"""
GUI smoke test for the Export screen: opens it from the dashboard,
picks a session from the list, patches the native save dialog, and
confirms a real file gets written with the right content.

Run with: python test_export_gui.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_export_gui.db"
if os.path.exists("test_export_gui.db"):
    os.remove("test_export_gui.db")

import pandas as pd  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog  # noqa: E402

QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.models import ReceiptDefinition, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import scan_service  # noqa: E402
from app.views.export_window import ExportWindow  # noqa: E402
from app.controllers.export_controller import ExportController  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

qt_app = QApplication([])
results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()
rd = ReceiptDefinition(
    name="EXPORT_GUI_RECEIPT", status="active",
    template_tokens=[{"type": "literal", "value": "EG-"}, {"type": "placeholder", "name": "SerialNumber"}],
    serial_min=1, serial_max=999999, created_at=datetime.now(timezone.utc),
)
db.add(rd)
db.commit()
db.refresh(rd)

session = scan_service.start_scan_session(
    db, started_by_user_id=user.id, receipt_definition_id=rd.id,
    operator_number="OPX", line_number="LX",
)
scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="EG-1")
scan_service.record_scan_event(db, user_id=user.id, scan_session_id=session.id, scanned_value="EG-2")
session_id = session.id
scan_service.end_scan_session(db, session_id)
db.close()

QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("gui_export_output.csv", "CSV files (*.csv)"))

window = ExportWindow()
controller = ExportController(window)
window.show()

check("Session list is populated", window.sessionList.count() >= 1)

found_row = None
for i in range(window.sessionList.count()):
    if f"#{session_id}" in window.sessionList.item(i).text():
        found_row = i
        break
check("The session we created appears in the list", found_row is not None)

if found_row is not None:
    window.sessionList.setCurrentRow(found_row)

window.formatCombo.setCurrentText("CSV")
window.exportButton.click()

check("Export file was written", os.path.exists("gui_export_output.csv"))
if os.path.exists("gui_export_output.csv"):
    df = pd.read_csv("gui_export_output.csv")
    check("Exported file has 2 rows", len(df) == 2)
    check("Exported file references the right receipt", (df["receipt_name"] == "EXPORT_GUI_RECEIPT").all())
    os.remove("gui_export_output.csv")

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_export_gui.db")
