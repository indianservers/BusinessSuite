from sqlalchemy import event
from app.apps.fam.schema import ensure_fam_seed_data
from app.apps.fam.models import FAMLedger, FAMVoucherType


def test_warm_finance_seed_batches_reads_and_preserves_custom_values(db):
    ensure_fam_seed_data(db, 1)
    ledger = db.query(FAMLedger).filter_by(company_id=1, ledger_code="CASH").one()
    voucher = db.query(FAMVoucherType).filter_by(company_id=1, voucher_type_code="JV").one()
    ledger.ledger_name = "Customized cash account"
    voucher.numbering_sequence = 84
    db.flush()
    statements = []
    connection = db.connection()
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(connection, "before_cursor_execute", record)
    try:
        ensure_fam_seed_data(db, 1)
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert len(statements) == 5, statements
    assert ledger.ledger_name == "Customized cash account"
    assert voucher.numbering_sequence == 84
