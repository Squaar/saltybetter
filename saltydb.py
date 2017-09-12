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
                elo INT NOT NULL DEFAULT 0,
                wins INT NOT NULL DEFAULT 0,
                losses INT NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS fights(
                guid INTEGER PRIMARY KEY,
                p1 INT NOT NULL,
                p2 INT NOT NULL,
                winner INT NOT NULL,
                time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(p1) REFERENCES fighters(guid),
                FOREIGN KEY(p2) REFERENCES fighters(guid)
            );
        ''')
        self.conn.commit()
    
    def add_fight(self, state):
        if not state.get('p1name') or not state.get('p2name'):
            raise RuntimeError('Could not determine fighter names (%s, %s)' % (state.get('p1name'), state.get('p2name')))
        if state['p1name'] == state['p2name']:
            log.warning('Self fight detected. Ignoring. %s' % state['p1name'])
            return
        
        p1 = self.conn.execute('SELECT * FROM fighters WHERE name=?', (state['p1name'],)).fetchone()
        p2 = self.conn.execute('SELECT * FROM fighters WHERE name=?', (state['p2name'],)).fetchone()

        if state['status'] == '1':
            if not p1:
                p1 = self.add_fighter(state['p1name'])
            self.increment_wins(p1['guid'], p2['elo'] if p2 else 0)
            if not p2:
                p2 = self.add_fighter(state['p2name'])
            self.increment_losses(p2['guid'], p1['elo'] if p1 else 0)
        elif state['status'] == '2':
            if not p1:
                p1 = self.add_fighter(state['p1name'])
            self.increment_losses(p1['guid'], p2['elo'] if p2 else 0)
            if not p2:
                p2 = self.add_fighter(state['p2name'])
            self.increment_wins(p2['guid'], p1['elo'] if p1 else 0)
        else:
            raise RuntimeError('Could not determine a winner: %s' % state['status'])

        result = self.conn.execute('INSERT INTO fights (p1, p2, winner) VALUES (?, ?, ?)', (p1['guid'], p2['guid'], state['status']))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fights WHERE ROWID=?', (result.lastrowid,))
        new_fight = result.fetchone()
        log.info('Fight recorded %s' % list(new_fight))
        return new_fight

    def add_fighter(self, name):
        result = self.conn.execute('INSERT INTO fighters (name) VALUES (?)', (name,))
        self.conn.commit()
        new_fighter = self.get_fighter(result.lastrowid)
        log.info('Fighter added %s' % list(new_fighter))
        return new_fighter 

    def get_fighter(self, fighter_guid):
        result = self.conn.execute('SELECT * FROM fighters WHERE guid =?', (fighter_guid,))
        return result.fetchone()

    def increment_wins(self, fighter_guid, enemy_elo):
        result = self.conn.execute(
            'UPDATE fighters SET elo=(elo*(wins+losses)+?+100)/(wins+losses+1), wins=wins+1 WHERE guid=?',
            (enemy_elo, fighter_guid)
        )
        self.conn.commit()
        updated = self.get_fighter(fighter_guid)
        log.info('Incremented wins: %s' % list(updated))

    def increment_losses(self, fighter_guid, enemy_elo):
        result = self.conn.execute(
            'UPDATE fighters SET elo=(elo*(wins+losses)+?-100)/(wins+losses+1), losses=losses+1 WHERE guid=?',
            (enemy_elo, fighter_guid)
        )
        self.conn.commit()
        updated = self.get_fighter(fighter_guid)
        log.info('Incremented losses: %s' % list(updated))

