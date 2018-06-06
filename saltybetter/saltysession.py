from . import saltyclient
from .db import saltydb
from . import saltyai
from socketIO_client import SocketIO, LoggingNamespace
import logging
import signal
import sys
import argparse


# logging.basicConfig(filename='salty.log', format='%(asctime)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


# TODO: Try Tensorflow/Keras
# TODO: implement --init_db

class SaltySession:

    def __init__(self):
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('-db', '--database', default='sqlite:///salt.db', help='SQLite database file to use')
        arg_parser.add_argument('-m', '--memory', action='store_true', help='Use in-memory database instead of a database file. This takes precedence over -db if it is set.')
        arg_parser.add_argument('-u', '--username', help='Saltybet login username. Currently non-functional. You must spoof login!')
        arg_parser.add_argument('-p', '--password', help='Saltybet login password. Currently non-functional. You must spoof login!')
        arg_parser.add_argument('-t', '--test', type=int, default=0, help='Test mode. Puts a limiter on the training data query so it doesn\'t take forever')
        arg_parser.add_argument('-e', '--echo', action='store_true', help='Echo DB queries to std.out')
        arg_parser.add_argument('--init_db', action='store_true', help='Test connection to the DB and initialize tables')
        arg_parser.add_argument('--max_bet', default=1000, type=int, help='The maximum amount of saltybux saltybetter will bet')
        arg_parser.add_argument('--min_bet', default=10, type=int, help='The minimum amount of saltybux saltybetter will bet')
        arg_parser.add_argument('--balance_source', default='page', choices=['page', 'ajax'],
                                help='Where saltybetter will look for the current wallet balance. Valid values are "page" and "ajax". Currently, only "page" works.')
        self.args = arg_parser.parse_args()

        self.client = saltyclient.SaltyClient()
        self.db = saltydb.SaltyDB(self.args.database, echo=self.args.echo)
        self.socket = SocketIO('www-cdn-twitch.saltybet.com', 1337, LoggingNamespace)
        self.socket.on('message', self._on_message)
        self.state = None
        self.mode = None
        self.balance = None
        self.tournament_balance = None
        self.session_id = None
        self.models = {}

        # TODO: Train in a thread
        training_data = self.db.get_training_data(test_mode=self.args.test, test_limit=self.args.test)
        # TODO: should handle no training_data
        ai_schema = [key for key in training_data[0].keys() if key != 'winner']
        trained_model = saltyai.LogRegression(ai_schema)
        trained_model.train(training_data, 'winner')
        trained_model_id = self.db.add_ai_logreg_model(trained_model.to_json()).guid
        self.models[trained_model_id] = trained_model

        bet_model_row = self.db.get_best_logreg_model(min_bets=400)
        if bet_model_row is None:
            bet_model_row = self.db.get_best_logreg_model(min_bets=0)
        if bet_model_row.guid == trained_model_id:
            self.bet_model_id = trained_model_id
        else:
            bet_model = saltyai.LogRegression.from_json(bet_model_row.betas)
            self.bet_model_id = bet_model_row.guid
            self.models[self.bet_model_id] = bet_model
        log.info('Using best model: %s' % bet_model_row)

    def update_balances(self):
        # gets tournament balance when in tournament mode
        old_balance = None
        if self.mode in ['normal', 'exhibition']:
            old_balance = self.balance
            self.balance = self.client.get_wallet_balance()[self.args.balance_source]

        # will always get tournament balance
        old_tournament_balance = self.tournament_balance
        self.tournament_balance = self.client.get_tournament_balance()

        if old_balance is not None and self.balance < old_balance:
            log.info('Lost bet! Old balance: %s, New balance: %s, Profit: %s' % (
                old_balance, self.balance, self.balance - old_balance
            ))
        elif old_balance is not None and self.balance > old_balance:
            log.info('Won bet!  Old balance: %s, New balance: %s, Profit: %s' % (
                old_balance, self.balance, self.balance - old_balance
            ))

        if old_tournament_balance is not None and self.tournament_balance < old_tournament_balance:
            log.info('Lost tournament bet! Old balance: %s, New balance: %s, Profit: %s' % (
                old_tournament_balance, self.tournament_balance, self.tournament_balance - old_tournament_balance
            ))
        elif old_tournament_balance is not None and self.tournament_balance > old_tournament_balance:
            log.info('Won tournament bet!  Old balance: %s, New balance: %s, Profit: %s' % (
                old_tournament_balance, self.tournament_balance, self.tournament_balance - old_tournament_balance
            ))

    def update_bet_stats(self):
        winner = int(self.state['status'])  # 1 or 2
        for guid, model in self.models.items():
            if winner == model.bet:
                self.db.increment_model_wins(guid)
                if self.session_id and guid == self.bet_model_id:
                    self.db.increment_session_wins(self.session_id)
            else:
                self.db.increment_model_losses(guid)
                if self.session_id and guid == self.bet_model_id:
                    self.db.increment_session_losses(self.session_id)

    def update_state(self):
        self.state = self.client.get_state()
        if 'more matches until the next tournament!' in self.state['remaining'] or 'Tournament mode will be activated after the next match!' in self.state['remaining']:
            self.mode = 'normal'
        elif 'characters are left in the bracket!' in self.state['remaining'] or 'FINAL ROUND!' in self.state['remaining']:
            self.mode = 'tournament'
        elif 'exhibition matches left!' in self.state['remaining'] or 'after the next exhibition match!' in self.state['remaining']:
            self.mode = 'exhibition'
        else:
            raise RuntimeError('Could not determine mode: %s' % self.state['remaining'])
        return self.state

    def make_bets(self):
        p1 = self.db.get_or_add_fighter(self.state['p1name'])
        p2 = self.db.get_or_add_fighter(self.state['p2name'])
        p1_wins = len(self.db.get_wins_against(p1.guid, p2.guid))
        p2_wins = len(self.db.get_wins_against(p2.guid, p1.guid))
        p1_fights = len(self.db.get_fights(p1.guid))
        p2_fights = len(self.db.get_fights(p2.guid))
        # TODO: think of a better solution to avoid / by 0?
        p1_winpct = 50.0 if p1.wins + p1.losses == 0 else p1.wins / (p1.wins + p1.losses) * 100
        p2_winpct = 50.0 if p2.wins + p2.losses == 0 else p2.wins / (p2.wins + p2.losses) * 100
        p_coeffs = {
            'elo_diff': p1.elo - p2.elo,
            'wins_diff': p1_wins - p2_wins,
            'win_pct_diff': p1_winpct - p2_winpct
        }

        log.info('P1({name}) elo: {elo}, wins vs p2: {wins}, win pct: {winpct}, fights: {nFights}'.format(
            name=p1.name,
            elo=p1.elo,
            wins=p1_wins,
            winpct=p1_winpct,
            nFights=p1_fights
        ))
        log.info('P2({name}) elo: {elo}, wins vs p1: {wins}, win pct: {winpct}, fights: {nFights}'.format(
            name=p2.name,
            elo=p2.elo,
            wins=p2_wins,
            winpct=p2_winpct,
            nFights=p2_fights
        ))

        for guid, model in self.models.items():
            prediction = model.p(p_coeffs)
            if prediction > 0.5:
                model.bet = 2
            elif prediction < 0.5:
                model.bet = 1
            else:
                model.bet = 1
                log.info('Prediction is a tie!')

            if guid == self.bet_model_id:
                log.info('Bet Prediction(%s): Player %s (%s)' % (guid, model.bet, prediction))
                # TODO: find a smarter way to decide amount to bet
                amount = 10

                # sanity checks
                if amount < self.args.min_bet:
                    amount = self.args.min_bet
                elif amount > self.args.max_bet:
                    amount = self.args.max_bet

                self.client.place_bet(model.bet, amount)
            else:
                log.info('Prediction(%s): Player %s (%s)' % (guid, model.bet, prediction))

    # TODO: cmd line args
    def start(self):
        # self.client.login(self.args.username, self.args.password)
        self.client.spoof_login(
            '__cfduid=dd23d875eb54af698be6f623da2345ef91523785275; PHPSESSID=uqnrffud693pjevnihg6g1ndo7;',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'
        )

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        self.socket.wait()

    def _on_message(self, *args):
        try:
            old_state = self.state
            self.update_state()
            if old_state != self.state:
                log.info('State: %s' % self.state)

                # fight over, have winner
                if self.state['status'] in ['1', '2']:
                    log.info('Player %s wins!' % self.state['status'])
                    self.db.add_fight(self.state['p1name'], self.state['p2name'], int(self.state['status']), self.mode)
                    self.update_bet_stats()
                    # TODO: retrain with new fight results?

                elif self.state['status'] == 'open':
                    self.update_balances()
                    if self.session_id is None and self.mode in ['normal', 'exhibition']:
                        try:
                            self.session_id = self.db.start_session(self.balance).guid
                        except saltydb.OpenSessionError:
                            self.db.end_session(self.balance)
                            self.session_id = self.db.start_session(self.balance).guid

                    log.info('Wallet: %s, Tournament Balance: %s' % (self.balance, self.tournament_balance))
                    self.make_bets()

        except Exception as e:
            log.exception('UH OH! %s' % e)

    def stop(self, signum=None, frame=None):
        self.db.end_session(self.balance)
        log.warning('Exiting... %s' % signum)
        sys.exit()


if __name__ == '__main__':
    SaltySession().start()
