#!/home/squaar/brogramming/python/saltybetter-py/.env/bin/python3
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

class SaltyController():

    def __init__(self):
        self.client = saltyclient.SaltyClient()
        self.db = saltydb.SaltyDB('salt.db')
        self.state = None
        self.balance = None
        self.tournament_balance = None

    def main(self):
        # self.client.login(_USER, _PASSWORD)
        self.client.spoof_login('__cfduid=d4ad05a1bdff57927e01f223ce5d3cc771503283048; PHPSESSID=uj61t6n9aokf6cdb8qd7a77963')
        while True:
            try:
                new_state = self.client.get_state()
                if new_state != self.state:
                    self.state = new_state
                    log.info(self.state)
                    if self.state['status'] in ['1', '2']: # fight over, have winner
                        self.db.add_fight(self.state['p1name'], self.state['p2name'], self.state['status'])
                    elif self.state['status'] == 'open':
                        # Decide who to bet on
                        p1 = self.db.get_fighter(self.state['p1name'])
                        p2 = self.db.get_fighter(self.state['p2name'])
                        self.balance = self.client.get_wallet_balance()
                        self.tournament_balance = self.client.get_tournament_balance()
                        log.info('Wallet: %s, Tournament Balance: %s' % (self.balance, self.tournament_balance))
                        self.client.place_bet(1, 10)
            except Exception as e:
                log.exception('UH OH! %s' % e)
            time.sleep(_REFRESH_INTERVAL)


if __name__ == '__main__':
    SaltyController().main()
