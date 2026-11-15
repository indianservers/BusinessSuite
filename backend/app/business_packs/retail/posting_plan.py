"""Create a finite refund posting plan from actual posted native sale sources."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from app.apps.fam import models as fam
from app.apps.srm.models import SRMReceipt,SRMInvoice
from app.apps.srm.service_checkout_models import POSCheckoutPayment
from .accounting import PostingPlan,VoucherSpec,_certify,authority,fail
from .models import RetailReturn


def build(db,actor,scope,source,checkout):
    authority(db,actor,scope)
    connection=db.connection();company=scope.company_id
    def rows(model,*criteria):
        table=model.__table__
        return list(connection.execute(select(table).where(*criteria)).mappings())
    def posted(kind,ident,expected_amount):
        mapping=fam.FAMSRMMapping.__table__;voucher=fam.FAMVoucher.__table__
        found=connection.execute(select(voucher).join(mapping,mapping.c.fam_record_id==voucher.c.id).where(
            mapping.c.company_id==company,mapping.c.srm_record_type==kind,mapping.c.srm_record_id==ident,
            mapping.c.fam_record_type=='voucher',mapping.c.mapping_status=='active',
            voucher.c.company_id==company,voucher.c.source_module=='srm',voucher.c.source_record_type==kind,
            voucher.c.source_record_id==str(ident),voucher.c.status=='posted')).mappings().all()
        if len(found)!=1:
            fail('Post the original invoice and its collected receipts in Accounting before issuing a Retail refund',409)
        lines=rows(fam.FAMVoucherLine,fam.FAMVoucherLine.voucher_id==found[0]['id'])
        if not lines:fail('Original accounting posting has no issued voucher lines',409)
        totals=(Decimal(found[0]['total_debit']),Decimal(found[0]['total_credit']),
            sum((Decimal(line['debit_amount'] or 0) for line in lines),Decimal(0)),
            sum((Decimal(line['credit_amount'] or 0) for line in lines),Decimal(0)))
        if any(value!=Decimal(expected_amount) for value in totals):
            fail('Original sale and its posted accounting amounts require reconciliation before refunding',409)
        return found[0],lines
    settings=rows(fam.FAMCompanyFinancialSettings,fam.FAMCompanyFinancialSettings.company_id==company)
    if len(settings)!=1 or settings[0]['base_currency']!=source.currency:
        fail('Configure Accounting in the original sale currency before refunding',409)
    total=connection.scalar(select(SRMInvoice.total_amount).where(SRMInvoice.id==checkout.invoice_id,SRMInvoice.organization_id==company))
    if total is None:fail('Original invoice is unavailable',409)
    invoice,issued=posted('invoice',checkout.invoice_id,total)
    debit=[row for row in issued if Decimal(row['debit_amount'] or 0)>0]
    if len(debit)!=1 or not debit[0]['party_id']:fail('Original sale party posting needs reconciliation',409)
    party_id=debit[0]['party_id'];party_ledger=debit[0]['ledger_id']
    parties=rows(fam.FAMParty,fam.FAMParty.id==party_id,fam.FAMParty.company_id==company,
        fam.FAMParty.ledger_id==party_ledger,fam.FAMParty.active.is_(True))
    mapping=fam.FAMSRMMapping.__table__
    mapped=connection.execute(select(mapping.c.id).where(mapping.c.company_id==company,
        mapping.c.srm_record_type=='customer',mapping.c.srm_record_id==checkout.customer_id,
        mapping.c.fam_record_type=='party',mapping.c.fam_record_id==party_id,mapping.c.mapping_status=='active')).first()
    if len(parties)!=1 or mapped is None:fail('Original customer accounting party is unavailable',409)
    credits=[row for row in issued if Decimal(row['credit_amount'] or 0)>0]
    ledger_ids={row['ledger_id'] for row in issued}
    ledgers=rows(fam.FAMLedger,fam.FAMLedger.id.in_(ledger_ids),fam.FAMLedger.company_id==company,fam.FAMLedger.active.is_(True))
    if {row['id'] for row in ledgers}!=ledger_ids:fail('Original sale ledger is unavailable',409)
    sales_ids={row['id'] for row in ledgers if row['ledger_code']=='SALES'}
    sales=[row for row in credits if row['ledger_id'] in sales_ids]
    if len(sales)!=1:fail('Original sales posting cannot be returned by this workflow',409)
    sale=sales[0]
    taxes={row['ledger_id']:Decimal(row['credit_amount']) for row in credits if row is not sale}
    if len(taxes)!=len(credits)-1:fail('Original tax ledger allocations need reconciliation',409)
    prior=rows(RetailReturn,RetailReturn.organization_id==company,RetailReturn.branch_id==scope.branch_id,
        RetailReturn.pack_context_id==scope.context_id,RetailReturn.checkout_id==checkout.id,RetailReturn.state=='committed')
    for old in prior:
        old_vouchers=rows(fam.FAMVoucher,fam.FAMVoucher.id==old['credit_voucher_id'],fam.FAMVoucher.company_id==company,
            fam.FAMVoucher.source_module=='srm',fam.FAMVoucher.source_record_type=='retail_return',
            fam.FAMVoucher.source_record_id==str(old['id']),fam.FAMVoucher.status=='posted')
        if len(old_vouchers)!=1:fail('Earlier return accounting needs reconciliation',409)
        for line in rows(fam.FAMVoucherLine,fam.FAMVoucherLine.voucher_id==old['credit_voucher_id']):
            if line['ledger_id'] in taxes:taxes[line['ledger_id']]-=Decimal(line['debit_amount'] or 0)
    refund_tax=Decimal(source.tax_amount);remaining_tax=sum(taxes.values(),Decimal(0))
    if any(amount<0 for amount in taxes.values()) or refund_tax>remaining_tax:fail('Return tax exceeds the remaining posted sale tax',409)
    tax_lines=[];unassigned=refund_tax
    for index,(ledger,remaining) in enumerate(sorted(taxes.items())):
        amount=min(remaining,unassigned) if index==len(taxes)-1 else min(remaining,unassigned,
            (refund_tax*remaining/remaining_tax).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if remaining_tax else Decimal(0)
        if amount:tax_lines.append((ledger,amount,Decimal(0),None));unassigned-=amount
    if unassigned:fail('Return tax cannot be reconciled to original tax ledgers',409)
    receipts=connection.execute(select(SRMReceipt.__table__).join(POSCheckoutPayment.__table__,
        POSCheckoutPayment.receipt_id==SRMReceipt.id).where(POSCheckoutPayment.checkout_id==checkout.id,
        POSCheckoutPayment.organization_id==company,POSCheckoutPayment.branch_id==scope.branch_id,
        POSCheckoutPayment.scope_context_key==scope.context_id,SRMReceipt.organization_id==company,
        SRMReceipt.customer_id==checkout.customer_id,SRMReceipt.currency==checkout.currency,
        SRMReceipt.payment_method==source.refund_method,SRMReceipt.status.in_(('confirmed','allocated')))).mappings().all()
    if sum((Decimal(row['amount']) for row in receipts),Decimal(0))-sum((Decimal(old['refund_amount']) for old in prior if old['refund_method']==source.refund_method),Decimal(0))<source.refund_amount:
        fail('Refund exceeds the original collected amount for this payment method',409)
    funding=set()
    for receipt in receipts:
        _,receipt_lines=posted('receipt',receipt['id'],receipt['amount'])
        incoming=[line for line in receipt_lines if Decimal(line['debit_amount'] or 0)>0]
        outgoing=[line for line in receipt_lines if Decimal(line['credit_amount'] or 0)>0]
        if len(incoming)!=1 or len(outgoing)!=1 or outgoing[0]['ledger_id']!=party_ledger or outgoing[0]['party_id']!=party_id:
            fail('Original receipt posting cannot fund this refund',409)
        funding.add(incoming[0]['ledger_id'])
    if len(funding)!=1:fail('Select a refund method with one original posted funding ledger',409)
    funding_id=next(iter(funding));ledger_ids.add(funding_id)
    today=date.today()
    years=rows(fam.FAMFinancialYear,fam.FAMFinancialYear.company_id==company,
        fam.FAMFinancialYear.start_date<=today,fam.FAMFinancialYear.end_date>=today)
    if len(years)!=1 or years[0]['status'] in ('closed','locked'):fail('An open Accounting financial year is required for the refund date',409)
    periods=rows(fam.FAMAccountingPeriod,fam.FAMAccountingPeriod.financial_year_id==years[0]['id'],
        fam.FAMAccountingPeriod.start_date<=today,fam.FAMAccountingPeriod.end_date>=today)
    if len(periods)>1 or periods and periods[0]['status'] in ('closed','locked'):fail('The refund accounting period is unavailable',409)
    types=rows(fam.FAMVoucherType,fam.FAMVoucherType.company_id==company,fam.FAMVoucherType.active.is_(True),
        fam.FAMVoucherType.voucher_type_code.in_(('CN','PV')))
    kinds={row['voucher_type_code']:row for row in types}
    if set(kinds)!={'CN','PV'} or kinds['CN']['category']!='credit_note' or kinds['PV']['category']!='payment':
        fail('Configure native CN credit-note and PV payment voucher types before refunding',409)
    # Canonical ledgers and number sequences are locked in the shared company
    # resource; there is no duplicate balance or series for a Business Pack.
    snapshots=[]
    for model,criteria in ((fam.FAMCompanyFinancialSettings,(fam.FAMCompanyFinancialSettings.company_id==company,)),
        (fam.FAMFinancialYear,(fam.FAMFinancialYear.id==years[0]['id'],)),
        (fam.FAMAccountingPeriod,(fam.FAMAccountingPeriod.id.in_([row['id'] for row in periods]),)),
        (fam.FAMParty,(fam.FAMParty.id==party_id,fam.FAMParty.company_id==company)),
        (fam.FAMVoucherType,(fam.FAMVoucherType.id.in_([row['id'] for row in types]),fam.FAMVoucherType.company_id==company)),
        (fam.FAMLedger,(fam.FAMLedger.id.in_(ledger_ids),fam.FAMLedger.company_id==company,fam.FAMLedger.active.is_(True)))):
        fetched=connection.execute(select(model.__table__).where(*criteria).with_for_update()).mappings().all()
        snapshots.extend((model,dict(row)) for row in fetched)
    if {row['id'] for model,row in snapshots if model is fam.FAMLedger}!=ledger_ids:fail('Refund funding ledger is inactive or unavailable',409)
    from app.shared.models import ServicePolicy
    policies=rows(ServicePolicy,ServicePolicy.organization_id==company,ServicePolicy.module_key=='fam',
        ServicePolicy.kind=='transaction_lock',ServicePolicy.scope_key.in_([f'fam-lock:{company}:{part}' for part in ('all','sales','banking')]))
    credit_lines=([(sale['ledger_id'],Decimal(source.net_amount),Decimal(0),None)] if source.net_amount else [])+tax_lines+[(party_ledger,Decimal(0),Decimal(source.refund_amount),party_id)]
    payment_lines=[(party_ledger,Decimal(source.refund_amount),Decimal(0),party_id),(funding_id,Decimal(0),Decimal(source.refund_amount),None)]
    plan=PostingPlan(source.id,company,scope.branch_id,scope.context_id,actor.id,years[0]['id'],
        periods[0]['id'] if periods else None,party_id,today,'RET-'+str(source.id),Decimal(source.refund_amount),
        (VoucherSpec('CN',kinds['CN']['id'],'credit_note',tuple(credit_lines)),
         VoucherSpec('PV',kinds['PV']['id'],'payment',tuple(payment_lines))),tuple(snapshots),tuple(row['id'] for row in policies))
    return _certify(plan,db,scope,actor,source)
