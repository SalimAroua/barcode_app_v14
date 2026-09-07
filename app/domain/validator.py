"""
Validates a scanned barcode string against a ReceiptDefinition's template.

Strategy: try the single composed regex first (see template_engine.py). If
it matches, we're done - extract SerialNumber/regex-group values for range
checks. If it doesn't match, walk the token list left-to-right rebuilding
the pattern one token at a time to find exactly where things diverge, so we
can report a specific, human-readable reason instead of just "no match".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.template_engine import compile_template, SERIAL_PLACEHOLDER


@dataclass
class ValidationResult:
    ok: bool
    failure_reason: Optional[str] = None
    details: dict = field(default_factory=dict)


def _diagnose(compiled, scanned_value: str) -> ValidationResult:
    """Only called when the full match already failed. Rebuilds the regex
    one token at a time (each attempt anchored at the start only) to find
    the first token that doesn't fit, and classifies why.
    """
    prefix_parts = []
    for kind, label, payload in compiled.tokens:
        if kind == "literal":
            piece = re.escape(payload)
        elif kind == "serial":
            piece = r"(?P<SerialNumber>\d+)"
        elif kind == "placeholder":
            piece = re.escape(payload)
        elif kind == "regex":
            group_name = re.sub(r"\W", "_", label) or "field"
            piece = f"(?P<{group_name}>{payload})"
        else:
            piece = ""

        candidate_pattern = re.compile("^" + "".join(prefix_parts) + piece)
        m = candidate_pattern.match(scanned_value)

        if m is None:
            # this token is the first one that fails
            if kind == "literal":
                return ValidationResult(False, "LiteralMismatch", {"expected": payload, "at_token": label})
            if kind == "placeholder":
                return ValidationResult(False, "FieldMismatch", {"placeholder": label, "expected": payload})
            if kind == "serial":
                return ValidationResult(False, "SerialNotNumeric", {})
            if kind == "regex":
                return ValidationResult(False, "FieldMismatch", {"field": label, "pattern": payload})

        prefix_parts.append(piece)

    # every token matched as a prefix, so the mismatch is about length:
    full_prefix_pattern = re.compile("^" + "".join(prefix_parts))
    m = full_prefix_pattern.match(scanned_value)
    if m and m.end() < len(scanned_value):
        return ValidationResult(False, "TrailingData", {"leftover": scanned_value[m.end():]})
    if m and m.end() == len(scanned_value):
        # all tokens matched and consumed everything -> shouldn't happen
        # since the full fullmatch would have succeeded; fall through
        return ValidationResult(False, "TruncatedInput", {})
    return ValidationResult(False, "TruncatedInput", {})


def validate_scanned_barcode(
    scanned_value: str,
    receipt_def,
    scan_session=None,
    now: datetime | None = None,
) -> ValidationResult:
    now = now or datetime.now()
    compiled = compile_template(receipt_def, scan_session, now)  # raises TemplateError subclasses

    match = compiled.pattern.fullmatch(scanned_value)

    if match is None:
        return _diagnose(compiled, scanned_value)

    details = {}

    if compiled.has_serial:
        serial_str = match.group("SerialNumber")
        serial_value = int(serial_str)
        details["SerialNumber"] = serial_value

        serial_min = receipt_def.serial_min
        serial_max = receipt_def.serial_max
        if serial_min is not None and serial_value < serial_min:
            return ValidationResult(False, "SerialOutOfRange", {"value": serial_value, "min": serial_min, "max": serial_max})
        if serial_max is not None and serial_value > serial_max:
            return ValidationResult(False, "SerialOutOfRange", {"value": serial_value, "min": serial_min, "max": serial_max})

    for group_name in compiled.variable_group_names:
        details[group_name] = match.group(group_name)

    return ValidationResult(True, None, details)
