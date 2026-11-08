"""Dated statements from existing posted opening records and voucher entries."""
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.fam.access import FAM_EXPORT_VIEW_PERMISSIONS
from app.apps.fam.models import FAMFinancialYear, FAMOpeningBalance, FAMLedgerEntry, FAMLedger, FAMVoucher, FAMCompanyFinancialSettings

router = APIRouter(prefix='/financial-statements', tags=['Financial statements'])
Report = Literal['trial_balance', 'ledger_report', 'profit_and_loss', 'balance_sheet']
ZERO = Decimal('0')


def money(value):
    return str(Decimal(value or 0).quantize(Decimal('.01')))


def statement(db, company_id, report, from_date=None, to_date=None):
    if report not in {'trial_balance', 'ledger_report', 'profit_and_loss', 'balance_sheet'}:
        raise HTTPException(422, 'Select a supported financial statement')
    if any(value is not None and not isinstance(value, (str, date)) for value in (from_date, to_date)):
        raise HTTPException(422, 'Enter valid statement dates')
    try:
        end = date.fromisoformat(to_date) if isinstance(to_date, str) else to_date or date.today()
        start = date.fromisoformat(from_date) if isinstance(from_date, str) else from_date
    except ValueError:
        raise HTTPException(422, 'Enter valid statement dates')
    year = db.query(FAMFinancialYear).filter(FAMFinancialYear.company_id == company_id,
        FAMFinancialYear.start_date <= end, FAMFinancialYear.end_date >= end).order_by(FAMFinancialYear.start_date.desc()).first()
    if not year:
        raise HTTPException(422, 'Create a financial year covering the statement date')
    start = start or year.start_date
    if not year.start_date <= start <= end:
        raise HTTPException(422, 'Statement dates must be ordered and within one financial year')
    settings = db.query(FAMCompanyFinancialSettings).filter_by(company_id=company_id).first()
    currency = settings.base_currency if settings else 'INR'
    openings = {ident: Decimal(dr or 0) - Decimal(cr or 0) for ident, dr, cr in db.query(
        FAMOpeningBalance.ledger_id, func.sum(FAMOpeningBalance.debit_amount), func.sum(FAMOpeningBalance.credit_amount)
    ).filter(FAMOpeningBalance.company_id == company_id, FAMOpeningBalance.financial_year_id == year.id,
             FAMOpeningBalance.posted.is_(True)).group_by(FAMOpeningBalance.ledger_id).all()}
    # A reversed original remains effective until its separately dated reversal is posted.
    entries = db.query(FAMLedgerEntry).join(FAMVoucher, FAMVoucher.id == FAMLedgerEntry.voucher_id).filter(
        FAMLedgerEntry.company_id == company_id, FAMLedgerEntry.financial_year_id == year.id,
        FAMVoucher.company_id == company_id, FAMVoucher.status.in_(['posted', 'reversed']),
        FAMLedgerEntry.voucher_date >= year.start_date, FAMLedgerEntry.voucher_date <= end)
    def movements(query):
        return {ident: (Decimal(dr or 0), Decimal(cr or 0)) for ident, dr, cr in query.with_entities(
            FAMLedgerEntry.ledger_id, func.sum(FAMLedgerEntry.debit_amount), func.sum(FAMLedgerEntry.credit_amount)
        ).group_by(FAMLedgerEntry.ledger_id).all()}
    prior = movements(entries.filter(FAMLedgerEntry.voucher_date < start))
    period = movements(entries.filter(FAMLedgerEntry.voucher_date >= start))
    rows = []
    for ledger in db.query(FAMLedger).filter_by(company_id=company_id).order_by(FAMLedger.ledger_code).all():
        before_dr, before_cr = prior.get(ledger.id, (ZERO, ZERO))
        dr, cr = period.get(ledger.id, (ZERO, ZERO))
        opening = openings.get(ledger.id, ZERO) + before_dr - before_cr
        closing = opening + dr - cr
        if not any((opening, dr, cr, closing)):
            continue
        rows.append({'ledger_id':ledger.id, 'ledger_code':ledger.ledger_code, 'ledger_name':ledger.ledger_name,
            'nature':ledger.nature, 'currency':currency, 'opening_balance':money(opening),
            'debit':money(dr), 'credit':money(cr), 'closing_balance':money(closing)})
    summary = {}
    if report == 'profit_and_loss':
        rows = [row for row in rows if row['nature'] in {'income', 'expense'}]
        for row in rows:
            amount = Decimal(row['credit']) - Decimal(row['debit']) if row['nature'] == 'income' else Decimal(row['debit']) - Decimal(row['credit'])
            row['amount'] = money(amount)
        income = sum((Decimal(r['amount']) for r in rows if r['nature'] == 'income'), ZERO)
        expense = sum((Decimal(r['amount']) for r in rows if r['nature'] == 'expense'), ZERO)
        summary = {'income':money(income), 'expense':money(expense), 'net_profit':money(income-expense)}
    elif report == 'balance_sheet':
        profit = sum((-Decimal(r['closing_balance']) for r in rows if r['nature'] in {'income','expense'}), ZERO)
        rows = [r for r in rows if r['nature'] in {'asset','liability','equity'}]
        for row in rows:
            row['amount'] = money(Decimal(row['closing_balance']) * (1 if row['nature'] == 'asset' else -1))
        rows.append({'ledger_name':'Unallocated financial-year profit / loss', 'nature':'equity', 'currency':currency, 'amount':money(profit)})
        totals = {nature:sum((Decimal(r['amount']) for r in rows if r['nature']==nature), ZERO) for nature in ('asset','liability','equity')}
        summary = {**{key:money(value) for key,value in totals.items()}, 'difference':money(totals['asset']-totals['liability']-totals['equity'])}
    else:
        dr = sum((max(Decimal(r['closing_balance']), ZERO) for r in rows), ZERO)
        cr = sum((max(-Decimal(r['closing_balance']), ZERO) for r in rows), ZERO)
        summary = {'closing_debit':money(dr), 'closing_credit':money(cr), 'difference':money(dr-cr)}
    return {'report':report, 'from_date':start.isoformat(), 'to_date':end.isoformat(), 'currency':currency,
        'financial_year_id':year.id, 'basis':'Accrual; posted dated opening balances and effective voucher entries only.',
        'items':rows, 'summary':summary}


@router.get('/{report}')
def read_statement(report:Report, from_date:date|None=None, to_date:date|None=None,
                   db:Session=Depends(get_db), user=Depends(RequirePermission(*FAM_EXPORT_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    return statement(db, bootstrap(db,user), report, from_date, to_date)
