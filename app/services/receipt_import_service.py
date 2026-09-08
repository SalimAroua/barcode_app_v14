"""
Bulk import of ReceiptDefinitions from a CSV file - one row per receipt.

Template mini-syntax (used in the CSV's 'template' column), since the
token list can't be written as plain JSON in a single CSV cell:

    <<PlaceholderName>>              -> a named placeholder, e.g. <<PartNumber>>
    <<DT:yyyyMMdd>>                  -> a computed-date placeholder (name is literal)
    <<regex:FieldName=PATTERN>>      -> a regex-mode field
    anything else outside <<...>>    -> literal text, matched exactly

Example:
    <<PartNumber>>-<<regex:LotCode=[A-Z]{2}\\d{3}>>-SN<<SerialNumber>>

Delimiters are '<<' / '>>' rather than '{' / '}' specifically because
regex quantifiers like \\d{3} use braces - reusing '{}' as the
placeholder delimiter would collide with that.

Expected CSV header columns (all optional except name/template):
    name, status, template, part_number, customer_part_number,
    part_description1, part_description2, drawing_number, drawing_date_text,
    manuf_code, ka_revision_level, generation_status, product_designation,
    duns, bg_nr, quantity_text, serial_min, serial_max, timestamp_policy,
    companion_receipt_name, companion_required, prevent_duplicate_scans,
    auto_generate_batch_number, operator_count, notes

A row with a `name` matching an existing receipt UPDATES it; otherwise a
new receipt is created. companion_receipt_name is resolved by name in a
second pass, so the companion receipt can appear earlier OR later in the
same file.
"""
import csv
import re

from app.models import ReceiptDefinition
from app.services import receipt_def_service

TOKEN_RE = re.compile(r"<<(.*?)>>")

REQUIRED_COLUMNS = {"name", "template"}

OPTIONAL_TEXT_COLUMNS = [
    "status", "part_number", "customer_part_number", "part_description1",
    "part_description2", "drawing_number", "drawing_date_text", "manuf_code",
    "ka_revision_level", "generation_status", "product_designation", "duns",
    "bg_nr", "quantity_text", "timestamp_policy", "notes",
]


class ImportError_(Exception):
    """A single row failed to import (name kept distinct from builtin
    ImportError to avoid any confusion with Python's own exception)."""


def parse_template_string(template_str):
    """Turns a mini-syntax template string into a template_tokens list."""
    tokens = []
    pos = 0
    for m in TOKEN_RE.finditer(template_str):
        if m.start() > pos:
            literal_text = template_str[pos:m.start()]
            if literal_text:
                tokens.append({"type": "literal", "value": literal_text})

        inner = m.group(1)
        if inner.startswith("regex:"):
            rest = inner[len("regex:"):]
            if "=" not in rest:
                raise ImportError_(
                    f"Invalid regex token '<<{inner}>>' - expected <<regex:Name=Pattern>>"
                )
            field_name, pattern = rest.split("=", 1)
            try:
                re.compile(pattern)
            except re.error as e:
                raise ImportError_(f"Invalid regex pattern in '<<{inner}>>': {e}") from e
            tokens.append({"type": "regex", "name": field_name.strip(), "pattern": pattern})
        else:
            tokens.append({"type": "placeholder", "name": inner.strip()})

        pos = m.end()

    if pos < len(template_str):
        trailing = template_str[pos:]
        if trailing:
            tokens.append({"type": "literal", "value": trailing})

    return tokens


def _parse_bool(value, default=False):
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def _parse_int_or_none(value):
    value = (value or "").strip()
    return int(value) if value else None


def import_csv(db, file_path, created_by_user_id=None):
    """Returns a report dict: {"created": [...names], "updated": [...names],
    "errors": [(row_number, name_or_blank, message)]}.

    All-or-nothing per row: a bad row is skipped and reported, it doesn't
    abort the whole import.
    """
    created, updated, errors = [], [], []

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            errors.append((0, "", "File is empty or has no header row."))
            return {"created": created, "updated": updated, "errors": errors}

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            errors.append((0, "", f"Missing required column(s): {', '.join(sorted(missing))}"))
            return {"created": created, "updated": updated, "errors": errors}

        rows = list(reader)

    # Pass 1: create/update every row EXCEPT companion linking (needs every
    # receipt to already exist so names can resolve to ids).
    name_to_id = {}
    pending_companion_links = []  # (name, companion_receipt_name, companion_required)

    for row_num, row in enumerate(rows, start=2):  # row 1 is the header
        name = (row.get("name") or "").strip()
        if not name:
            errors.append((row_num, "", "Missing 'name'."))
            continue

        template_str = row.get("template") or ""
        try:
            tokens = parse_template_string(template_str)
        except ImportError_ as e:
            errors.append((row_num, name, str(e)))
            continue

        if not tokens:
            errors.append((row_num, name, "Template is empty."))
            continue

        fields = {"template_tokens": tokens}
        for col in OPTIONAL_TEXT_COLUMNS:
            val = row.get(col)
            if val is not None and val != "":
                fields[col] = val
        if "status" not in fields:
            fields["status"] = "draft"

        try:
            fields["serial_min"] = _parse_int_or_none(row.get("serial_min"))
            fields["serial_max"] = _parse_int_or_none(row.get("serial_max"))
            operator_count = _parse_int_or_none(row.get("operator_count"))
            if operator_count is not None and not 1 <= operator_count <= 10:
                raise ValueError
            fields["operator_count"] = operator_count or 1
        except ValueError:
            errors.append((row_num, name, "serial_min/serial_max must be whole numbers and operator_count must be 1-10."))
            continue

        fields["companion_required"] = _parse_bool(row.get("companion_required"))
        fields["prevent_duplicate_scans"] = _parse_bool(row.get("prevent_duplicate_scans"))
        fields["auto_generate_batch_number"] = _parse_bool(row.get("auto_generate_batch_number"))

        try:
            existing = db.query(ReceiptDefinition).filter_by(name=name).first()
            if existing is None:
                rd = receipt_def_service.create_receipt(
                    db, name=name, created_by_user_id=created_by_user_id, **fields
                )
                created.append(name)
            else:
                rd = receipt_def_service.update_receipt(db, existing.id, **fields)
                updated.append(name)
            name_to_id[name] = rd.id
        except ValueError as e:
            errors.append((row_num, name, str(e)))
            continue

        companion_name = (row.get("companion_receipt_name") or "").strip()
        if companion_name:
            pending_companion_links.append((name, companion_name, fields["companion_required"]))

    # Pass 2: resolve companion links by name now that everything exists.
    for name, companion_name, companion_required in pending_companion_links:
        receipt_id = name_to_id.get(name) or (
            db.query(ReceiptDefinition).filter_by(name=name).first() or ReceiptDefinition()
        ).id
        companion = db.query(ReceiptDefinition).filter_by(name=companion_name).first()
        if companion is None:
            errors.append((0, name, f"Companion receipt '{companion_name}' not found."))
            continue
        try:
            receipt_def_service.update_receipt(
                db, receipt_id, companion_receipt_id=companion.id, companion_required=companion_required
            )
        except ValueError as e:
            errors.append((0, name, str(e)))

    return {"created": created, "updated": updated, "errors": errors}
