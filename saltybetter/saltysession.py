from . import saltyclient
from .db import saltydb
from . import saltyai
from socketIO_client import SocketIO, LoggingNamespace
import logging
import signal
import sys
import argparse
import threading


# logging.basicConfig(filename='salty.log', format='%(asctime)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
logging.basicConfig(format='%(asctime)s-%(threadName)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


# TODO: Try Tensorflow/Keras
# TODO: add % based min/max bets

class SaltySession:

    def __init__(self):
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('-db', '--database', default='sqlite:///salt.db', help='Database connection string to use')
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

        # TODO: make some of these "private"
        self.t_locals = threading.local()
        self.t_locals.client = saltyclient.SaltyClient()
        self.t_locals.db = saltydb.SaltyDB(self.args.database, echo=self.args.echo)
        self.socket = SocketIO('www-cdn-twitch.saltybet.com', 1337, LoggingNamespace)
        self.socket.on('message', self._on_message)
        self.state = None
        self.mode = None
        self.balance = None
        self.tournament_balance = None
        self.session_id = None
        self.models = {}
        self.bet_model_id = None
        self._threads = []

        self._locks = {
            'models': threading.Lock()
        }

    def start(self):
        # self.t_locals.client.login(self.args.username, self.args.password)
        self.t_locals.client.spoof_login(
            '__cfduid=dd23d875eb54af698be6f623da2345ef91523785275; PHPSESSID=uqnrffud693pjevnihg6g1ndo7;',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'
        )

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        self.setup_models()
        self.socket.wait()

    # TODO: check if threads are running and close gracefully?.
    def stop(self, signum=None, frame=None):
        self.t_locals.db.end_session(self.balance)
        log.warning('Exiting... %s: %s' % (signum, frame))
        sys.exit()

    def setup_models(self):
        # train new logreg model and add to active models to use for this session
        def new_model():
            self.t_locals.db = saltydb.SaltyDB(self.args.database, echo=self.args.echo)
            training_data = self.t_locals.db.get_training_data(test_mode=self.args.test, test_limit=self.args.test)
            if not training_data:
                log.warning('%s thread done. No new model created because no training data was found.' % threading.current_thread().name)
                return

            ai_schema = [key for key in training_data[0].keys() if key != 'winner']
            trained_model = saltyai.LogRegression(ai_schema)
            trained_model.train(training_data, 'winner')
            trained_model_id = self.t_locals.db.add_ai_logreg_model(trained_model.to_json()).guid

            self._locks['models'].acquire()
            if self.bet_model_id is None:
                self.bet_model_id = trained_model_id
            self.models[trained_model_id] = trained_model
            self._locks['models'].release()
            log.info('%s thread done. Created new model %s' % (threading.current_thread().name, trained_model_id))

        # get best logreg model and add to active models
        def best_model():
            self.t_locals.db = saltydb.SaltyDB(self.args.database, echo=self.args.echo)
            bet_model_row = self.t_locals.db.get_best_logreg_model(min_bets=400)
            if bet_model_row is None:
                bet_model_row = self.t_locals.db.get_best_logreg_model(min_bets=0)
            if bet_model_row is None: # still!
                log.warning('%s thread done. Could not find a best model.' % threading.current_thread().name)
                return

            self._locks['models'].acquire()
            self.bet_model_id = bet_model_row.guid
            if bet_model_row.guid not in self.models:
                self.models[self.bet_model_id] = saltyai.LogRegression.from_json(bet_model_row.betas)
            self._locks['models'].release()
            log.info('%s thread done. Using best model: %s' % (threading.current_thread().name, bet_model_row))

        self._threads.append(threading.Thread(name='train_model', target=new_model))
        self._threads.append(threading.Thread(name='best_model', target=best_model))
        for thread in self._threads:
            thread.start()
            log.info('%s thread started.' % thread.name)

    def _on_message(self, *args):
        try:
            old_state = self.state
            self.update_state()
            if old_state != self.state:
                log.info('State: %s' % self.state)

                # fight over, have winner
                if self.state['status'] in ['1', '2']:
                    log.info('Player %s wins!' % self.state['status'])
                    self.t_locals.db.add_fight(self.state['p1name'], self.state['p2name'], int(self.state['status']), self.mode)
                    self.update_bet_stats()
                    # TODO: retrain with new fight results?

                elif self.state['status'] == 'open':
                    self.update_balances()
                    if self.session_id is None and self.mode in ['normal', 'exhibition']:
                        try:
                            self.session_id = self.t_locals.db.start_session(self.balance).guid
                        except saltydb.OpenSessionError:
                            self.t_locals.db.end_session(self.balance)
                            self.session_id = self.t_locals.db.start_session(self.balance).guid

                    log.info('Wallet: %s, Tournament Balance: %s' % (self.balance, self.tournament_balance))
                    self.make_bets()

        except Exception as e:
            log.exception('UH OH! %s' % e)

    def update_balances(self):
        # gets tournament balance when in tournament mode
        old_balance = None
        if self.mode in ['normal', 'exhibition']:
            old_balance = self.balance
            self.balance = self.t_locals.client.get_wallet_balance()[self.args.balance_source]

        # will always get tournament balance
        old_tournament_balance = self.tournament_balance
        self.tournament_balance = self.t_locals.client.get_tournament_balance()

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
                self.t_locals.db.increment_model_wins(guid)
                if self.session_id and guid == self.bet_model_id:
                    self.t_locals.db.increment_session_wins(self.session_id)
            else:
                self.t_locals.db.increment_model_losses(guid)
                if self.session_id and guid == self.bet_model_id:
                    self.t_locals.db.increment_session_losses(self.session_id)

    def update_state(self):
        self.state = self.t_locals.client.get_state()
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
        p1 = self.t_locals.db.get_or_add_fighter(self.state['p1name'])
        p2 = self.t_locals.db.get_or_add_fighter(self.state['p2name'])
        p1_wins = len(self.t_locals.db.get_wins_against(p1.guid, p2.guid))
        p2_wins = len(self.t_locals.db.get_wins_against(p2.guid, p1.guid))
        p1_fights = len(self.t_locals.db.get_fights(p1.guid))
        p2_fights = len(self.t_locals.db.get_fights(p2.guid))
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

        self._locks['models'].acquire()
        for guid, model in self.models.items():
            prediction = model.p(p_coeffs)

            if prediction > 0.5:
                model.bet = 2
            elif prediction <= 0.5:
                model.bet = 1

            if guid == self.bet_model_id:
                bet_amount = ((abs(float(prediction) - 0.5) / 0.5) * (self.args.max_bet - self.args.min_bet)) + self.args.min_bet
                log.info('Bet Prediction(%s): Player %s (%s)' % (guid, model.bet, prediction))

                # sanity checks
                if bet_amount < self.args.min_bet:
                    log.warning('bet_amount (%s) less than min_bet! Forced min_bet (%s).' % (bet_amount, self.args.min_bet))
                    bet_amount = self.args.min_bet
                elif bet_amount > self.args.max_bet:
                    log.warning('bet_amount (%s) greater than max_bet! Forced max_bet (%s).' % (bet_amount, self.args.max_bet))
                    bet_amount = self.args.max_bet

                self.t_locals.client.place_bet(model.bet, bet_amount)
            else:
                log.info('Prediction(%s): Player %s (%s)' % (guid, model.bet, prediction))
        self._locks['models'].release()


if __name__ == '__main__':
    SaltySession().start()
