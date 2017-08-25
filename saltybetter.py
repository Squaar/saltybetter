#!/home/squaar/brogramming/python/saltybetter-py/.env/bin/python3
import saltyclient
import saltydb
import logging
import time

logging.basicConfig(filename='salty.log', format='%(asctime)s-%(name)s-%(levelname)s-%(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

class SaltyController():

    def __init__(self):
        self.client = saltyclient.SaltyClient()
        self.db = saltydb.saltyDB('salt.db')
        self.state = None
        self.balance = None
        self.tournament_balance = None

    def main(self):
        # self.client.login('saltyface@gmail.com', 'saltyface')
        self.client.spoof_login('__cfduid=d4ad05a1bdff57927e01f223ce5d3cc771503283048; PHPSESSID=uj61t6n9aokf6cdb8qd7a77963')
        while True:
            new_state = self.client.get_state()
            if new_state != self.state:
                if new_state['status'] != 'open' and new_state['status'] != 'closed':
                    self.db.add_fight(new_state)
                self.state = new_state
                self.balance = self.client.get_wallet_balance()
                self.tournament_balance = self.client.get_tournament_balance()
                log.info('State: ' + str(self.state))
                log.info('Wallet Balance: ' + str(self.balance))
                log.info('Tournament Balance: ' + self.tournament_balance)
            time.sleep(10)


if __name__ == '__main__':
    SaltyController().main()
