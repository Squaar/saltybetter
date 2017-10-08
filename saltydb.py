import sqlite3
import logging

log = logging.getLogger(__name__)

MEMORY = ':memory:'

class SaltyDB():

    def __init__(self, db=MEMORY, elo_stake=.05):
        self.elo_stake = elo_stake
        self.conn = sqlite3.connect(db)
        self.conn.row_factory = sqlite3.Row
        ##TODO: add tournament bool to fights
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS fighters(
                guid INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                elo REAL NOT NULL DEFAULT 100,
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

            CREATE TABLE IF NOT EXISTS sessions(
                guid INTEGER PRIMARY KEY,
                startTS DATETIME DEFAULT CURRENT_TIMESTAMP,
                endTS DATETIME,
                startBalance INT NOT NULL,
                endBalance INT
            );
        ''')
        self.conn.commit()
    
    def add_fight(self, p1name, p2name, winner):
        if p1name == p2name:
            log.warning('Self fight detected. Ignoring. %s' % state['p1name'])
            return
        
        p1 = self.get_or_add_fighter(p1name)
        p2 = self.get_or_add_fighter(p2name)

        if winner == 1:
            self.increment_wins(p1['guid'], p2['elo'] if p2 else 0)
            self.increment_losses(p2['guid'])
        elif winner == 2:
            self.increment_losses(p1['guid'])
            self.increment_wins(p2['guid'], p1['elo'] if p1 else 0)
        else:
            raise RuntimeError("Winner must be in [1, 2]: %s" % winner)

        result = self.conn.execute('INSERT INTO fights (p1, p2, winner) VALUES (?, ?, ?)', (p1['guid'], p2['guid'], winner))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fights WHERE ROWID=?', (result.lastrowid,))
        new_fight = result.fetchone()
        log.info('Fight recorded %s' % list(new_fight))
        return new_fight

    # returns newly created fighter
    def add_fighter(self, name):
        result = self.conn.execute('INSERT INTO fighters (name) VALUES (?)', (name,))
        self.conn.commit()
        new_fighter = self.get_fighter(result.lastrowid)
        log.info('Fighter added %s' % list(new_fighter))
        return new_fighter 

    def get_or_add_fighter(self, name):
        fighter = self.get_fighter(name)
        if not fighter:
            fighter = self.add_fighter(name)
        return fighter

    # fighter can be name or guid
    def get_fighter(self, fighter):
        result = self.conn.execute('SELECT * FROM fighters WHERE guid =? or name =?', (fighter, fighter))
        return result.fetchone()

    def get_fights(self, p1_guid, p2_guid):
        guids = ",".join([str(p1_guid), str(p2_guid)])
        result = self.conn.execute('SELECT * FROM fights WHERE p1 IN (?) and p2 in (?)', (guids, guids))
        return result.fetchall()

    def increment_wins(self, fighter_guid, enemy_elo):
        result = self.conn.execute(
            'UPDATE fighters SET elo=elo+(?*?), wins=wins+1 WHERE guid=?',
            (self.elo_stake, enemy_elo, fighter_guid)
        )
        self.conn.commit()
        updated = self.get_fighter(fighter_guid)
        log.info('Incremented wins: %s' % list(updated))

    def increment_losses(self, fighter_guid):
        result = self.conn.execute(
            'UPDATE fighters SET elo=elo-(?*elo), losses=losses+1 WHERE guid=?',
            (self.elo_stake, fighter_guid)
        )
        self.conn.commit()
        updated = self.get_fighter(fighter_guid)
        log.info('Incremented losses: %s' % list(updated))

    def start_session(self, balance):
        if balance is None:
            raise TypeError('Balance cannot be None')
        result = self.conn.execute('SELECT * FROM sessions WHERE endTS IS NULL')
        open_sessions = result.fetchall()
        if len(open_sessions) > 0:
            raise OpenSessionError('A session is already open!', len(open_sessions))
        
        result = self.conn.execute('INSERT INTO sessions (startBalance) VALUES (?)', (balance,))
        self.conn.commit()

        result = self.conn.execute('SELECT * FROM sessions WHERE guid=(SELECT MAX(guid) FROM sessions)')
        new_session = result.fetchone()
        log.info('Session started: %s' % list(new_session))

    # does nothing if there are no open sessions, ends only the most recent session
    def end_session(self, balance):
        if balance is None:
            raise TypeError('Balance cannot be None')
        result = self.conn.execute(
            'UPDATE sessions SET endTS=(SELECT MAX(time) FROM fights), endBalance=? WHERE guid=(SELECT MAX(guid) FROM sessions) AND endTS IS NULL', 
            (balance,)
        )
        if result.rowcount > 1:
            log.warning('More than one session closed: %s' % result.rowcount)
        self.conn.commit()

        result = self.conn.execute('SELECT * FROM sessions WHERE guid=(SELECT MAX(guid) FROM sessions)')
        closed_session = result.fetchone()
        log.info('Session ended: %s' % list(closed_session))

class OpenSessionError(RuntimeError):
    def __init__(self, message, open_sessions):
        super().__init__(message, open_sessions)
        self.message = message
        self.open_sessions = open_sessions
