from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from app.database.session import SessionLocal
from app.services import receipt_def_service, scan_service
from app.views.scan_window import ScanWindow
from app.controllers.scan_controller import ScanController
from app.views.receipt_editor_window import ReceiptEditorWindow
from app.controllers.receipt_editor_controller import ReceiptEditorController
from app.views.user_editor_window import UserEditorWindow
from app.controllers.user_editor_controller import UserEditorController
from app.views.export_window import ExportWindow
from app.controllers.export_controller import ExportController
from app.views.printer_settings_window import PrinterSettingsWindow
from app.controllers.printer_settings_controller import PrinterSettingsController


class DashboardController:
    def __init__(self, view, user):
        self.view = view
        self.user = user
        self._scan_window = None  # keep a reference so it isn't garbage-collected
        self._scan_controller = None
        self._receipt_editor_window = None
        self._receipt_editor_controller = None
        self._user_editor_window = None
        self._user_editor_controller = None
        self._export_window = None
        self._export_controller = None
        self._printer_settings_window = None
        self._printer_settings_controller = None

        self._load_receipts()
        self.view.receiptNameInput.textChanged.connect(self.on_receipt_selection_changed)

        self.view.startSessionButton.clicked.connect(self.on_start_session)
        self.view.logoutButton.clicked.connect(self.view.close)

        if hasattr(self.view, "manageReceiptsButton"):
            self.view.manageReceiptsButton.clicked.connect(self.on_manage_receipts)
        if hasattr(self.view, "manageUsersButton"):
            self.view.manageUsersButton.clicked.connect(self.on_manage_users)
        if hasattr(self.view, "exportButton"):
            self.view.exportButton.clicked.connect(self.on_export)
        if hasattr(self.view, "printerSettingsButton"):
            self.view.printerSettingsButton.clicked.connect(self.on_printer_settings)

    def on_not_implemented(self):
        self.view.show_info("This screen isn't built yet - coming soon.")

    def on_export(self):
        self._export_window = ExportWindow()
        self._export_controller = ExportController(self._export_window)
        self._export_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._export_window.showMaximized()

    def on_printer_settings(self):
        self._printer_settings_window = PrinterSettingsWindow()
        self._printer_settings_controller = PrinterSettingsController(self._printer_settings_window)
        self._printer_settings_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._printer_settings_window.showMaximized()

    def on_manage_receipts(self):
        self._receipt_editor_window = ReceiptEditorWindow()
        self._receipt_editor_controller = ReceiptEditorController(self._receipt_editor_window, self.user)
        self._receipt_editor_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._receipt_editor_window.destroyed.connect(lambda: self._load_receipts())
        self._receipt_editor_window.showMaximized()

    def on_manage_users(self):
        self._user_editor_window = UserEditorWindow()
        self._user_editor_controller = UserEditorController(self._user_editor_window, self.user)
        self._user_editor_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self._user_editor_window.showMaximized()

    def _load_receipts(self):
        db = SessionLocal()
        try:
            receipts = receipt_def_service.list_active_receipts(db)
            self._receipt_auto_batch = {r.id: bool(r.auto_generate_batch_number) for r in receipts}
        finally:
            db.close()
        self.on_receipt_selection_changed()

    def on_receipt_selection_changed(self, *_args):
        receipt_name = self.view.receiptNameInput.text().strip()
        if not receipt_name:
            self.view.set_batch_auto_generated(False)
            return

        db = SessionLocal()
        try:
            receipt = receipt_def_service.get_receipt_by_name(db, receipt_name)
            auto = bool(receipt and receipt.auto_generate_batch_number)
        finally:
            db.close()
        self.view.set_batch_auto_generated(auto)

    def on_start_session(self):
        receipt_name = self.view.receiptNameInput.text().strip()
        if not receipt_name:
            self.view.show_error("Receipt name is required to start a session.")
            return

        operator_number = self.view.operatorNumberInput.text().strip()
        line_number = self.view.lineNumberInput.text().strip()
        plain_line_number = self.view.plainLineNumberInput.text().strip()
        operators = self.view.operatorsInput.text().strip() or None
        batch_label = self.view.batchLabelInput.text().strip()
        target_text = self.view.targetQuantityInput.text().strip()

        if not operator_number or not line_number:
            self.view.show_error("Operator # and Line are required to start a session.")
            return
        if target_text and not target_text.isdigit():
            self.view.show_error("Target quantity must be a positive whole number.")
            return

        target_quantity = int(target_text) if target_text else None

        db = SessionLocal()
        try:
            receipt = receipt_def_service.get_receipt_by_name(db, receipt_name)
            if receipt is None:
                self.view.show_error(f"No active receipt named '{receipt_name}' was found.")
                return

            session = scan_service.start_scan_session(
                db,
                started_by_user_id=self.user.id,
                receipt_definition_id=receipt.id,
                operator_number=operator_number,
                line_number=line_number,
                plain_line_number=plain_line_number or None,
                batch_label=batch_label or None,
                operators=operators,
                target_quantity=target_quantity,
            )
            session_id = session.id
        except ValueError as e:
            self.view.show_error(str(e))
            return
        finally:
            db.close()

        self._scan_window = ScanWindow(session, receipt_name)
        self._scan_controller = ScanController(self._scan_window, self.user, session_id)
        self._scan_window.showMaximized()
