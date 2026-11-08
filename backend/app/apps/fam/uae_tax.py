"""UAE working papers; preserves India GST/TDS and never submits tax returns.

Sources: FTA VAT Returns User Guide and Corporate Tax General Guide.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.fam.access import FAM_GST_VIEW_PERMISSIONS, FAM_GST_RETURN_PREPARE_PERMISSIONS, FAM_SETTINGS_PERMISSIONS
from app.shared.models import ServicePolicy

router = APIRouter(prefix='/uae-tax', tags=['UAE tax working papers'])
BOXES = {'1a':'Abu Dhabi','1b':'Dubai','1c':'Sharjah','1d':'Ajman','1e':'Umm Al Quwain','1f':'Ras Al Khaimah','1g':'Fujairah','2':'Tourist refunds','3':'Reverse charge outputs','4':'Zero-rated supplies','5':'Exempt supplies','6':'Goods imported','7':'Import adjustments','9':'Standard-rated expenses','10':'Recoverable reverse charge'}

def rounded(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class UAETaxSettings(BaseModel):
    trn: str = Field(pattern=r'^[0-9]{15}$')
    emirate: Literal['1a','1b','1c','1d','1e','1f','1g']
    output_vat_ledger_id: int = Field(gt=0)
    input_vat_ledger_id: int = Field(gt=0)

def tax_settings(db, company_id):
    row=db.query(ServicePolicy).filter_by(scope_key=f'uae-tax-settings:{company_id}',organization_id=company_id,kind='uae_tax_settings').first()
    return row.values_json if row else None

def output_vat_ledger(db, company_id):
    from app.apps.fam.models import FAMLedger
    values=tax_settings(db,company_id)
    ledger=db.query(FAMLedger).filter_by(company_id=company_id,id=values['output_vat_ledger_id'],active=True).first() if values else None
    if not ledger or ledger.nature != 'liability' or ledger.ledger_type != 'tax':
        raise HTTPException(422,'Configure an active output VAT liability ledger in UAE tax settings before posting')
    return ledger


def input_vat_ledger(db, company_id):
    from app.apps.fam.models import FAMLedger
    values = tax_settings(db, company_id)
    ledger = db.query(FAMLedger).filter_by(company_id=company_id,
        id=values['input_vat_ledger_id'], active=True).first() if values else None
    if not ledger or ledger.nature != 'asset' or ledger.ledger_type != 'tax':
        raise HTTPException(422, 'Configure an active input VAT asset ledger in UAE tax settings before posting')
    return ledger

@router.get('/settings')
def read_settings(db:Session=Depends(get_db),user=Depends(RequirePermission(*(FAM_GST_VIEW_PERMISSIONS | FAM_SETTINGS_PERMISSIONS)))):
    from app.apps.fam.api.router import bootstrap
    from app.apps.fam.models import FAMLedger
    ident=bootstrap(db,user)
    return {'settings':tax_settings(db,ident),'ledgers':[{'id':r.id,'name':r.ledger_name,'nature':r.nature} for r in db.query(FAMLedger).filter_by(company_id=ident,active=True,ledger_type='tax').all()]}

@router.put('/settings')
def configure(data:UAETaxSettings,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap,audit
    from app.apps.fam.models import FAMLedger
    ident=bootstrap(db,user)
    for ledger_id,nature in [(data.output_vat_ledger_id,'liability'),(data.input_vat_ledger_id,'asset')]:
        if not db.query(FAMLedger).filter_by(id=ledger_id,company_id=ident,nature=nature,ledger_type='tax',active=True).first():
            raise HTTPException(422,'Select active VAT tax ledgers in the current company with the correct asset/liability nature')
    key=f'uae-tax-settings:{ident}'
    row=db.query(ServicePolicy).filter_by(scope_key=key,organization_id=ident).with_for_update().first()
    before=row.values_json if row else None
    values=data.model_dump(mode='json')
    if row: row.values_json=values;row.updated_by=user.id;row.version+=1
    else: row=ServicePolicy(scope_key=key,organization_id=ident,module_key='fam',kind='uae_tax_settings',values_json=values,updated_by=user.id);db.add(row)
    db.flush();audit(db,request,user,ident,'uae_tax_settings',row.id,'CONFIGURE',before,values);db.commit()
    return values

class VATCalculation(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    inclusive: bool = False
    treatment: Literal['standard','zero_rated','exempt'] = 'standard'

def calculate_vat(data):
    rate = Decimal('0.05') if data.treatment == 'standard' else Decimal('0')
    tax = rounded(data.amount * rate / (1 + rate)) if data.inclusive else rounded(data.amount * rate)
    net = data.amount - tax if data.inclusive else data.amount
    return {'net':str(net),'vat':str(tax),'gross':str(net+tax),'currency':'AED'}

class VATBox(BaseModel):
    box: Literal['1a','1b','1c','1d','1e','1f','1g','2','3','4','5','6','7','9','10']
    amount: Decimal = Field(default=Decimal('0'), max_digits=14, decimal_places=2)
    vat: Decimal = Field(default=Decimal('0'), max_digits=14, decimal_places=2)
    adjustment: Decimal = Field(default=Decimal('0'), max_digits=14, decimal_places=2)
    @model_validator(mode='after')
    def check(self):
        if self.box == '2' and (self.amount > 0 or self.vat > 0 or self.adjustment != 0):
            raise ValueError('Tourist refunds must be negative; box 2 has no adjustments')
        if self.box in {'4','5'} and (self.vat != 0 or self.adjustment != 0):
            raise ValueError('Zero-rated and exempt boxes cannot contain VAT or VAT adjustments')
        return self

class VATWorking(BaseModel):
    expected_version: int = Field(default=0, ge=0)
    period_start: date
    period_end: date
    rows: list[VATBox] = Field(default_factory=list, max_length=1000)
    reconciliation_note: str = Field(default='', max_length=4000)
    @model_validator(mode='after')
    def check(self):
        if self.period_end < self.period_start:
            raise ValueError('End date must follow start date')
        return self

def vat201(data):
    boxes = {key:{'amount':Decimal('0'),'vat':Decimal('0'),'adjustment':Decimal('0')} for key in BOXES}
    for row in data.rows:
        for field in ('amount','vat','adjustment'):
            boxes[row.box][field] += getattr(row, field)
    output = sum((v['vat']+v['adjustment'] for k,v in boxes.items() if k not in {'9','10'}), Decimal('0'))
    inputs = sum((boxes[k]['vat']+boxes[k]['adjustment'] for k in ('9','10')), Decimal('0'))
    return {'status':'draft_working','currency':'AED','boxes':{k:{**{f:str(rounded(v)) for f,v in values.items()},'label':BOXES[k]} for k,values in boxes.items()},'output_vat':str(rounded(output)),'recoverable_vat':str(rounded(inputs)),'net_vat_due':str(rounded(output-inputs)),'standard_due_date':(data.period_end+timedelta(days=28)).isoformat(),'filing_status':'not_submitted'}

class CorporateTax(BaseModel):
    adjusted_taxable_income: Decimal = Field(max_digits=14, decimal_places=2)
    regime: Literal['standard','qualifying_free_zone','small_business_relief','exempt','dmtt']

def corporate_tax(data):
    if data.regime != 'standard':
        raise HTTPException(422,'This regime needs a regime-specific assessment; the ordinary calculation was not applied')
    taxable = max(Decimal('0'), data.adjusted_taxable_income - Decimal('375000'))
    return {'status':'draft_estimate','currency':'AED','adjusted_taxable_income':str(data.adjusted_taxable_income),'zero_rate_band':'375000.00','taxable_at_nine_percent':str(rounded(taxable)),'estimated_tax':str(rounded(taxable*Decimal('0.09'))),'filing_status':'not_submitted'}

@router.get('/reference')
def reference(user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return {'boxes':BOXES,'standard_vat_rate':'5','ordinary_ct_threshold':'375000','ordinary_ct_rate':'9','currency':'AED'}

@router.post('/calculate-vat')
def preview_vat(data:VATCalculation, user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return calculate_vat(data)

@router.post('/corporate-tax/preview')
def preview_ct(data:CorporateTax, user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return corporate_tax(data)

@router.post('/vat201/preview')
def preview_return(data:VATWorking, user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    return vat201(data)

@router.get('/vat201/workings')
def list_workings(db:Session=Depends(get_db), user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    ident=bootstrap(db,user)
    return [{'id':r.id,'version':r.version,'data':r.values_json} for r in db.query(ServicePolicy).filter_by(organization_id=ident,module_key='fam',kind='uae_vat_working').order_by(ServicePolicy.id.desc()).limit(100)]

@router.post('/vat201/workings')
def save_working(data:VATWorking, request:Request, db:Session=Depends(get_db), user=Depends(RequirePermission(*FAM_GST_RETURN_PREPARE_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap, audit
    ident=bootstrap(db,user)
    key=f'uae-vat201:{ident}:{data.period_start}:{data.period_end}'
    row=db.query(ServicePolicy).filter_by(scope_key=key,organization_id=ident).with_for_update().first()
    if data.expected_version != (row.version if row else 0):
        raise HTTPException(409,'This VAT working changed. Load the saved period and review it before saving')
    before=row.values_json if row else None
    values={'input':data.model_dump(mode='json'),'result':vat201(data)}
    if row:
        row.values_json=values
        row.version+=1
        row.updated_by=user.id
    else:
        row=ServicePolicy(scope_key=key,organization_id=ident,module_key='fam',kind='uae_vat_working',values_json=values,updated_by=user.id)
        db.add(row)
    db.flush()
    audit(db,request,user,ident,'uae_vat_working',row.id,'SAVE_WORKING',before,values)
    db.commit()
    return {'id':row.id,'version':row.version,**values}


@router.get('/register')
def vat_account_register(period_start:date,period_end:date,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_GST_VIEW_PERMISSIONS))):
    """Reconcile manual VAT201 figures to effective postings in the mapped VAT accounts."""
    from app.apps.fam.api.router import bootstrap
    from app.apps.fam.models import FAMCompanyFinancialSettings,FAMLedgerEntry,FAMVoucher
    company=bootstrap(db,user)
    if period_start>period_end: raise HTTPException(422,'Choose an ordered VAT period')
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=company).one()
    if settings.country_code.upper() not in {'AE','UAE'} or settings.base_currency!='AED':
        raise HTTPException(422,'The UAE VAT account register requires a UAE company with AED base currency')
    output=output_vat_ledger(db,company)
    inputs=input_vat_ledger(db,company)
    entries=db.query(FAMLedgerEntry,FAMVoucher).join(FAMVoucher,FAMVoucher.id==FAMLedgerEntry.voucher_id).filter(
        FAMLedgerEntry.company_id==company,FAMVoucher.company_id==company,
        FAMVoucher.status.in_(['posted','reversed']),FAMLedgerEntry.voucher_date>=period_start,
        FAMLedgerEntry.voucher_date<=period_end,FAMLedgerEntry.ledger_id.in_([output.id,inputs.id])
    ).order_by(FAMLedgerEntry.voucher_date,FAMLedgerEntry.id).all()
    output_total=input_total=Decimal('0')
    rows=[]
    for entry,voucher in entries:
        is_output=entry.ledger_id==output.id
        amount=Decimal(entry.credit_amount or 0)-Decimal(entry.debit_amount or 0)
        if is_output: output_total+=amount
        else: amount=-amount;input_total+=amount
        rows.append({'date':entry.voucher_date.isoformat(),'voucher_id':voucher.id,'voucher_number':voucher.voucher_number,
            'reference':voucher.reference_number,'source_type':voucher.source_record_type,'source_id':voucher.source_record_id,
            'direction':'output' if is_output else 'recoverable_input','vat_amount':str(rounded(amount))})
    working=db.query(ServicePolicy).filter_by(organization_id=company,scope_key=f'uae-vat201:{company}:{period_start}:{period_end}',kind='uae_vat_working').first()
    comparison=None
    if working:
        prepared=working.values_json['result']
        comparison={'working_id':working.id,'working_version':working.version,
            'output_difference':str(rounded(Decimal(prepared['output_vat'])-output_total)),
            'recoverable_difference':str(rounded(Decimal(prepared['recoverable_vat'])-input_total)),
            'net_difference':str(rounded(Decimal(prepared['net_vat_due'])-(output_total-input_total)))}
    return {'currency':'AED','period_start':period_start,'period_end':period_end,'items':rows,
        'output_vat':str(rounded(output_total)),'recoverable_vat':str(rounded(input_total)),
        'net_vat':str(rounded(output_total-input_total)),'comparison':comparison,
        'basis':'Posted mapped VAT accounts. Review tax classifications, missing postings and adjustments before preparing or filing VAT201.'}
