from sqlalchemy import Column, Integer, String

from app.database.database import Base


class LineBatchCounter(Base):
    """One row per production line, tracking the last batch sequence
    number used on that line. Scoped to the line (Plain Line #), shared
    across every receipt run on that line - never resets.

    Used only when a ReceiptDefinition has auto_generate_batch_number
    turned on; see app/services/batch_numbering_service.py.
    """

    __tablename__ = "line_batch_counters"

    id = Column(Integer, primary_key=True)
    plain_line_number = Column(String(50), unique=True, nullable=False)
    last_sequence = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<LineBatchCounter line={self.plain_line_number!r} last_sequence={self.last_sequence}>"
