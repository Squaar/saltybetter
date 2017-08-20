#!/home/squaar/brogramming/python/saltybetter-py/.env/bin/python3
import saltyclient
import logging
import time

logging.basicConfig(level=logging.INFO)

class SaltyController():

    def __init__(self, email, password):
        self.client = saltyclient.SaltyClient(email, password)

    def main(self):
        while True:
            logging.info('State: ' + str(self.client.get_state()))
            logging.info('Wallet Balance: ' + str(self.client.get_wallet_balance()))
            logging.info('Tournament Balance: ' + self.client.get_tournament_balance())
            time.sleep(10)


if __name__ == '__main__':
    SaltyController('saltyface@gmail.com', 'saltyface').main()
