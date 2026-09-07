from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ScanSession(Base):
    """One working session at a station: operator + line + batch, tied to
    a single active ReceiptDefinition. LineNumber/OpNumber placeholders
    resolve from here.
    """

    __tablename__ = "scan_sessions"

    id = Column(Integer, primary_key=True)

    receipt_definition_id = Column(Integer, ForeignKey("receipt_definitions.id"), nullable=False)
    receipt_definition = relationship("ReceiptDefinition")

    started_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    operator_number = Column(String(50), nullable=False)
    line_number = Column(String(50), nullable=False)
    plain_line_number = Column(String(50))
    batch_label = Column(String(100))

    started_at = Column(DateTime, default=_utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<ScanSession id={self.id} line={self.line_number!r} active={self.is_active}>"
