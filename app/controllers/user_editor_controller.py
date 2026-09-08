from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from app.database.session import SessionLocal
from app.services import user_service
from app.services import user_import_service


class UserEditorController:
    def __init__(self, view, acting_user):
        self.view = view
        self.acting_user = acting_user
        self.current_user_id = None  # None => creating a new user

        self._load_user_list()
        self.view.clear_form()

        self.view.userList.currentItemChanged.connect(self.on_select_user)
        self.view.newButton.clicked.connect(self.on_new_user)
        self.view.importCsvButton.clicked.connect(self.on_import_csv)
        self.view.saveButton.clicked.connect(self.on_save)
        self.view.closeButton.clicked.connect(self.view.close)

    def _load_user_list(self):
        db = SessionLocal()
        try:
            users = user_service.list_users(db)
            self.view.set_user_list(users)
        finally:
            db.close()

    def on_select_user(self, current, previous):
        if current is None:
            return
        user_id = current.data(Qt.UserRole)
        db = SessionLocal()
        try:
            u = user_service.get_user(db, user_id)
            if u is None:
                return
            self._load_form_from_user(u)
        finally:
            db.close()

    def _load_form_from_user(self, u):
        self.current_user_id = u.id
        self.view.usernameInput.setText(u.username)
        self.view.usernameInput.setEnabled(False)  # username isn't editable once created
        self.view.fullnameInput.setText(u.fullname or "")
        self.view.employeeIdInput.setText(u.employee_id or "")
        self.view.teamLeaderInput.setText(u.team_leader or "")
        self.view.shiftLeaderInput.setText(u.shift_leader or "")
        idx = self.view.roleCombo.findText(u.role)
        self.view.roleCombo.setCurrentIndex(max(idx, 0))
        self.view.activeCheck.setChecked(bool(u.active))
        self.view.passwordInput.clear()
        self.view.passwordConfirmInput.clear()

    def on_new_user(self):
        self.current_user_id = None
        self.view.userList.clearSelection()
        self.view.clear_form()

    def on_import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.view, "Import Users from CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if not file_path:
            return

        db = SessionLocal()
        try:
            report = user_import_service.import_csv(
                db, file_path, acting_user_id=self.acting_user.id
            )
        except Exception as e:
            self.view.show_error(f"Import failed: {e}")
            return
        finally:
            db.close()

        lines = [
            f"Created: {len(report['created'])}",
            f"Updated: {len(report['updated'])}",
            f"Errors: {len(report['errors'])}",
        ]
        if report["errors"]:
            lines.append("")
            lines.append("Errors:")
            for row_num, username, message in report["errors"][:20]:
                where = f"row {row_num}" if row_num else "import"
                label = f" ({username})" if username else ""
                lines.append(f"  - {where}{label}: {message}")
            if len(report["errors"]) > 20:
                lines.append(f"  ... and {len(report['errors']) - 20} more")

        if report["errors"] and not (report["created"] or report["updated"]):
            self.view.show_error("\n".join(lines))
        else:
            self.view.show_info("\n".join(lines))

        self._load_user_list()

    def on_save(self):
        username = self.view.usernameInput.text().strip()
        fullname = self.view.fullnameInput.text().strip()
        employee_id = self.view.employeeIdInput.text().strip()
        team_leader = self.view.teamLeaderInput.text().strip()
        shift_leader = self.view.shiftLeaderInput.text().strip()
        role = self.view.roleCombo.currentText()
        active = self.view.activeCheck.isChecked()
        password = self.view.passwordInput.text()
        confirm = self.view.passwordConfirmInput.text()

        if password or confirm:
            if password != confirm:
                self.view.show_error("Password and confirmation don't match.")
                return

        db = SessionLocal()
        try:
            if self.current_user_id is None:
                if not username:
                    self.view.show_error("Username is required.")
                    return
                if not password:
                    self.view.show_error("Password is required for a new user.")
                    return
                user_service.create_user(
                    db, username=username, fullname=fullname,
                        password=password, role=role, active=active,
                        employee_id=employee_id, team_leader=team_leader,
                        shift_leader=shift_leader,
                )
                self.view.show_info(f"User '{username}' created.")
            else:
                user_service.update_user(
                    db, self.current_user_id,
                    fullname=fullname, role=role, active=active,
                    employee_id=employee_id, team_leader=team_leader,
                    shift_leader=shift_leader,
                    acting_user_id=self.acting_user.id,
                )
                if password:
                    user_service.reset_password(db, self.current_user_id, password)
                self.view.show_info(f"User '{username}' saved.")
        except ValueError as e:
            self.view.show_error(str(e))
            return
        finally:
            db.close()

        self._load_user_list()
