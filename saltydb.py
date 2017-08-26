import sqlite3
import logging

log = logging.getLogger(__name__)

MEMORY = ':memory:'

class SaltyDB():

    def __init__(self, db=MEMORY):
        self.conn = sqlite3.connect(db)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS fighters(
                guid INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                MMR INT DEFAULT 1000,
                wins INT DEFAULT 0,
                losses INT DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS fights(
                guid INTEGER PRIMARY KEY,
                p1 INT NOT NULL,
                p2 INT NOT NULL,
                winner INT NOT NULL,
                time DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(p1) REFERENCES fighters(guid),
                FOREIGN KEY(p2) REFERENCES fighters(guid)
            );
        ''')
        self.conn.commit()
    
    def add_fight(self, state):
        p1 = self.conn.execute('SELECT * FROM fighters WHERE name=?', (state['p1name'],)).fetchone()
        p2 = self.conn.execute('SELECT * FROM fighters WHERE name=?', (state['p2name'],)).fetchone()

        if state['status'] == '1':
            if not p1:
                p1 = self.add_fighter(state['p1name'], 1, 0)
            else:
                self.increment_wins(p1['guid'])
            if not p2:
                p2 = self.add_fighter(state['p2name'], 0, 1)
            else:
                self.increment_losses(p2['guid'])
        elif state['status'] == '2':
            if not p1:
                p1 = self.add_fighter(state['p1name'], 0, 1)
            else:
                self.increment_wins(p2['guid'])
            if not p2:
                p2 = self.add_fighter(state['p2name'], 1, 0)
            else:
                self.increment_losses(p1['guid'])
        else:
            raise RuntimeError('Could not determine a winner: %s' % state['status'])

        result = self.conn.execute('INSERT INTO fights (p1, p2, winner) VALUES (?, ?, ?)', (p1['guid'], p2['guid'], state['status']))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fights WHERE ROWID=?', (result.lastrowid,))
        new_fight = result.fetchone()
        log.info('Fight recorded %s' % list(new_fight))
        return new_fight

    def add_fighter(self, name, wins=0, losses=0):
        result = self.conn.execute('INSERT INTO fighters (name, wins, losses) VALUES (?, ?, ?)', (name, wins, losses))
        self.conn.commit()
        # import pdb; pdb.set_trace()
        result = self.conn.execute('SELECT * FROM fighters WHERE ROWID=?', (result.lastrowid,))
        new_fighter = result.fetchone()
        log.info('Fighter added %s' % list(new_fighter))
        return new_fighter 

    def increment_wins(self, fighter_guid):
        self.conn.execute('UPDATE fighters SET wins=wins+1 WHERE guid =?', (fighter_guid,))
        log.info('Incremented %s\'s wins')

    def increment_losses(self, fighter_guid):
        self.conn.execute('UPDATE fighters SET losses=losses+1 WHERE guid =?', (fighter_guid,))
        log.info('Incremented %s\'s losses')
