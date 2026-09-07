from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
)
from sqlalchemy.orm import relationship

from app.database.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ScanEvent(Base):
    """A single scan attempt (pass or fail), always logged - even failures -
    so the full history is auditable.
    """

    __tablename__ = "scan_events"

    id = Column(Integer, primary_key=True)

    scan_session_id = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)
    receipt_definition_id = Column(Integer, ForeignKey("receipt_definitions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    sequence_no = Column(Integer, nullable=False)
    scanned_value = Column(String(500), nullable=False)

    result_ok = Column(Boolean, nullable=False)
    failure_reason = Column(String(50), nullable=True)  # e.g. FieldMismatch, SerialOutOfRange, TrailingData
    details_json = Column(JSON, nullable=True)  # extracted field values, matched span, etc.

    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        status = "OK" if self.result_ok else f"FAIL:{self.failure_reason}"
        return f"<ScanEvent id={self.id} {status} value={self.scanned_value!r}>"


class ScanUnit(Base):
    """Tracks primary+companion label pairing for a single physical unit.
    Opened by a primary scan, completed by the matching companion scan.
    """

    __tablename__ = "scan_units"

    id = Column(Integer, primary_key=True)
    scan_session_id = Column(Integer, ForeignKey("scan_sessions.id"), nullable=False)

    primary_event_id = Column(Integer, ForeignKey("scan_events.id"), nullable=False)
    companion_event_id = Column(Integer, ForeignKey("scan_events.id"), nullable=True)

    is_complete = Column(Boolean, default=False)
    opened_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    primary_event = relationship("ScanEvent", foreign_keys=[primary_event_id])
    companion_event = relationship("ScanEvent", foreign_keys=[companion_event_id])

    def __repr__(self):
        return f"<ScanUnit id={self.id} complete={self.is_complete}>"
