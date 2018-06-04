from sqlalchemy import create_engine, desc, case, cast, func, or_, and_, Column, ForeignKey
from sqlalchemy import String, Integer, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import sessionmaker, aliased
import logging
import datetime


log = logging.getLogger(__name__)
Base = declarative_base()


# https://www.blog.pythonlibrary.org/2010/09/10/sqlalchemy-connecting-to-pre-existing-databases/
# http://docs.sqlalchemy.org/en/latest/core/reflection.html
# http://docs.sqlalchemy.org/en/latest/orm/tutorial.html
# http://docs.sqlalchemy.org/en/latest/core/type_basics.html#generic-types


# noinspection PyPep8
class SaltyDB:

    def __init__(self, conn_str, elo_stake=0.05, echo=False):
        self.elo_stake = elo_stake
        self.engine = create_engine(conn_str, echo=echo)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def add_ai_logreg_model(self, serialized):
        new_model = AILogregModel(betas=serialized)
        self.session.add(new_model)
        self.session.commit()
        log.info('Saved LogReg model: %s' % new_model)
        return new_model  # this might have issues with threads

    def get_best_logreg_model(self, min_bets=0):
        q = self.session.query(AILogregModel)
        q = q.filter(AILogregModel.won_bets + AILogregModel.lost_bets >= min_bets)
        q = q.order_by(desc(AILogregModel.won_bets_pct))
        return q.first()

    def add_fight(self, p1name, p2name, winner, mode):
        if p1name == p2name:
            log.warning('Self fight detected. Ignoring. %s' % p1name)
            return

        p1 = self.get_or_add_fighter(p1name)
        p2 = self.get_or_add_fighter(p2name)

        if winner == 1:
            self.increment_wins(p1.guid, p2.elo if p2 else 0)
            self.increment_losses(p2.guid)
        elif winner == 2:
            self.increment_losses(p1.guid)
            self.increment_wins(p2.guid, p1.elo if p1 else 0)
        else:
            raise RuntimeError("Winner must be in [1, 2]: %s" % winner)

        new_fight = Fight(p1=p1.guid, p2=p2.guid, winner=winner, mode=mode)
        self.session.add(new_fight)
        self.session.commit()
        log.info('Fight recorded %s' % new_fight)
        return new_fight.guid  # TODO: return whole fight

    # TODO: refactor to not need this - just keep the session object and update
    def increment_session_wins(self, session_guid):
        session = self.session.query(Session).filter(Session.guid == session_guid).first()
        session.won_bets += 1
        self.session.commit()

    def increment_model_wins(self, model_guid):
        model = self.session.query(AILogregModel).filter(AILogregModel.guid == model_guid).first()
        model.won_bets += 1
        self.session.commit()

    def increment_session_losses(self, session_guid):
        session = self.session.query(Session).filter(Session.guid == session_guid).first()
        session.lost_bets += 1
        self.session.commit()

    def increment_model_losses(self, model_guid):
        model = self.session.query(AILogregModel).filter(AILogregModel.guid == model_guid).first()
        model.lost_bets += 1
        self.session.commit()

    # returns newly created fighter
    def add_fighter(self, name):
        new_fighter = Fighter(name=name)
        self.session.add(new_fighter)
        self.session.commit()
        log.info('Fighter added %s' % new_fighter)
        return new_fighter

    def get_or_add_fighter(self, name):
        fighter = self.get_fighter_by_name(name)
        if not fighter:
            fighter = self.add_fighter(name)
        return fighter

    # fighter can be name or guid

    def get_fighter_by_guid(self, guid):
        fighter = self.session.query(Fighter).filter(Fighter.guid == guid).first()
        return fighter

    def get_fighter_by_name(self, name):
        fighter = self.session.query(Fighter).filter(Fighter.name == name).first()
        return fighter

    # def get_fights(self, p1_guid, p2_guid):
    #     fighters = [p1_guid, p2_guid]
    #     fights = self.session.query(Fight).filter(Fight.p1 in fighters and Fight.p2 in fighters).all()
    #     return fights

    def get_fights(self, guid):
        fights = self.session.query(Fight).filter(or_(Fight.p1 == guid, Fight.p2 == guid)).all()
        return fights

    # get p1's wins against p2. includes where #s reversed
    # TODO: refactor to just return the number instead of full list (get_n_wins_against)
    def get_wins_against(self, p1_guid, p2_guid):
        wins = self.session.query(Fight).filter(or_(
            and_(Fight.p1 == p1_guid, Fight.p2 == p2_guid, Fight.winner == 1),
            and_(Fight.p1 == p2_guid, Fight.p2 == p1_guid, Fight.winner == 2)
        )).all()
        return wins

    def increment_wins(self, fighter_guid, enemy_elo):
        fighter = self.get_fighter_by_guid(fighter_guid)
        fighter.wins += 1
        fighter.elo = fighter.elo + (self.elo_stake * enemy_elo)
        self.session.commit()
        log.info('Incremented wins: %s' % fighter)

    def increment_losses(self, fighter_guid):
        fighter = self.get_fighter_by_guid(fighter_guid)
        fighter.losses += 1
        fighter.elo = fighter.elo - (self.elo_stake * fighter.elo)
        self.session.commit()
        log.info('Incremented losses: %s' % fighter)

    def start_session(self, balance):
        if balance is None:
            raise TypeError('Balance cannot be None')
        open_sessions = self.session.query(Session).filter(Session.end_ts == None).all()
        if len(open_sessions) > 0:
            raise OpenSessionError('A session is already open!', len(open_sessions))

        new_session = Session(start_balance=balance)
        self.session.add(new_session)
        self.session.commit()
        log.info('Session started: %s' % new_session)
        return new_session

    # does nothing if there are no open sessions, ends only the most recent session
    def end_session(self, balance):
        if balance is None:
            raise TypeError('Balance cannot be None')

        open_sessions = self.session.query(Session).filter(Session.end_ts == None).all()
        last_fight = self.session.query(func.max(Fight.time)).first()
        last_fight = last_fight[0] if last_fight else datetime.datetime.utcnow()
        for session in open_sessions:
            session.end_ts = last_fight
            session.end_balance = balance
        self.session.commit()
        if len(open_sessions) == 0:
            log.info('No sessions to close')
        if len(open_sessions) > 1:
            log.warning('More than one session closed: %s' % [session.guid for session in open_sessions])

        last_session_guid = self.session.query(func.max(Session.guid)).subquery()
        last_session = self.session.query(Session).filter(Session.guid == last_session_guid).first()
        return last_session

    # TODO: this is causing oom errors in the kernel :(
    # only need p1elo, p2elo, p1winsvp2, p2winsvp1, p1winpct, p2winpct, winner
    def get_training_data(self, test_mode=False, test_limit=100):
        log.info('Generating training data, this may take a while...')
        f = aliased(Fight, name='f')
        p1 = aliased(Fighter, name='p1')
        p2 = aliased(Fighter, name='p2')
        p1winsvp2 = self.session.query(func.count(1)).filter(or_(
            and_(Fight.p1 == f.p1, Fight.p2 == f.p2, Fight.winner == 1),
            and_(Fight.p1 == f.p2, Fight.p2 == f.p1, Fight.winner == 2)
        )).label('p1winsvp2')
        p2winsvp1 = self.session.query(func.count(1)).filter(or_(
            and_(Fight.p1 == f.p1, Fight.p2 == f.p2, Fight.winner == 2),
            and_(Fight.p1 == f.p2, Fight.p2 == f.p1, Fight.winner == 1)
        )).label('p2winsvp1')

        fights = self.session.query(f.winner, p1.elo, p2.elo, p1winsvp2, p2winsvp1, p1.winpct, p2.winpct)
        fights = fights.join(p1, f.p1==p1.guid).join(p2, f.p2==p2.guid)
        if test_mode:
            fights = fights.limit(test_limit)
        return [{
            'elo_diff': p1elo - p2elo,
            'wins_diff': p1winsvp2 - p2winsvp1,
            'win_pct_diff': p1winpct - p2winpct,
            'winner': winner - 1  # -1 to put in range [0,1]
        } for winner, p1elo, p2elo, p1winsvp2, p2winsvp1, p1winpct, p2winpct in fights.all()]


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

    @hybrid_property
    def winpct(self):
        if self.wins + self.losses == 0:
            return 50.0
        # noinspection PyTypeChecker
        return float(self.wins) / (self.wins + self.losses) * 100

    @winpct.expression
    def winpct(self):
        return case(
            [(self.wins + self.losses == 0, 50.0)],
            else_ =cast(self.wins, Float) / (self.wins + self.losses) * 100
        )


class Fight(Base):
    __tablename__ = 'fights'

    guid =      Column(Integer, primary_key=True)
    p1 =        Column(Integer, ForeignKey('fighters.guid'), nullable=False)
    p2 =        Column(Integer, ForeignKey('fighters.guid'), nullable=False)
    winner =    Column(Integer, nullable=False)
    time =      Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    mode =      Column(String)

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
    start_ts =       Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    end_ts =         Column(DateTime)
    start_balance =  Column(Integer, nullable=False)
    end_balance =    Column(Integer)
    won_bets =       Column(Integer, nullable=False, default=0)  # TODO: can we get rid of won/lost count once bets table is implemented?
    lost_bets =      Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return '<Session ({guid}): {start} - {end}>'.format(
            guid =  self.guid,
            start = self.start_ts,
            end =   self.end_ts
        )


class Bet(Base):
    __tablename__ = 'bets'

    guid =          Column(Integer, primary_key=True)
    fight =         Column(Integer, ForeignKey('fights.guid'), nullable=False)
    session =       Column(Integer, ForeignKey('sessions.guid'), nullable=False)
    # model =       Column(Integer, ForeignKey('ai_logreg_models.guid'), nullable=False)  # TODO: add model column
    # on =            Column(Integer, ForeignKey('fighters.guid'), nullable=False)  # TODO: add on column
    amount =        Column(Integer, nullable=False)
    won =           Column(Boolean)
    pre_balance =    Column(Integer, nullable=False)
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
    won_bets =   Column(Integer, nullable=False, default=0)  # TODO: can we get rid of won/lost count once bets table is implemented?
    lost_bets =  Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return '<AILogregModel ({guid}): {nfights} - {winpct}%>'.format(
            guid =      self.guid,
            nfights =   self.won_bets + self.lost_bets,
            winpct =    None if self.won_bets + self.lost_bets == 0 else self.won_bets / (self.won_bets + self.lost_bets) * 100
        )

    @hybrid_property
    def won_bets_pct(self):
        if self.won_bets + self.lost_bets == 0:
            return 0.0
        # noinspection PyTypeChecker
        return float(self.won_bets) / (self.won_bets + self.lost_bets) * 100.0

    # TODO: this doesn't work
    @won_bets_pct.expression
    def won_bets_pct(self):
        return case(
            [(self.won_bets + self.lost_bets == 0, 0.0)],
            else_ =cast(self.won_bets, Float) / (self.won_bets + self.lost_bets) * 100.0
        )


class OpenSessionError(RuntimeError):
    def __init__(self, message, open_sessions):
        super().__init__(message, open_sessions)
        self.message = message
        self.open_sessions = open_sessions


if __name__ == '__main__':
    db = SaltyDB('sqlite:///salt.db', True)
    db.get_training_data(True)
    pass
