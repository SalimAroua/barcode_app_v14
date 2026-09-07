from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
)
from sqlalchemy.orm import relationship

from app.database.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ReceiptDefinition(Base):
    """A label template: an ordered list of tokens (literal / placeholder /
    regex) plus the fixed field values those placeholders resolve from.

    template_tokens is a JSON list of dicts, e.g.:
        [
            {"type": "literal", "value": "PN-"},
            {"type": "placeholder", "name": "PartNumber"},
            {"type": "literal", "value": "-SN"},
            {"type": "placeholder", "name": "SerialNumber"},
        ]
        {"type": "regex", "name": "MyField", "pattern": "[A-Z]{2}\\d{3}"}
    """

    __tablename__ = "receipt_definitions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft | active | retired

    template_tokens = Column(JSON, nullable=False, default=list)

    # ---- Fixed fields a Placeholder can resolve from ----
    part_number = Column(String(100))
    customer_part_number = Column(String(100))
    part_description1 = Column(String(200))
    part_description2 = Column(String(200))
    drawing_number = Column(String(100))
    drawing_date_text = Column(String(50))
    manuf_code = Column(String(50))
    ka_revision_level = Column(String(20))
    generation_status = Column(String(20))
    product_designation = Column(String(100))  # new field, per your reference label
    duns = Column(String(20))
    bg_nr = Column(String(20))
    quantity_text = Column(String(20))

    # ---- SerialNumber bounds (replaces the old fixed-width rule) ----
    serial_min = Column(Integer, nullable=True)
    serial_max = Column(Integer, nullable=True)

    # ---- Timestamp policy ----
    timestamp_policy = Column(String(30), nullable=False, default="use_scan_time")  # use_scan_time | freeze_on_receipt_def
    frozen_timestamp = Column(DateTime, nullable=True)

    # ---- Companion label pairing ----
    companion_receipt_id = Column(Integer, ForeignKey("receipt_definitions.id"), nullable=True)
    companion_required = Column(Boolean, default=False)
    companion_of = relationship("ReceiptDefinition", remote_side=[id])

    # ---- Duplicate-scan prevention ----
    # When True, a scanned value that already has a PASSED ScanEvent for
    # this receipt (any session, any time) is rejected as a duplicate.
    # The duplicate attempt is still recorded as a failed ScanEvent for
    # traceability - it just doesn't count as a valid pass.
    prevent_duplicate_scans = Column(Boolean, nullable=False, default=False)

    # ---- Batch number auto-generation ----
    # When True, the operator-entered Batch field is ignored at session
    # start and a batch number is generated automatically instead:
    # YYMMDD + Plain Line # + an ever-incrementing per-line sequence
    # (e.g. 26090712001). See app/services/batch_numbering_service.py.
    auto_generate_batch_number = Column(Boolean, nullable=False, default=False)

    # ---- Workflow defaults ----
    # Optional local .txt label template used for printing.
    template_file_path = Column(String(500), nullable=True)

    # Number of successful units required to complete a session.
    target_quantity = Column(Integer, nullable=True)

    notes = Column(String(500))
    created_at = Column(DateTime, default=_utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    def __repr__(self):
        return f"<ReceiptDefinition {self.name!r} status={self.status!r}>"
