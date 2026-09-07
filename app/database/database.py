from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

import config

engine = create_engine(
    config.DATABASE_URL,
    echo=config.SQL_ECHO,
    future=True
)


class Base(DeclarativeBase):
    pass