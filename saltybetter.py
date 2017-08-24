#!/home/squaar/brogramming/python/saltybetter-py/.env/bin/python3
import saltyclient
import logging
import time

class SaltyController():

    def __init__(self, log_lvl=logging.NOTSET):
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_lvl)
        self.client = saltyclient.SaltyClient(log_lvl=log_lvl)

    def main(self):
        # self.client.login('saltyface@gmail.com', 'saltyface')
        self.client.spoof_login('__cfduid=d4ad05a1bdff57927e01f223ce5d3cc771503283048; PHPSESSID=uj61t6n9aokf6cdb8qd7a77963')
        # while True:
        logging.info('State: ' + str(self.client.get_state()))
        logging.info('Wallet Balance: ' + str(self.client.get_wallet_balance()))
        logging.info('Tournament Balance: ' + self.client.get_tournament_balance())
        # time.sleep(10)


if __name__ == '__main__':
    SaltyController(logging.DEBUG).main()
