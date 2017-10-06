#!/home/squaar/brogramming/python/saltybetter/.env/bin/python3
import saltyclient
import saltydb
import logging
import time

# logging.basicConfig(filename='salty.log', format='%(asctime)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

_REFRESH_INTERVAL = 5 # seconds
_USER = 'saltyface@gmail.com'
_PASSWORD = 'saltyface'
_MAX_BET = 1000
_MIN_BET = _MAX_BET * .01
_WIN_MULTIPLIER = _MAX_BET * 0.1
_BALANCE_SOURCE = 'page' # 'page' or 'ajax'

class SaltyController():

    def __init__(self):
        self.client = saltyclient.SaltyClient()
        self.db = saltydb.SaltyDB('salt.db')
        self.state = None
        self.mode = None
        self.balance = None
        self.tournament_balance = None

    def update_mode(self):
        if 'more matches until the next tournament!' in self.state['remaining']:
            self.mode = 'normal'
        elif 'characters are left in the bracket!' in self.state['remaining']:
            self.mode = 'tournament'
        elif 'exhibition matches left!' in self.state['remaining']:
            self.mode = 'exhibition'

    def update_balances(self):
        old_balance = self.balance
        old_tournament_balance = self.tournament_balance
        self.balance = self.client.get_wallet_balance()[_BALANCE_SOURCE]
        self.tournament_balance = self.client.get_tournament_balance()

        if old_balance is None or old_tournament_balance is None:
            return # no change to log yet

        if self.balance < old_balance:
            log.info('Lost bet! Old balance: %s, New balance: %s, Profit: %s' % (
                old_balance, self.balance, self.balance - old_balance
            ))
        elif self.balance > old_balance:
            log.info('Won bet!  Old balance: %s, New balance: %s, Profit: %s' % (
                old_balance, self.balance, self.balance - old_balance
            ))

        if self.tournament_balance < old_tournament_balance:
            log.info('Lost tournament bet! Old balance: %s, New balance: %s, Profit: %s' % (
                old_tournament_balance, self.tournament_balance, self.tournament_balance - old_tournament_balance
            ))
        elif self.tournament_balance > old_tournament_balance:
            log.info('Won tournament bet!  Old balance: %s, New balance: %s, Profit: %s' % (
                old_tournament_balance, self.tournament_balance, self.tournament_balance - old_tournament_balance
            ))

    def make_bet(self):
        p1 = self.db.get_or_add_fighter(self.state['p1name'])
        p2 = self.db.get_or_add_fighter(self.state['p2name'])
        past_fights = self.db.get_fights(p1['guid'], p2['guid'])
        p1_wins = [fight for fight in past_fights if fight['winner'] == p1['guid']]
        p2_wins = [fight for fight in past_fights if fight['winner'] == p2['guid']]
        log.info('P1(%s) elo: %s, wins: %s; P2(%s) elo: %s, wins: %s' % (p1['name'], p1['elo'], len(p1_wins), p2['name'], p2['elo'], len(p2_wins)))

        win_bonus = abs(len(p1_wins) - len(p2_wins)) * _WIN_MULTIPLIER

        if len(p1_wins) > len(p2_wins) or (len(p1_wins) == len(p2_wins) and p1['elo'] > p2['elo']):
            bet_on = 1
            amount = abs(p1['elo'] - p2['elo']) / max(abs(p1['elo']), abs(p2['elo'])) * _MAX_BET + win_bonus

        elif len(p2_wins) > len(p1_wins) or (len(p2_wins) == len(p1_wins) and p2['elo'] > p1['elo']):
            bet_on = 2
            amount = abs(p1['elo'] - p2['elo']) / max(abs(p1['elo']), abs(p2['elo'])) * _MAX_BET + win_bonus

        else: # len(p1_wins) == len(p2_wins) and p1['elo'] == p2['elo']
            bet_on = 1
            amount = _MIN_BET
            log.info('P1 and P2 have the same wins and elo, betting min on P1 by default.')

        # sanity checks
        if amount < _MIN_BET:
            amount = _MIN_BET
        elif amount > _MAX_BET:
            amount = _MAX_BET
        
        self.client.place_bet(bet_on, amount)

    def main(self):
        # self.client.login(_USER, _PASSWORD)
        self.client.spoof_login(
                '__cfduid=d4ad05a1bdff57927e01f223ce5d3cc771503283048; PHPSESSID=kpplnfa9oks5b4ekodobqg66s2',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.91 Safari/537.36'
        )
        while True:
            try:
                new_state = self.client.get_state()
                if new_state != self.state:
                    self.state = new_state
                    log.info(self.state)

                    if self.state['status'] in ['1', '2']: # fight over, have winner
                        self.db.add_fight(self.state['p1name'], self.state['p2name'], int(self.state['status']))
                    elif self.state['status'] == 'open':
                        self.update_mode()
                        self.update_balances()
                        log.info('Wallet: %s, Tournament Balance: %s' % (self.balance, self.tournament_balance))
                        self.make_bet()

            except Exception as e:
                log.exception('UH OH! %s' % e)
            time.sleep(_REFRESH_INTERVAL)

if __name__ == '__main__':
    SaltyController().main()
