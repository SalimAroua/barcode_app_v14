"""
Full integration test against a real (temporary) SQLite DB: creates
tables, seeds a SuperUser, creates receipts, runs a scan session with
primary/companion pairing.

Run with: python test_integration.py
"""
import os

# Point at a throwaway DB before importing anything that touches config/engine
os.environ["DATABASE_URL"] = "sqlite:///test_integration.db"

from datetime import datetime, timezone  # noqa: E402

import app.models  # noqa: E402  (registers all models on Base)
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service  # noqa: E402
from app.domain.exceptions import IncompletePairError  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results = []


def record(label, ok, info=""):
    results.append((PASS if ok else FAIL, label, info))


def main():
    if os.path.exists("test_integration.db"):
        os.remove("test_integration.db")
    Base.metadata.create_all(engine)
    AuthService.create_superuser()

    db = SessionLocal()
    try:
        user = db.query(User).first()
        record("Seeded SuperUser exists", user is not None and user.role == "SuperUser")

        now = datetime.now(timezone.utc)
        primary = ReceiptDefinition(
            name="IT_PRIMARY", status="active",
            template_tokens=[{"type": "literal", "value": "MAIN-"}, {"type": "placeholder", "name": "SerialNumber"}],
            serial_min=1, serial_max=9_999_999, created_at=now, created_by_user_id=user.id,
        )
        db.add(primary)
        db.flush()

        companion = ReceiptDefinition(
            name="IT_COMPANION", status="active",
            template_tokens=[{"type": "literal", "value": "COMP-"}, {"type": "placeholder", "name": "SerialNumber"}],
            serial_min=1, serial_max=9_999_999, created_at=now, created_by_user_id=user.id,
        )
        db.add(companion)
        db.flush()

        primary.companion_receipt_id = companion.id
        primary.companion_required = True
        db.add(primary)
        db.flush()

        session = scan_service.start_scan_session(
            db, started_by_user_id=user.id, receipt_definition_id=primary.id,
            operator_number="OP01", line_number="FAWL01", plain_line_number="01", batch_label="BATCH-A",
        )
        record("Session started", session.is_active is True)

        ev1, unit1 = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="MAIN-1")
        record("Primary scan opens incomplete unit", ev1.result_ok and unit1 is not None and not unit1.is_complete)

        blocked = False
        try:
            scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="MAIN-2")
        except IncompletePairError:
            blocked = True
        record("Second primary blocked until companion scanned", blocked)

        ev2, unit2 = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="COMP-1")
        record("Companion scan completes the unit", ev2.result_ok and unit2 is not None and unit2.id == unit1.id and unit2.is_complete)

        ev3, unit3 = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="COMP-99")
        record("Orphan companion scan rejected", (not ev3.result_ok) and ev3.failure_reason == "CompanionWithoutPrimary")

        ev4, unit4 = scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="MAIN-2")
        record("Primary scan works again after unit closed", ev4.result_ok and unit4 is not None and not unit4.is_complete)

        scan_service.end_scan_session(db, session.id)
        record("Session ends cleanly", True)
    finally:
        db.close()

    print("\n" + "=" * 90)
    n_pass = 0
    for status, label, info in results:
        n_pass += status == PASS
        print(f"{status:<6} {label}")
        if status == FAIL and info:
            print(f"       -> {info}")
    print("=" * 90)
    print(f"{n_pass}/{len(results)} passed")


if __name__ == "__main__":
    main()
