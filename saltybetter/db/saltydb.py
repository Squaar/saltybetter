from sqlalchemy import create_engine, desc, Column, ForeignKey
from sqlalchemy import String, Integer, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
import datetime


log = logging.getLogger(__name__)
Base = declarative_base()


# https://www.blog.pythonlibrary.org/2010/09/10/sqlalchemy-connecting-to-pre-existing-databases/
# http://docs.sqlalchemy.org/en/latest/core/reflection.html
# http://docs.sqlalchemy.org/en/latest/orm/tutorial.html
# http://docs.sqlalchemy.org/en/latest/core/type_basics.html#generic-types
'''
fighter_a = aliased(Fighter)
db.session.query(Fight).join(Fighter, Fight.p1==Fighter.guid).join(fighter_a, Fight.p2==fighter_a.guid).first()
'''

class SaltyDB:

    def __init__(self, conn_str, echo=False):
        self.engine = create_engine(conn_str, echo=echo)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def add_ai_logreg_model(self, serialized):
        pass

    def get_best_logreg_model(self, min_bets=0):
        pass

    def add_fight(self, p1name, p2name, winner, mode):
        pass

    def increment_session_wins(self, session_guid):
        pass

    def increment_model_wins(self, model_guid):
        pass

    def increment_session_losses(self, session_guid):
        pass

    def increment_model_losses(self, model_guid):
        pass

    # returns newly created fighter
    def add_fighter(self, name):
        pass

    def get_or_add_fighter(self, name):
        pass

    # fighter can be name or guid
    def get_fighter(self, fighter):
        pass

    def get_fights(self, p1_guid, p2_guid):
        pass

    # get p1's wins against p2. includes where #s reversed
    def get_wins_against(self, p1_guid, p2_guid):
        pass

    def increment_wins(self, fighter_guid, enemy_elo):
        pass

    def increment_losses(self, fighter_guid):
        pass

    def start_session(self, balance):
        pass

    # does nothing if there are no open sessions, ends only the most recent session
    def end_session(self, balance):
        pass

    def get_training_data(self):
        pass


class Fighter(Base):
    __tablename__ = 'fighters'

    guid =      Column(Integer, primary_key=True)
    name =      Column(String, nullable=False, unique=True)
    elo =       Column(Float, nullable=False, default=100)
    wins =      Column(Integer, nullable=False, default=0)
    losses =    Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return '<Fighter ({guid}): {name}>'.format(
            guid = self.guid,
            name = self.name
        )


class Fight(Base):
    __tablename__ = 'fights'

    guid =      Column(Integer, primary_key=True)
    p1 =        Column(Integer, ForeignKey('fighters.guid'), nullable=False)
    p2 =        Column(Integer, ForeignKey('fighters.guid'), nullable=False)
    winner =    Column(Integer, nullable=False)
    time =      Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    mode =      Column(String, nullable=False)

    def __repr__(self):
        return '<Fight ({guid}): {time} - {p1} vs. {p2}>'.format(
            guid =      self.guid,
            time =      self.time,
            p1 =        self.p1,
            p2 =        self.p2,
            winner =    self.winner
        )


class Session(Base):
    __tablename__ = 'sessions'

    guid =          Column(Integer, primary_key=True)
    startTS =       Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    endTS =         Column(DateTime)
    startBalance =  Column(Integer, nullable=False)
    endBalance =    Column(Integer)
    wonBets =       Column(Integer, nullable=False, default=0)  # TODO: can we get rid of won/lost count once bets table is implemented?
    lostBets =      Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return '<Session ({guid}): {start} - {end}>'.format(
            guid =  self.guid,
            start = self.startTS,
            end =   self.endTS
        )


class Bet(Base):
    __tablename__ = 'bets'

    guid =          Column(Integer, primary_key=True)
    fight =         Column(Integer, ForeignKey('fights.guid'), nullable=False)
    session =       Column(Integer, ForeignKey('sessions.guid'), nullable=False)
    # model =       Column(Integer, ForeignKey('ai_logreg_models.guid'), nullable=False)  # TODO: add model column
    amount =        Column(Integer, nullable=False)
    won =           Column(Boolean)
    preBalance =    Column(Integer, nullable=False)
    profit =        Column(Integer)

    def __repr__(self):
        return '<Bet ({guid}): {wonlost} profit: {profit}>'.format(
            guid =      self.guid,
            wonlost =   'won' if self.won else 'lost',
            profit =    self.profit
        )


class AILogregModel(Base):
    __tablename__ = 'ai_logreg_models'

    guid =      Column(Integer, primary_key=True)
    betas =     Column(String, nullable=False)
    wonBets =   Column(Integer, nullable=False, default=0)  # TODO: can we get rid of won/lost count once bets table is implemented?
    lostBets =  Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return '<AILogregModel ({guid}): {winpct}%>'.format(
            guid =      self.guid,
            winpct =    None if self.wonBets + self.lostBets == 0 else self.wonBets / (self.wonBets + self.lostBets) * 100
        )


class OpenSessionError(RuntimeError):
    def __init__(self, message, open_sessions):
        super().__init__(message, open_sessions)
        self.message = message
        self.open_sessions = open_sessions


if __name__ == '__main__':
    db = SaltyDB('sqlite:///salt.db', True)
    pass