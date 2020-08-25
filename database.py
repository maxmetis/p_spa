from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import os

from sqlalchemy_utils import database_exists

current_dir = os.path.dirname(__file__)

db_path = os.environ['DATABASE_URL']

engine = create_engine(db_path, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    engine.connect()

    if engine.dialect.has_table(engine, 'products'):
        return False
    else:
        Base.metadata.create_all(engine)
        return True
