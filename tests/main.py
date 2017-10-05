from saltybetter import main
import saltybetter.saltyclient
import saltybetter.saltydb
from unittest.mock import patch
import unittest

@patch('saltybetter.main.logging')
@patch('saltybetter.main.saltyclient')
@patch('saltybetter.main.saltydb')
class SaltyControllerTest(unittest.TestCase):

    @patch('saltybetter.main.saltyclient')
    @patch('saltybetter.main.saltydb')
    def setUp(self, db, client):
        self.controller = main.SaltyController()
        self.db = db
        self.client = client

    def tearDown(self):
        pass

    def test_make_bet(self, db, client, log):
        self.controller.state = {'p1name': 'a', 'p2name': 'b'}

        # p1 more wins, p1 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 1, 'guid': 1}, {'name': 'b', 'elo': 0, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 1}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 1
        assert 0 <= bet_amount <= main._MAX_BET

        # p2 more wins, p2 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 0, 'guid': 1}, {'name': 'b', 'elo': 1, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 2}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 2
        assert 0 <= bet_amount <= main._MAX_BET

        # p1 more wins, p2 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 0, 'guid': 1}, {'name': 'b', 'elo': 1, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 1}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 1
        assert 0 <= bet_amount <= main._MAX_BET

        # p2 more wins, p1 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 1, 'guid': 1}, {'name': 'b', 'elo': 0, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 2}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 2
        assert 0 <= bet_amount <= main._MAX_BET
 
        # equal wins, p1 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 1, 'guid': 1}, {'name': 'b', 'elo': 0, 'guid': 2}]
        self.controller.db.get_fights.return_value = []
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 1
        assert 0 <= bet_amount <= main._MAX_BET

        # equal wins, p2 higher elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 0, 'guid': 1}, {'name': 'b', 'elo': 1, 'guid': 2}]
        self.controller.db.get_fights.return_value = []
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 2
        assert 0 <= bet_amount <= main._MAX_BET

        # p1 more wins, equal elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 0, 'guid': 1}, {'name': 'b', 'elo': 0, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 1}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 1
        assert 0 <= bet_amount <= main._MAX_BET

        # p2 more wins, equal elo
        self.controller.db.get_or_add_fighter.side_effect = [{'name': 'a', 'elo': 0, 'guid': 1}, {'name': 'b', 'elo': 0, 'guid': 2}]
        self.controller.db.get_fights.return_value = [{'winner': 2}]
        self.controller.make_bet()
        bet_on = self.controller.client.place_bet.call_args[0][0]
        bet_amount = self.controller.client.place_bet.call_args[0][1]
        assert bet_on == 2
        assert 0 <= bet_amount <= main._MAX_BET

if __name__ == '__main__':
    unittest.main()
