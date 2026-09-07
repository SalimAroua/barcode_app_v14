"""
Auto-generated batch numbers: YYMMDD + Plain Line # + an ever-incrementing,
per-line running sequence, e.g. "26090712001" for 2026-09-07, line "12",
the 1st batch ever started on that line.

The sequence is scoped to the LINE (Plain Line #), shared across every
receipt run on that line, and never resets - it only ever counts up.
"""
from datetime import datetime

from app.models import LineBatchCounter


def _line_code(plain_line_number: str) -> str:
    """Zero-pads a purely numeric line code to at least 2 digits (e.g.
    "5" -> "05"). A non-numeric or already-longer code is used as-is,
    since the format is meant to accommodate real line-numbering schemes,
    not force every line into exactly 2 digits.
    """
    s = plain_line_number.strip()
    if s.isdigit() and len(s) < 2:
        return s.zfill(2)
    return s


def generate_batch_number(db, plain_line_number: str, now: datetime | None = None) -> str:
    """Atomically increments this line's counter and returns the new
    batch number. Raises ValueError if plain_line_number is missing -
    it's required input for the format, not optional here.
    """
    if not plain_line_number or not plain_line_number.strip():
        raise ValueError(
            "Plain Line # is required to auto-generate a batch number for this receipt."
        )

    now = now or datetime.now()
    plain_line_number = plain_line_number.strip()

    counter = db.query(LineBatchCounter).filter_by(plain_line_number=plain_line_number).first()
    if counter is None:
        counter = LineBatchCounter(plain_line_number=plain_line_number, last_sequence=0)
        db.add(counter)
        db.flush()

    counter.last_sequence += 1
    db.add(counter)
    db.flush()

    date_part = now.strftime("%y%m%d")
    line_part = _line_code(plain_line_number)
    seq_part = f"{counter.last_sequence:03d}"
    return f"{date_part}{line_part}{seq_part}"
