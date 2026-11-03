from sqlalchemy import event

from app.apps.srm import models
from app.apps.srm.api import router


def test_invoice_list_preserves_payload_with_bounded_queries(db, monkeypatch):
    invoices = []
    for index in range(12):
        invoice = models.SRMInvoice(organization_id=1, invoice_number=f'BATCH-{index}',
            status='draft', subtotal=100, tax_amount=18, total_amount=118,
            paid_amount=0, balance_amount=118)
        db.add(invoice)
        db.flush()
        db.add(models.SRMInvoiceLine(invoice_id=invoice.id, description='Sample line',
            quantity=1, unit_price=100, tax_amount=18, line_total=118))
        invoices.append(invoice)
    db.commit()
    monkeypatch.setattr(router, 'authorized_invoice_query', lambda session, user: session.query(models.SRMInvoice))
    expected = [router._invoice_payload(item, db) for item in reversed(invoices)]
    db.expire_all()
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(db.bind, 'before_cursor_execute', record)
    try:
        actual = router.list_invoices(db, None)
    finally:
        event.remove(db.bind, 'before_cursor_execute', record)
    assert actual == expected
    assert len(statements) <= 8, len(statements)
