import sqlite3
import logging

log = logging.getLogger(__name__)

MEMORY = ':memory:'

class SaltyDB():

    def __init__(self, db=MEMORY):
        self.conn = sqlite3.connect(db)
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
        p1 = self.conn.execute('SELECT * FROM fighters WHERE name="?"', state['p1name'])
        p2 = self.conn.execute('SELECT * FROM fighters WHERE name="?"', state['p2name'])

        if not p1:
            p1 = self.add_fighter(state['p1name'])
        if not p2:
            p2 = self.add_fighter(state['p2name'])

        result = self.conn.execute('INSERT INTO fights VALUES (?, ?, ?)', (p1['name'], p2['name'], state['status']))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fights WHERE ROWID=?', (result.lastrowid))
        log.info('Fight recorded %s' % result)
        return result

    def add_fighter(self, name):
        result = self.conn.execute('INSERT INTO fighters VALUES (?)', (name))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fighters WHERE ROWID=?', (result.lastrowid))
        log.info('Fighter added %s' % result)
        return result 
