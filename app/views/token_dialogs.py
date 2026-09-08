from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QDialogButtonBox
)

from app.domain.template_engine import FIXED_FIELD_MAP, SESSION_FIELD_MAP
from app.views.window_utils import enable_maximize, set_app_icon

# Placeholder names offered in the "Add Placeholder" dropdown, grouped for
# clarity. DT:<format> is handled by its own dialog since it needs a
# format string, not just a name.
FIXED_PLACEHOLDER_NAMES = list(FIXED_FIELD_MAP.keys()) + ["CustomerPartNumberNoDot"]
SESSION_PLACEHOLDER_NAMES = list(SESSION_FIELD_MAP.keys())
COMPUTED_PLACEHOLDER_NAMES = ["Date", "Time"]
SERIAL_PLACEHOLDER_NAME = "SerialNumber"

ALL_SIMPLE_PLACEHOLDER_NAMES = (
    FIXED_PLACEHOLDER_NAMES + SESSION_PLACEHOLDER_NAMES
    + COMPUTED_PLACEHOLDER_NAMES + [SERIAL_PLACEHOLDER_NAME]
)


class LiteralTokenDialog(QDialog):
    """Add a fixed literal piece of text, e.g. '-' or 'SN'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        enable_maximize(self)
        set_app_icon(self)
        self.setWindowTitle("Add Literal Text")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Exact text this token must match:"))
        self.valueInput = QLineEdit()
        layout.addWidget(self.valueInput)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def token(self):
        return {"type": "literal", "value": self.valueInput.text()}


class PlaceholderTokenDialog(QDialog):
    """Add a named placeholder (fixed field, session field, Date/Time,
    SerialNumber, or a custom DT:<format>)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        enable_maximize(self)
        set_app_icon(self)
        self.setWindowTitle("Add Placeholder")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Placeholder:"))
        self.combo = QComboBox()
        self.combo.addItems(ALL_SIMPLE_PLACEHOLDER_NAMES + ["DT:<custom format>"])
        layout.addWidget(self.combo)

        self.dtFormatRow = QHBoxLayout()
        self.dtFormatRow.addWidget(QLabel("Format (e.g. yyyyMMdd):"))
        self.dtFormatInput = QLineEdit()
        self.dtFormatRow.addWidget(self.dtFormatInput)
        layout.addLayout(self.dtFormatRow)
        self._set_dt_row_visible(False)
        self.combo.currentTextChanged.connect(
            lambda text: self._set_dt_row_visible(text == "DT:<custom format>")
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _set_dt_row_visible(self, visible):
        self.dtFormatInput.setVisible(visible)
        for i in range(self.dtFormatRow.count()):
            w = self.dtFormatRow.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    def token(self):
        selected = self.combo.currentText()
        if selected == "DT:<custom format>":
            fmt = self.dtFormatInput.text().strip()
            return {"type": "placeholder", "name": f"DT:{fmt}"}
        return {"type": "placeholder", "name": selected}


class RegexTokenDialog(QDialog):
    """Add a custom regex-mode field for formats no named placeholder covers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        enable_maximize(self)
        set_app_icon(self)
        self.setWindowTitle("Add Regex Field")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Field name (used to label results, e.g. LotCode):"))
        self.nameInput = QLineEdit()
        layout.addWidget(self.nameInput)

        layout.addWidget(QLabel("Regex pattern (e.g. [A-Z]{2}\\d{3}):"))
        self.patternInput = QLineEdit()
        layout.addWidget(self.patternInput)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def token(self):
        return {
            "type": "regex",
            "name": self.nameInput.text().strip() or "Field",
            "pattern": self.patternInput.text(),
        }
