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
                        self.db.add_fight(self.state)
                    self.balance = self.client.get_wallet_balance()
                    self.tournament_balance = self.client.get_tournament_balance()
                    log.debug('State: ' + str(self.state))
                    log.debug('Wallet Balance: ' + str(self.balance))
                    log.debug('Tournament Balance: ' + self.tournament_balance)
            except Exception as e:
                log.exception('UH OH! %s' % e)
            time.sleep(_REFRESH_INTERVAL)


if __name__ == '__main__':
    SaltyController().main()
