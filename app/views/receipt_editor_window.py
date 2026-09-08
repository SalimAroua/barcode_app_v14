from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QComboBox, QGroupBox, QFormLayout,
    QMessageBox, QSplitter, QTextEdit, QCheckBox, QScrollArea, QSpinBox
)
from PySide6.QtCore import Qt

from app.services.receipt_def_service import FIXED_FIELD_NAMES
from app.views.window_utils import enable_maximize, set_app_icon

# Human-friendly labels for the fixed fields, matching the reference label
# naming from the spec (Section 3.1).
FIELD_LABELS = {
    "part_number": "PartNumber",
    "customer_part_number": "Customer PartNumber",
    "part_description1": "Part descr. line 1",
    "part_description2": "Part descr. line 2",
    "drawing_number": "Drawing number",
    "drawing_date_text": "Drawing date",
    "manuf_code": "Manuf. code",
    "ka_revision_level": "KA revision number",
    "generation_status": "Status part history",
    "product_designation": "Product designation",
    "duns": "DUNS",
    "bg_nr": "BG-Nr",
    "quantity_text": "Quantity",
}


class ReceiptEditorWindow(QWidget):
    """Admin screen: pick a receipt on the left to edit it, or start a new
    one; build its template token-by-token in the middle; set its fixed
    field values and rules on the right.
    """

    def __init__(self):
        super().__init__()
        enable_maximize(self)
        set_app_icon(self)
        self.setWindowTitle("Barcode Placeholder App - Receipt Definitions")
        self.resize(1000, 640)

        root = QHBoxLayout()

        # ---- Left: receipt list ----
        left = QVBoxLayout()
        left.addWidget(QLabel("Receipts"))
        self.receiptList = QListWidget()
        left.addWidget(self.receiptList)
        self.newButton = QPushButton("New Receipt")
        left.addWidget(self.newButton)
        self.importCsvButton = QPushButton("Import CSV...")
        left.addWidget(self.importCsvButton)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(220)

        # ---- Middle: template token builder ----
        middle = QVBoxLayout()
        middle.addWidget(QLabel("Template tokens (in order):"))
        self.tokenList = QListWidget()
        middle.addWidget(self.tokenList)

        token_buttons = QHBoxLayout()
        self.addLiteralButton = QPushButton("+ Literal")
        self.addPlaceholderButton = QPushButton("+ Placeholder")
        self.addRegexButton = QPushButton("+ Regex")
        self.moveUpButton = QPushButton("\u2191")
        self.moveDownButton = QPushButton("\u2193")
        self.removeTokenButton = QPushButton("Remove")
        for b in (self.addLiteralButton, self.addPlaceholderButton, self.addRegexButton,
                  self.moveUpButton, self.moveDownButton, self.removeTokenButton):
            token_buttons.addWidget(b)
        middle.addLayout(token_buttons)

        middle.addWidget(QLabel("Live preview (example barcode this template would accept):"))
        self.previewLabel = QLabel("")
        self.previewLabel.setWordWrap(True)
        self.previewLabel.setStyleSheet("color: #2a6; font-family: monospace;")
        middle.addWidget(self.previewLabel)

        middle_widget = QWidget()
        middle_widget.setLayout(middle)

        # ---- Right: fixed fields + rules ----
        right = QVBoxLayout()

        identity_box = QGroupBox("Identity")
        identity_form = QFormLayout()
        self.nameInput = QLineEdit()
        self.statusCombo = QComboBox()
        self.statusCombo.addItems(["draft", "active", "retired"])
        identity_form.addRow("Name", self.nameInput)
        identity_form.addRow("Status", self.statusCombo)
        identity_box.setLayout(identity_form)
        right.addWidget(identity_box)

        fields_box = QGroupBox("Fixed fields")
        fields_form = QFormLayout()
        self.field_inputs = {}
        for field_name in FIXED_FIELD_NAMES:
            edit = QLineEdit()
            fields_form.addRow(FIELD_LABELS.get(field_name, field_name), edit)
            self.field_inputs[field_name] = edit
        fields_box.setLayout(fields_form)
        right.addWidget(fields_box)

        rules_box = QGroupBox("SerialNumber bounds")
        rules_form = QFormLayout()
        self.serialMinInput = QLineEdit()
        self.serialMaxInput = QLineEdit()
        rules_form.addRow("Min", self.serialMinInput)
        rules_form.addRow("Max", self.serialMaxInput)
        rules_box.setLayout(rules_form)
        right.addWidget(rules_box)

        duplicate_box = QGroupBox("Duplicate detection")
        duplicate_layout = QVBoxLayout()
        self.preventDuplicatesCheck = QCheckBox("Reject a barcode that has already passed before")
        self.preventDuplicatesCheck.setToolTip(
            "Checks the full scanned barcode against every previously PASSED scan "
            "for this receipt (any session, any time). A repeat is logged as a "
            "failed scan (reason: DuplicateScan) rather than counted as a pass."
        )
        duplicate_layout.addWidget(self.preventDuplicatesCheck)
        duplicate_box.setLayout(duplicate_layout)
        right.addWidget(duplicate_box)

        batch_box = QGroupBox("Batch number")
        batch_layout = QVBoxLayout()
        self.autoGenerateBatchCheck = QCheckBox("Auto-generate batch number (Date + Line + running sequence)")
        self.autoGenerateBatchCheck.setToolTip(
            "When on, the operator's Batch field is ignored at session start and a "
            "batch number is generated automatically instead: YYMMDD + Plain Line # "
            "+ an ever-increasing per-line sequence, e.g. 26090712001 for "
            "2026-09-07, line 12, the 1st batch ever started on that line. "
            "The sequence never resets and is shared across every receipt run on "
            "that line."
        )
        batch_layout.addWidget(self.autoGenerateBatchCheck)
        batch_box.setLayout(batch_layout)
        right.addWidget(batch_box)

        workflow_box = QGroupBox("Workflow")
        workflow_form = QFormLayout()
        self.targetQtyInput = QLineEdit()
        self.targetQtyInput.setPlaceholderText("Required quantity")
        self.operatorCountInput = QSpinBox()
        self.operatorCountInput.setRange(1, 10)
        self.operatorCountInput.setValue(1)
        self.batchTemplateInput = QLineEdit()
        self.batchTemplateInput.setPlaceholderText("Select .zpl label template")
        self.templateBrowseButton = QPushButton("Choose template")
        template_row = QHBoxLayout()
        template_row.addWidget(self.batchTemplateInput)
        template_row.addWidget(self.templateBrowseButton)
        workflow_form.addRow("Target quantity:", self.targetQtyInput)
        workflow_form.addRow("Number of operators:", self.operatorCountInput)
        workflow_form.addRow("Label template:", template_row)
        workflow_box.setLayout(workflow_form)
        right.addWidget(workflow_box)

        ts_box = QGroupBox("Timestamp policy")
        ts_layout = QVBoxLayout()
        self.timestampPolicyCombo = QComboBox()
        self.timestampPolicyCombo.addItems(["use_scan_time", "freeze_on_receipt_def"])
        ts_layout.addWidget(self.timestampPolicyCombo)
        ts_box.setLayout(ts_layout)
        right.addWidget(ts_box)

        companion_box = QGroupBox("Companion label (optional)")
        companion_form = QFormLayout()
        self.companionCombo = QComboBox()
        self.companionRequiredCheck = QCheckBox("Companion required")
        companion_form.addRow("Companion receipt", self.companionCombo)
        companion_form.addRow("", self.companionRequiredCheck)
        companion_box.setLayout(companion_form)
        right.addWidget(companion_box)

        notes_box = QGroupBox("Notes")
        notes_layout = QVBoxLayout()
        self.notesInput = QTextEdit()
        self.notesInput.setMaximumHeight(60)
        notes_layout.addWidget(self.notesInput)
        notes_box.setLayout(notes_layout)
        right.addWidget(notes_box)

        self.saveButton = QPushButton("Save")
        right.addWidget(self.saveButton)

        self.closeButton = QPushButton("Close")
        right.addWidget(self.closeButton)

        right_widget = QWidget()
        right_layout_container = QVBoxLayout()
        right_layout_container.addLayout(right)
        right_widget.setLayout(right_layout_container)
        right_widget.setMinimumWidth(500)

        right_scroll = QScrollArea()
        right_scroll.setWidget(right_widget)
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setMinimumWidth(520)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_scroll)
        splitter.setMaximumWidth(1500)
        splitter.setSizes([220, 500, 600])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

        root.addWidget(splitter, alignment=Qt.AlignHCenter)
        self.setLayout(root)

    # ---- helpers used by the controller ----

    def show_error(self, message):
        QMessageBox.warning(self, "Error", message)

    def show_info(self, message):
        QMessageBox.information(self, "Info", message)

    def clear_form(self):
        self.nameInput.clear()
        self.statusCombo.setCurrentIndex(0)
        for edit in self.field_inputs.values():
            edit.clear()
        self.serialMinInput.clear()
        self.serialMaxInput.clear()
        self.timestampPolicyCombo.setCurrentIndex(0)
        self.companionCombo.setCurrentIndex(0)
        self.companionRequiredCheck.setChecked(False)
        self.preventDuplicatesCheck.setChecked(False)
        self.autoGenerateBatchCheck.setChecked(False)
        self.targetQtyInput.clear()
        self.operatorCountInput.setValue(1)
        self.batchTemplateInput.clear()
        self.notesInput.clear()
        self.tokenList.clear()
        self.previewLabel.setText("")

    def token_type_label(self, token):
        if token["type"] == "literal":
            return f"[literal] {token['value']!r}"
        if token["type"] == "placeholder":
            return f"[placeholder] {token['name']}"
        if token["type"] == "regex":
            return f"[regex] {token['name']} = {token['pattern']!r}"
        return str(token)

    def set_tokens(self, tokens):
        self.tokenList.clear()
        for tok in tokens:
            item = QListWidgetItem(self.token_type_label(tok))
            item.setData(Qt.UserRole, tok)
            self.tokenList.addItem(item)

    def get_tokens(self):
        tokens = []
        for i in range(self.tokenList.count()):
            tokens.append(self.tokenList.item(i).data(Qt.UserRole))
        return tokens
