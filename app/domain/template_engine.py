"""
Compiles a ReceiptDefinition's `template_tokens` into a single regular
expression, then matches the whole scanned barcode against it in one shot.

Why one composed regex instead of hand-rolled positional matching:
 - PartNumber, CustomerPartNumber, Date, etc. all resolve to a KNOWN exact
   value before the scan happens, so they compile to escaped literal text.
 - Only two kinds of token are truly variable-length: SerialNumber (an
   unknown number of digits that will be range-checked afterwards) and
   Regex-mode fields (a user-supplied pattern).
 - Python's own regex backtracking resolves the "where does this variable
   field end" question automatically, even when a template has more than
   one variable field - no custom boundary rule needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.exceptions import (
    InvalidRegexTokenError,
    MissingSessionFieldError,
    UnknownPlaceholderError,
)

# Placeholder -> attribute name on ReceiptDefinition (exact-text fields)
FIXED_FIELD_MAP = {
    "PartNumber": "part_number",
    "CustomerPartNumber": "customer_part_number",
    "PartDescription1": "part_description1",
    "PartDescription2": "part_description2",
    "DrawingNumber": "drawing_number",
    "DrawingDate": "drawing_date_text",
    "ManufCode": "manuf_code",
    "KaRevisionLevel": "ka_revision_level",
    "GenerationStatus": "generation_status",
    "ProductDesignation": "product_designation",
    "DUNS": "duns",
    "BgNr": "bg_nr",
    "Quantity": "quantity_text",
}

# Placeholder -> attribute name on ScanSession
SESSION_FIELD_MAP = {
    "LineNumber": "line_number",
    "PlainLineNumber": "plain_line_number",
    "OpNumber": "operator_number",
}

SERIAL_PLACEHOLDER = "SerialNumber"

_DT_TOKEN_RE = re.compile(r"yyyy|yy|MM|M|dd|d|HH|H|mm|m|ss|s|DOY")
_DT_TOKEN_TO_STRFTIME = {
    "yyyy": "%Y", "yy": "%y",
    "MM": "%m", "M": "%m",  # both zero-padded for simplicity/consistency
    "dd": "%d", "d": "%d",
    "HH": "%H", "H": "%H",
    "mm": "%M", "m": "%M",
    "ss": "%S", "s": "%S",
    "DOY": "%j",
}


def format_dt(now: datetime, fmt: str) -> str:
    """Render a DT:<format> placeholder, e.g. 'yyyyMMdd' -> '20260717'."""
    def repl(m):
        return now.strftime(_DT_TOKEN_TO_STRFTIME[m.group(0)])
    return _DT_TOKEN_RE.sub(repl, fmt)


@dataclass
class CompiledTemplate:
    pattern: "re.Pattern"
    variable_group_names: list = field(default_factory=list)  # groups that aren't SerialNumber
    has_serial: bool = False
    # ordered list of (token, resolved_literal_or_None) - used for the
    # diagnostic (friendly-reason) pass when a scan fails to match.
    tokens: list = field(default_factory=list)


def _resolve_fixed_or_computed(name: str, receipt_def, scan_session, now: datetime) -> str:
    """Resolve a placeholder that has a single known value at compile time
    (i.e. everything except SerialNumber and Regex tokens)."""
    if name in FIXED_FIELD_MAP:
        value = getattr(receipt_def, FIXED_FIELD_MAP[name], None)
        return "" if value is None else str(value)

    if name == "CustomerPartNumberNoDot":
        value = getattr(receipt_def, "customer_part_number", None) or ""
        return value.replace(".", "")

    if name in SESSION_FIELD_MAP:
        if scan_session is None:
            raise MissingSessionFieldError(
                f"Placeholder '{name}' requires an active ScanSession, but none was provided."
            )
        value = getattr(scan_session, SESSION_FIELD_MAP[name], None)
        return "" if value is None else str(value)

    if name == "Date":
        return now.strftime("%d.%m.%Y")

    if name == "Time":
        return now.strftime("%H:%M:%S")

    if name.startswith("DT:"):
        return format_dt(now, name[len("DT:"):])

    raise UnknownPlaceholderError(f"Unknown placeholder: '{name}'")


# Public alias - used by the receipt editor UI to render a live preview of
# a single placeholder's resolved value without compiling a full template.
resolve_placeholder_value = _resolve_fixed_or_computed


def compile_template(receipt_def, scan_session=None, now: datetime | None = None) -> CompiledTemplate:
    """Turn receipt_def.template_tokens into one composed regex.

    Raises TemplateError subclasses if the template references a session
    field with no session, an unknown placeholder, or an invalid regex.
    """
    now = now or datetime.now()
    tokens = receipt_def.template_tokens or []

    parts = []
    variable_group_names = []
    has_serial = False
    diagnostic_tokens = []  # (kind, label, resolved_literal_or_pattern)

    for idx, tok in enumerate(tokens):
        kind = tok.get("type")

        if kind == "literal":
            value = tok.get("value", "")
            parts.append(re.escape(value))
            diagnostic_tokens.append(("literal", value, value))

        elif kind == "placeholder" and tok.get("name") == SERIAL_PLACEHOLDER:
            has_serial = True
            parts.append(r"(?P<SerialNumber>\d+)")
            diagnostic_tokens.append(("serial", "SerialNumber", None))

        elif kind == "placeholder":
            name = tok.get("name")
            value = _resolve_fixed_or_computed(name, receipt_def, scan_session, now)
            parts.append(re.escape(value))
            diagnostic_tokens.append(("placeholder", name, value))

        elif kind == "regex":
            name = tok.get("name") or f"field{idx}"
            pattern = tok.get("pattern", "")
            group_name = re.sub(r"\W", "_", name) or f"field{idx}"
            try:
                re.compile(pattern)
            except re.error as e:
                raise InvalidRegexTokenError(f"Regex field '{name}' has an invalid pattern: {e}") from e
            parts.append(f"(?P<{group_name}>{pattern})")
            variable_group_names.append(group_name)
            diagnostic_tokens.append(("regex", name, pattern))

        else:
            raise UnknownPlaceholderError(f"Unknown token type: {tok!r}")

    full_pattern = re.compile("^" + "".join(parts) + "$")

    return CompiledTemplate(
        pattern=full_pattern,
        variable_group_names=variable_group_names,
        has_serial=has_serial,
        tokens=diagnostic_tokens,
    )
