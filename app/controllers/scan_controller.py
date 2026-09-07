from PySide6.QtWidgets import QMessageBox

from app.database.session import SessionLocal
from app.domain.exceptions import IncompletePairError, TemplateError
from app.services import scan_service


class ScanController:
    def __init__(self, view, user, scan_session_id):
        self.view = view
        self.user = user
        self.scan_session_id = scan_session_id

        self.view.scanInput.returnPressed.connect(self.on_scan)
        self.view.endSessionButton.clicked.connect(self.on_end_session)

    def on_scan(self):
        scanned_value = self.view.scanInput.text().strip()
        if not scanned_value:
            return

        db = SessionLocal()
        try:
            try:
                event, unit = scan_service.record_scan_event(
                    db,
                    user_id=self.user.id,
                    scan_session_id=self.scan_session_id,
                    scanned_value=scanned_value,
                )
            except IncompletePairError:
                self.view.show_result(False, "IncompletePair")
                self.view.add_log_entry(scanned_value, False, "IncompletePair - scan the companion label first")
                self.view.clear_input()
                return
            except TemplateError as e:
                QMessageBox.critical(self.view, "Template error", str(e))
                self.view.clear_input()
                return

            unit_info = ""
            if unit is not None:
                unit_info = "(unit complete)" if unit.is_complete else "(waiting for companion)"

            self.view.show_result(event.result_ok, event.failure_reason)
            self.view.add_log_entry(scanned_value, event.result_ok, event.failure_reason, unit_info)
            self.view.clear_input()
        finally:
            db.close()

    def on_end_session(self):
        db = SessionLocal()
        try:
            scan_service.end_scan_session(db, self.scan_session_id)
        finally:
            db.close()
        self.view.close()
