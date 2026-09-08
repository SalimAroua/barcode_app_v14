from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from app.database.database import Base


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    username = Column(String(50), unique=True, nullable=False)

    fullname = Column(String(100))

    employee_id = Column(String(50))

    team_leader = Column(String(100))

    shift_leader = Column(String(100))

    password_hash = Column(String(255), nullable=False)

    role = Column(String(20), nullable=False)

    active = Column(Boolean, default=True)