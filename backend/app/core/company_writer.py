"""One transaction lock order for company lifecycle and commercial writers."""
from fastapi import HTTPException
from sqlalchemy import select, text


def lock_company_writer(db, company_id):
    # Callers must establish native actor/company authority before entering.
    # This fixed infrastructure operation grants no record access.
    from app.models.company import Company
    if type(company_id) is not int or company_id <= 0:
        raise HTTPException(403, 'A verified company is required for the writer lock')
    connection = db.connection()
    if connection.dialect.name == 'postgresql':
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 720000000 + company_id})
        row = connection.execute(select(Company.id).where(Company.id == company_id).with_for_update()).first()
    else:
        connection.execute(Company.__table__.update().where(Company.id == company_id).values(name=Company.__table__.c.name))
        row = connection.execute(select(Company.id).where(Company.id == company_id)).first()
    if row is None:
        raise HTTPException(403, 'Company writer scope is unavailable')
