"""Never expose company-wide materialized ledger balances in branch views."""
from sqlalchemy import func, inspect


def scoped(db):
    ctx = db.info.get("branch_context")
    return ctx is not None and not (ctx.superuser and ctx.branch_id is None)


def ledger_amounts(db, ledger):
    from app.apps.fam.models import FAMOpeningBalance, FAMLedgerEntry
    if not scoped(db):
        return {key: getattr(ledger, key) for key in ("opening_balance_dr", "opening_balance_cr", "current_balance_dr", "current_balance_cr")}
    opening = db.query(func.coalesce(func.sum(FAMOpeningBalance.debit_amount), 0), func.coalesce(func.sum(FAMOpeningBalance.credit_amount), 0)).filter(FAMOpeningBalance.ledger_id == ledger.id).one()
    movement = db.query(func.coalesce(func.sum(FAMLedgerEntry.debit_amount), 0), func.coalesce(func.sum(FAMLedgerEntry.credit_amount), 0)).filter(FAMLedgerEntry.ledger_id == ledger.id).one()
    return {"opening_balance_dr": opening[0], "opening_balance_cr": opening[1], "current_balance_dr": opening[0] + movement[0], "current_balance_cr": opening[1] + movement[1]}


def protect_serialized(record, output):
    db = inspect(record).session
    if db is None or not scoped(db):
        return output
    if record.__tablename__ == "fam_ledgers":
        output.update({key: float(value or 0) for key, value in ledger_amounts(db, record).items()})
    elif record.__tablename__ == "fam_ledger_entries":
        from app.apps.fam.models import FAMLedgerEntry
        # Stored running_balance includes other branches' postings.
        balance = db.query(func.coalesce(func.sum(FAMLedgerEntry.debit_amount - FAMLedgerEntry.credit_amount), 0)).filter(FAMLedgerEntry.ledger_id == record.ledger_id, FAMLedgerEntry.id <= record.id).scalar()
        output["running_balance"] = float(balance or 0)
    return output
