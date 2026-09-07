from datetime import datetime, timezone

from app.models import ReceiptDefinition


FIXED_FIELD_NAMES = [
    "part_number", "customer_part_number", "part_description1", "part_description2",
    "drawing_number", "drawing_date_text", "manuf_code", "ka_revision_level",
    "generation_status", "product_designation", "duns", "bg_nr", "quantity_text",
]


def list_active_receipts(db):
    return (
        db.query(ReceiptDefinition)
        .filter(ReceiptDefinition.status == "active")
        .order_by(ReceiptDefinition.name)
        .all()
    )


def list_all_receipts(db):
    return db.query(ReceiptDefinition).order_by(ReceiptDefinition.name).all()


def get_receipt(db, receipt_id):
    return db.query(ReceiptDefinition).get(receipt_id)


def get_receipt_by_name(db, name):
    return db.query(ReceiptDefinition).filter_by(name=name).first()


def create_receipt(db, *, name, created_by_user_id=None, **fields):
    existing = db.query(ReceiptDefinition).filter_by(name=name).first()
    if existing is not None:
        raise ValueError(f"A receipt named '{name}' already exists.")

    rd = ReceiptDefinition(
        name=name,
        created_at=datetime.now(timezone.utc),
        created_by_user_id=created_by_user_id,
        **fields,
    )
    db.add(rd)
    db.commit()
    db.refresh(rd)
    return rd


def update_receipt(db, receipt_id, **fields):
    rd = db.query(ReceiptDefinition).get(receipt_id)
    if rd is None:
        raise ValueError("ReceiptDefinition not found.")

    new_name = fields.get("name")
    if new_name and new_name != rd.name:
        clash = db.query(ReceiptDefinition).filter(
            ReceiptDefinition.name == new_name, ReceiptDefinition.id != receipt_id
        ).first()
        if clash is not None:
            raise ValueError(f"A receipt named '{new_name}' already exists.")

    for key, value in fields.items():
        setattr(rd, key, value)
    db.add(rd)
    db.commit()
    db.refresh(rd)
    return rd


def seed_demo_receipt_if_missing(db):
    """Creates one demo ReceiptDefinition so the app is usable end-to-end
    before a real receipt-editor UI exists. Safe to call every startup."""
    existing = db.query(ReceiptDefinition).filter_by(name="DEMO_RECEIPT").first()
    if existing is not None:
        return existing

    rd = ReceiptDefinition(
        name="DEMO_RECEIPT",
        status="active",
        template_tokens=[
            {"type": "placeholder", "name": "PartNumber"},
            {"type": "literal", "value": "-"},
            {"type": "placeholder", "name": "CustomerPartNumberNoDot"},
            {"type": "literal", "value": "-SN"},
            {"type": "placeholder", "name": "SerialNumber"},
        ],
        part_number="PN-DEMO-001",
        customer_part_number="CUST.123.456",
        serial_min=1_000_000,
        serial_max=9_999_999,
        timestamp_policy="use_scan_time",
        created_at=datetime.now(timezone.utc),
    )
    db.add(rd)
    db.commit()
    db.refresh(rd)
    return rd
