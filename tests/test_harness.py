"""
Headless functional tests for the template engine + validator.
Run with: python -m tests.test_harness
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.receipt_definition import ReceiptDefinition
from app.services.validation_service import validate

PASS, FAIL = "PASS", "FAIL"
results = []


def check(label, scanned, rd, session=None, now=None, expect_ok=True, expect_reason=None):
    res = validate(scanned, rd, session, use_now=now or datetime(2026, 7, 17, 10, 30, 45, tzinfo=timezone.utc))
    ok_match = res.ok == expect_ok
    reason_match = True if expect_reason is None else (res.failure_reason == expect_reason)
    status = PASS if (ok_match and reason_match) else FAIL
    results.append((status, label, scanned, res.ok, res.failure_reason, res.details))


def make_rd(**overrides):
    base = dict(
        id=1, name="TEST", status="active", template_tokens=[],
        part_number=None, customer_part_number=None, part_description1=None,
        part_description2=None, drawing_number=None, drawing_date_text=None,
        manuf_code=None, ka_revision_level=None, generation_status=None,
        product_designation=None, duns=None, bg_nr=None, quantity_text=None,
        serial_min=None, serial_max=None,
        timestamp_policy="use_scan_time", frozen_timestamp=None,
        companion_receipt_id=None, companion_required=False,
    )
    base.update(overrides)
    return ReceiptDefinition(**base)


def main():
    # Section 1: exact-value placeholders + fixed-width-style serial via min/max
    rd1 = make_rd(
        template_tokens=[
            {"type": "placeholder", "name": "PartNumber"},
            {"type": "literal", "value": "-"},
            {"type": "placeholder", "name": "CustomerPartNumberNoDot"},
            {"type": "literal", "value": "-SN"},
            {"type": "placeholder", "name": "SerialNumber"},
        ],
        part_number="PN-EXAMPLE-001",
        customer_part_number="CUST.123.456",
        serial_min=1_000_000, serial_max=9_999_999,  # emulates old "fixed 7 digits"
    )
    check("Valid barcode", "PN-EXAMPLE-001-CUST123456-SN1000000", rd1, expect_ok=True)
    check("Wrong PartNumber", "PN-WRONG-001-CUST123456-SN1000000", rd1, expect_ok=False, expect_reason="FieldMismatch")
    # SerialNumber is the LAST token here with nothing after it, so "1A00000"
    # is read as serial="1" + leftover "A00000" -> correctly TrailingData,
    # not SerialNotNumeric. (See rd1b below for a genuine SerialNotNumeric case.)
    check("Letter right after a valid digit (no anchor) -> trailing, not non-numeric", "PN-EXAMPLE-001-CUST123456-SN1A00000", rd1, expect_ok=False, expect_reason="TrailingData")
    check("Serial below the emulated width (too few digits -> below min)", "PN-EXAMPLE-001-CUST123456-SN123", rd1, expect_ok=False, expect_reason="SerialOutOfRange")
    check("Trailing garbage", "PN-EXAMPLE-001-CUST123456-SN1000000EXTRA", rd1, expect_ok=False, expect_reason="TrailingData")

    # rd1b: same idea but with a literal AFTER SerialNumber, so the serial
    # field is anchored and a non-digit right there is a genuine SerialNotNumeric.
    rd1b = make_rd(
        template_tokens=[
            {"type": "literal", "value": "SN"},
            {"type": "placeholder", "name": "SerialNumber"},
            {"type": "literal", "value": "-END"},
        ],
        serial_min=1, serial_max=9_999_999,
    )
    check("Anchored serial: no digit at all -> genuine SerialNotNumeric", "SNXYZ-END", rd1b, expect_ok=False, expect_reason="SerialNotNumeric")
    check("Anchored serial: valid", "SN42-END", rd1b, expect_ok=True)

    # Section 2: SerialNumber bounds only (no emulated width)
    rd2 = make_rd(
        template_tokens=[{"type": "literal", "value": "BOX-"}, {"type": "placeholder", "name": "SerialNumber"}],
        serial_min=100, serial_max=200,
    )
    check("Serial within range", "BOX-150", rd2, expect_ok=True)
    check("Serial below min", "BOX-50", rd2, expect_ok=False, expect_reason="SerialOutOfRange")
    check("Serial above max", "BOX-999", rd2, expect_ok=False, expect_reason="SerialOutOfRange")

    # Section 3: Date / Time / DT: placeholders
    rd3 = make_rd(template_tokens=[
        {"type": "placeholder", "name": "Date"}, {"type": "literal", "value": "_"},
        {"type": "placeholder", "name": "Time"}, {"type": "literal", "value": "_"},
        {"type": "placeholder", "name": "DT:yyyyMMdd"},
    ])
    check("Date/Time/DT formats", "17.07.2026_10:30:45_20260717", rd3, expect_ok=True)
    check("Wrong date format", "2026-07-17_10:30:45_20260717", rd3, expect_ok=False, expect_reason="FieldMismatch")

    # Section 4: session-scoped fields
    rd4 = make_rd(template_tokens=[
        {"type": "placeholder", "name": "OpNumber"}, {"type": "literal", "value": "-"},
        {"type": "placeholder", "name": "LineNumber"},
    ])
    fake_session = SimpleNamespace(operator_number="OP07", line_number="FAWL12", plain_line_number="12")
    check("Session fields present", "OP07-FAWL12", rd4, session=fake_session, expect_ok=True)

    # Section 5: Regex-mode field (new capability)
    rd5 = make_rd(template_tokens=[
        {"type": "literal", "value": "LOT-"},
        {"type": "regex", "name": "LotCode", "pattern": r"[A-Z]{2}\d{3}"},
        {"type": "literal", "value": "-END"},
    ])
    check("Regex field matches", "LOT-AB123-END", rd5, expect_ok=True)
    check("Regex field wrong shape", "LOT-A1234-END", rd5, expect_ok=False, expect_reason="FieldMismatch")

    # Section 6: mixing SerialNumber AND a regex field in one template
    # (this is exactly the scenario the composed-regex design exists for)
    rd6 = make_rd(template_tokens=[
        {"type": "regex", "name": "Prefix", "pattern": r"[A-Z]{2,4}"},
        {"type": "literal", "value": "-"},
        {"type": "placeholder", "name": "SerialNumber"},
    ], serial_min=1, serial_max=99999)
    check("Two variable fields resolved via backtracking", "ABCD-42", rd6, expect_ok=True)
    check("Two variable fields, serial out of range", "ABCD-999999", rd6, expect_ok=False, expect_reason=None)

    # Section 7: Product Designation (the field added in spec v0.2)
    rd7 = make_rd(template_tokens=[{"type": "placeholder", "name": "ProductDesignation"}], product_designation="WIDGET-X")
    check("New ProductDesignation field", "WIDGET-X", rd7, expect_ok=True)

    print("\n" + "=" * 100)
    print(f"{'STATUS':<6} {'SCENARIO':<55} SCANNED")
    print("=" * 100)
    n_pass = 0
    for status, label, scanned, ok, reason, details in results:
        n_pass += status == PASS
        print(f"{status:<6} {label:<55} {scanned!r}")
        if status == FAIL:
            print(f"       -> got ok={ok} reason={reason} details={details}")
    print("=" * 100)
    print(f"{n_pass}/{len(results)} passed")


if __name__ == "__main__":
    main()
