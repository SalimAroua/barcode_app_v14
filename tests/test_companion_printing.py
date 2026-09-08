"""Regression test for printing after a companion label completes a unit."""
import os

os.environ["DATABASE_URL"] = "sqlite:///test_companion_printing.db"
if os.path.exists("test_companion_printing.db"):
    os.remove("test_companion_printing.db")

from datetime import datetime, timezone  # noqa: E402

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service  # noqa: E402


Base.metadata.create_all(engine)
AuthService.create_superuser()

db = SessionLocal()
user = db.query(User).first()
now = datetime.now(timezone.utc)
primary = ReceiptDefinition(
    name="PRINT_PRIMARY", status="active",
    template_tokens=[{"type": "literal", "value": "MAIN-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999, created_at=now,
)
companion = ReceiptDefinition(
    name="PRINT_COMPANION", status="active",
    template_tokens=[{"type": "literal", "value": "COMP-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999, created_at=now,
)
db.add_all([primary, companion])
db.flush()
primary.companion_receipt_id = companion.id
primary.companion_required = True
db.commit()

session = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=primary.id,
    operator_number="OP1", line_number="LINE1", target_quantity=1,
)

original_print = scan_service._print_label
scan_service._print_label = lambda session, receipt: "mocked-companion-label.zpl"
try:
    primary_event, unit = scan_service.record_scan_event(
        db, user_id=user.id, scan_session_id=session.id,
        scanned_value="MAIN-1", expected_receipt="primary",
    )
    assert primary_event.result_ok
    assert primary_event.failure_reason is None
    assert unit is not None and not unit.is_complete

    companion_event, completed_unit = scan_service.record_scan_event(
        db, user_id=user.id, scan_session_id=session.id,
        scanned_value="COMP-1", expected_receipt="companion",
    )
    assert companion_event.result_ok
    assert completed_unit is not None and completed_unit.is_complete
    assert session.printed_label_path == "mocked-companion-label.zpl"
    assert session.is_active is False
finally:
    scan_service._print_label = original_print
    db.close()
    engine.dispose()
    if os.path.exists("test_companion_printing.db"):
        os.remove("test_companion_printing.db")

print("Companion printing regression test passed")