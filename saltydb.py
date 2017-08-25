import sqlite3
import logging

log = logging.getLogger(__name__)

MEMORY = ':memory:'

class SaltyDB():

    def __init__(self, db=MEMORY):
        self.conn = sqlite3.connect(db)
        result = conn.execute('.tables')
        ##TODO: set up tables & schemas
    
    def add_fight(self, state):
        p1 = self.conn.execute('SELECT * FROM fighters WHERE name="?"', state['p1name'])
        p2 = self.conn.execute('SELECT * FROM fighters WHERE name="?"', state['p2name'])

        if not p1:
            self.add_fighter(state['p1name'])
        if not p2:
            self.add_fighter(state['p2name'])

    def add_fighter(self, name):
        pass

