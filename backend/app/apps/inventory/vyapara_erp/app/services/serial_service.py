from app.extensions import db
from app.models import SerialNumber


def normalize_serial(value):
    serial = str(value or "").strip().upper()
    if not serial or len(serial) > 100:
        raise ValueError("Serial number must contain 1 to 100 characters")
    return serial


def find_serial(value, product_id=None):
    serial = normalize_serial(value)
    query = SerialNumber.query.filter(db.func.upper(db.func.trim(SerialNumber.serial_no)) == serial)
    if product_id is not None: query = query.filter_by(product_id=product_id)
    rows = query.limit(2).all()
    if len(rows) > 1:
        raise ValueError("Ambiguous legacy serial records require reconciliation")
    return rows[0] if rows else None


def new_serial(value, **fields):
    serial = normalize_serial(value)
    if find_serial(serial):
        raise ValueError("Serial number already exists (case and surrounding spaces are ignored)")
    return SerialNumber(serial_no=serial, **fields)
