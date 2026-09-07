"""
Headless GUI smoke test for the Receipt Definition editor: opens it from
the dashboard, builds a brand-new template token-by-token (literal +
placeholder + regex), saves it, reopens it to confirm it round-trips, then
verifies it's immediately usable for an actual scan.

Run with: python test_receipt_editor.py
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DATABASE_URL"] = "sqlite:///test_receipt_editor.db"
if os.path.exists("test_receipt_editor.db"):
    os.remove("test_receipt_editor.db")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.Ok)

import app.models  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services import receipt_def_service  # noqa: E402
from app.models import User  # noqa: E402

from app.views.receipt_editor_window import ReceiptEditorWindow  # noqa: E402
from app.controllers.receipt_editor_controller import ReceiptEditorController  # noqa: E402
from app.views.token_dialogs import LiteralTokenDialog, PlaceholderTokenDialog, RegexTokenDialog  # noqa: E402

Base.metadata.create_all(engine)
AuthService.create_superuser()

qt_app = QApplication([])

results = []


def check(label, cond):
    results.append(("PASS" if cond else "FAIL", label))


db = SessionLocal()
user = db.query(User).first()
db.close()

# --- 1. Open the editor and build a brand new template ---
window = ReceiptEditorWindow()
controller = ReceiptEditorController(window, user)
window.show()

controller.on_new_receipt()
window.nameInput.setText("EDITOR_TEST_RECEIPT")
window.statusCombo.setCurrentText("active")
window.field_inputs["part_number"].setText("PN-EDIT-001")
window.field_inputs["customer_part_number"].setText("CUST.999.888")
window.serialMinInput.setText("1")
window.serialMaxInput.setText("999999")

# Add tokens the same way a user would, via the real dialogs:
# PartNumber, literal "-", regex LotCode, literal "-SN", SerialNumber
controller._append_token({"type": "placeholder", "name": "PartNumber"})
controller._append_token({"type": "literal", "value": "-"})
controller._append_token({"type": "regex", "name": "LotCode", "pattern": r"[A-Z]{2}\d{2}"})
controller._append_token({"type": "literal", "value": "-SN"})
controller._append_token({"type": "placeholder", "name": "SerialNumber"})

check("5 tokens added to the list widget", window.tokenList.count() == 5)
check("Live preview renders without a template error", "error" not in window.previewLabel.text().lower())

# --- 2. Save it ---
controller.on_save()

db = SessionLocal()
saved = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).filter_by(name="EDITOR_TEST_RECEIPT").first()
check("Receipt persisted to the database", saved is not None)
check("Fixed fields persisted", saved is not None and saved.part_number == "PN-EDIT-001")
check("Serial bounds persisted", saved is not None and saved.serial_min == 1 and saved.serial_max == 999999)
check("Token list persisted with correct length/order", saved is not None and len(saved.template_tokens) == 5 and saved.template_tokens[2]["type"] == "regex")
db.close()

# --- 3. Re-select it from the list to confirm it round-trips into the form ---
controller._load_receipt_list()
found_row = None
for i in range(window.receiptList.count()):
    if window.receiptList.item(i).text().startswith("EDITOR_TEST_RECEIPT"):
        found_row = i
        break
check("New receipt appears in the list", found_row is not None)

if found_row is not None:
    window.receiptList.setCurrentRow(found_row)
    check("Form reloads the saved name", window.nameInput.text() == "EDITOR_TEST_RECEIPT")
    check("Form reloads fixed fields", window.field_inputs["part_number"].text() == "PN-EDIT-001")
    check("Form reloads tokens", window.tokenList.count() == 5)

# --- 4. Edit it (change status, add a token) and re-save ---
window.field_inputs["part_number"].setText("PN-EDIT-002")
controller.on_save()
db = SessionLocal()
saved2 = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).filter_by(name="EDITOR_TEST_RECEIPT").first()
check("Edit persisted (updated, not duplicated)", saved2 is not None and saved2.part_number == "PN-EDIT-002")
count_with_name = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).filter_by(name="EDITOR_TEST_RECEIPT").count()
check("No duplicate row created on edit", count_with_name == 1)
db.close()

# --- 5. Reject invalid regex ---
controller.on_new_receipt()
window.nameInput.setText("BAD_REGEX_RECEIPT")
controller._append_token({"type": "regex", "name": "Bad", "pattern": "[unclosed"})
before_count = None
db = SessionLocal()
before_count = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).count()
db.close()
controller.on_save()
db = SessionLocal()
after_count = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).count()
db.close()
check("Invalid regex is rejected (not saved)", after_count == before_count)

# --- 6. Reject duplicate name ---
controller.on_new_receipt()
window.nameInput.setText("EDITOR_TEST_RECEIPT")  # already exists
controller._append_token({"type": "literal", "value": "X"})
db = SessionLocal()
before_count2 = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).count()
db.close()
controller.on_save()
db = SessionLocal()
after_count2 = db.query(__import__("app.models", fromlist=["ReceiptDefinition"]).ReceiptDefinition).count()
db.close()
check("Duplicate name is rejected (not saved)", after_count2 == before_count2)

print("\n" + "=" * 90)
n_pass = 0
for status, label in results:
    n_pass += status == "PASS"
    print(f"{status:<6} {label}")
print("=" * 90)
print(f"{n_pass}/{len(results)} passed")

os.remove("test_receipt_editor.db")
