from sqlalchemy.orm import sessionmaker

from .database import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)   