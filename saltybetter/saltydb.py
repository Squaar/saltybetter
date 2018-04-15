import sqlite3
import logging

log = logging.getLogger(__name__)

MEMORY = ':memory:'

class SaltyDB():

    def __init__(self, db=MEMORY, elo_stake=.05):
        self.elo_stake = elo_stake
        self.conn = sqlite3.connect(db)
        self.conn.row_factory = sqlite3.Row
        ##TODO: add table to keep betas between sesisons
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS fighters(
                guid INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                elo REAL NOT NULL DEFAULT 100,
                wins INT NOT NULL DEFAULT 0,
                losses INT NOT NULL DEFAULT 0
            );

            DROP VIEW IF EXISTS v_fighters;
            CREATE VIEW IF NOT EXISTS v_fighters AS
            SELECT *,
                wins + losses AS nFights,
                CAST(wins AS REAL) / CAST(wins + losses AS REAL) * 100 AS winPct,
                name LIKE 'Team %' AS isTournament
            FROM fighters;

            CREATE TABLE IF NOT EXISTS fights(
                guid INTEGER PRIMARY KEY,
                p1 INT NOT NULL,
                p2 INT NOT NULL,
                winner INT NOT NULL,
                time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                mode TEXT NOT NULL,
                FOREIGN KEY(p1) REFERENCES fighters(guid),
                FOREIGN KEY(p2) REFERENCES fighters(guid)
            );

            DROP VIEW IF EXISTS v_fights;
            CREATE VIEW IF NOT EXISTS v_fights AS
            SELECT *,
                (SELECT MAX(guid) FROM sessions WHERE fights.time > sessions.startTS) AS session
            FROM fights;

            CREATE TABLE IF NOT EXISTS sessions(
                guid INTEGER PRIMARY KEY,
                startTS DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                endTS DATETIME,
                startBalance INT NOT NULL,
                endBalance INT,
                wonBets INT NOT NULL DEFAULT 0,
                lostBets INT NOT NULL DEFAULT 0
            );

            DROP VIEW IF EXISTS v_sessions;
            CREATE VIEW IF NOT EXISTS v_sessions AS
            SELECT guid, 
                DATETIME(startTS, 'localtime') AS startTS,
                DATETIME(endTS, 'localtime') AS endTS,
                startBalance,
                endBalance,
                wonBets, 
                lostBets,
                CAST(wonBets AS REAL) / CAST((wonBets + lostBets) AS REAL) * 100 AS wonBetsPct
            FROM sessions;

            CREATE TABLE IF NOT EXISTS bets(
                guid INTEGER PRIMARY KEY,
                fight INT NOT NULL,
                session INT NOT NULL,
                amount INT NOT NULL,
                won INT,
                preBalance INT NOT NULL,
                profit INT,
                FOREIGN KEY(fight) REFERENCES fights(guid),
                FOREIGN KEY(session) REFERENCES sessions(guid)
            );

            CREATE TABLE IF NOT EXISTS ai_logreg_models(
                guid INTEGER PRIMARY KEY,
                betas TEXT NOT NULL,
                wonBets INT NOT NULL DEFAULT 0,
                lostBets INT NOT NULL DEFAULT 0
            );

            DROP VIEW IF EXISTS v_ai_logreg_models;
            CREATE VIEW IF NOT EXISTS v_ai_logreg_models AS
            SELECT guid,
                betas,
                wonBets,
                lostBets,
                CAST(wonBets AS REAL) / CAST((wonBets + lostBets) AS REAL) * 100 AS wonBetsPct
            FROM ai_logreg_models;
        ''')
        self.conn.commit()

    def add_ai_logreg_model(self, serialized):
        result = self.conn.execute('INSERT INTO ai_logreg_models (betas) VALUES(?)', (serialized,))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM ai_logreg_models WHERE ROWID=?', (result.lastrowid,))
        new_model = result.fetchone()
        log.info('Saved LogReg model: %s' % list(new_model))
        return new_model

    def add_fight(self, p1name, p2name, winner, mode):
        if p1name == p2name:
            log.warning('Self fight detected. Ignoring. %s' % p1name)
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

        result = self.conn.execute('INSERT INTO fights (p1, p2, winner, mode) VALUES (?, ?, ?, ?)', (p1['guid'], p2['guid'], winner, mode))
        self.conn.commit()
        result = self.conn.execute('SELECT * FROM fights WHERE ROWID=?', (result.lastrowid,))
        new_fight = list(result.fetchone())
        log.info('Fight recorded %s' % new_fight)
        return new_fight[0]

    def increment_won_bets(self, session_guid, model_guid):
        if session_guid:
            result = self.conn.execute('UPDATE sessions SET wonBets = wonBets + 1 WHERE guid = ?', (session_guid,))
        result = self.conn.execute('UPDATE ai_logreg_models SET wonBets = wonBets + 1 WHERE guid = ?', (model_guid,))
        self.conn.commit()

    def increment_lost_bets(self, session_guid, model_guid):
        if session_guid:
            result = self.conn.execute('UPDATE sessions SET lostBets = lostBets + 1 WHERE guid = ?', (session_guid,))
        result = self.conn.execute('UPDATE ai_logreg_models SET lostBets = lostBets + 1 WHERE guid = ?', (model_guid,))
        self.conn.commit()

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
        result = self.conn.execute('SELECT * FROM fighters WHERE guid = ? or name = ?', (fighter, fighter))
        return result.fetchone()

    def get_fights(self, p1_guid, p2_guid):
        guids = ",".join([str(p1_guid), str(p2_guid)])
        result = self.conn.execute('SELECT * FROM fights WHERE p1 IN (?) and p2 in (?)', (guids, guids))
        return result.fetchall()

    def get_fights(self, guid):
        result = self.conn.execute('SELECT * FROM fights WHERE p1 = ? or p2 = ?', (guid, guid))
        return result.fetchall()
    
    # get p1's wins against p2. includes where #s reversed
    def get_wins_against(self, p1_guid, p2_guid):
        result = self.conn.execute('''
            SELECT * FROM fights 
            WHERE (p1 = ? AND p2 = ? AND winner = 1)
            OR    (p1 = ? AND p2 = ? AND winner = 2)
        ''',(
            p1_guid, p2_guid,
            p2_guid, p1_guid
        ))
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
        return new_session

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

    def get_training_data(self):
        log.info('Generating training data, this may take a few moments...')
        # winner - 1 to put in range 0,1. p() will predict probability of p2 winning
        result = self.conn.execute ('''
            SELECT p1elo - p2elo AS elo_diff,
            p1winsvp2 - p2winsvp1 AS wins_diff,
            p1winpct - p2winpct AS win_pct_diff,
            winner
            FROM (
                SELECT p1.elo AS p1elo, p2.elo AS p2elo,
                (SELECT count(1) FROM fights 
                    WHERE (p1 = f.p1 AND p2 = f.p2 AND winner = 1)
                    OR    (p2 = f.p1 AND p1 = f.p2 AND winner = 2)
                ) AS p1winsvp2,
                (SELECT count(1) FROM fights 
                    WHERE (p1 = f.p2 AND p2 = f.p1 AND winner = 1) 
                    OR    (p2 = f.p2 AND p1 = f.p1 AND winner = 2)
                ) AS p2winsvp1,
                CAST(p1.wins AS FLOAT) / CAST((p1.wins + p1.losses) AS FLOAT) AS p1winpct,
                CAST(p2.wins AS FLOAT) / CAST((p2.wins + p2.losses) AS FLOAT) AS p2winpct,
                f.winner - 1 AS winner
                FROM fights f
                JOIN fighters p1 ON p1.guid = f.p1
                JOIN fighters p2 ON p2.guid = f.p2
            )
        ''')
        data = result.fetchall()
        log.info('Training data generated: %s' % len(data))
        return data

class OpenSessionError(RuntimeError):
    def __init__(self, message, open_sessions):
        super().__init__(message, open_sessions)
        self.message = message
        self.open_sessions = open_sessions
