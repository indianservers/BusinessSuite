"""Reviewed bank categorization using existing vouchers and reconciliation matches."""
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,RequirePermission
from app.shared.models import ServicePolicy
from app.apps.fam.access import FAM_BANKING_VIEW_PERMISSIONS,FAM_BANKING_MANAGE_PERMISSIONS,FAM_BANK_RECONCILE_PERMISSIONS,FAM_VOUCHER_POST_PERMISSIONS
from app.apps.srm.access import has_any_permission
from app.apps.fam.models import FAMBankAccount,FAMLedger,FAMBankStatement,FAMBankStatementLine,FAMVoucher,FAMLedgerEntry,FAMBankReconciliationMatch

router=APIRouter(prefix='/bank-rules',tags=['Bank transaction rules'])


class Rule(BaseModel):
    name:str=Field(min_length=1,max_length=150)
    bank_account_id:int=Field(gt=0)
    direction:Literal['withdrawal','deposit']
    field:Literal['description','reference_number']='description'
    operator:Literal['contains','equals','starts_with']='contains'
    text:str=Field(min_length=1,max_length=200)
    counter_ledger_id:int=Field(gt=0)
    minimum:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    maximum:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    priority:int=Field(default=100,ge=1,le=999)
    active:bool=True
    expected_version:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def valid(self):
        self.name=self.name.strip();self.text=self.text.strip()
        if not self.name or not self.text: raise ValueError('Enter a rule name and matching text')
        if self.minimum is not None and self.maximum is not None and self.minimum>self.maximum:
            raise ValueError('Minimum must not exceed maximum')
        return self


class Apply(BaseModel):
    rule_id:int=Field(gt=0)
    expected_version:int=Field(ge=1)
    line_hash:str=Field(min_length=1,max_length=128)


def rules(db,company):
    return db.query(ServicePolicy).filter_by(organization_id=company,module_key='fam',kind='bank_rule').all()


def public(row):
    return {'id':row.id,'version':row.version,**row.values_json}


def validate(db,company,data):
    bank=db.query(FAMBankAccount).filter_by(company_id=company,id=data.bank_account_id,active=True).first()
    counter=db.query(FAMLedger).filter_by(company_id=company,id=data.counter_ledger_id,active=True).first()
    if not bank or not counter: raise HTTPException(422,'Choose active bank and counter accounts in this company')
    expected='expense' if data.direction=='withdrawal' else 'income'
    if counter.nature!=expected or counter.ledger_type in {'customer','vendor','tax','bank','cash'}:
        raise HTTPException(422,'Use an expense account for withdrawals or an income account for deposits; use the existing tax and party workflows for other transactions')
    return bank,counter


def matches(values,line):
    debit,credit=Decimal(line.debit_amount or 0),Decimal(line.credit_amount or 0)
    if debit<0 or credit<0 or bool(debit)==bool(credit): return False
    if values['direction']!=('withdrawal' if debit else 'deposit'): return False
    amount=debit or credit
    if values.get('minimum') is not None and amount<Decimal(values['minimum']): return False
    if values.get('maximum') is not None and amount>Decimal(values['maximum']): return False
    actual=str(getattr(line,values['field']) or '').casefold()
    expected=values['text'].casefold()
    return expected in actual if values['operator']=='contains' else actual==expected if values['operator']=='equals' else actual.startswith(expected)


@router.get('')
def list_rules(db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    return sorted([public(r) for r in rules(db,bootstrap(db,user))],key=lambda r:(r['priority'],r['id']))


@router.get('/options')
def rule_options(db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    company=bootstrap(db,user)
    return {'ledgers':[{'id':row.id,'ledger_name':row.ledger_name,'nature':row.nature,'ledger_type':row.ledger_type,'active':True}
        for row in db.query(FAMLedger).filter(FAMLedger.company_id==company,FAMLedger.active.is_(True),FAMLedger.nature.in_(['income','expense']),
            FAMLedger.ledger_type.notin_(['tax','bank','cash','customer','vendor'])).order_by(FAMLedger.ledger_name).all()]}


@router.post('',status_code=201)
def create_rule(data:Rule,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap,audit
    from app.apps.srm.services.commercial import lock_tenant
    company=bootstrap(db,user);lock_tenant(db,user);validate(db,company,data)
    if data.expected_version: raise HTTPException(409,'A new bank rule must start at version zero')
    if any(r.values_json['name'].casefold()==data.name.casefold() for r in rules(db,company)):
        raise HTTPException(409,'A rule with this name already exists; edit the existing rule')
    row=ServicePolicy(scope_key=f'bank-rule:{company}:{uuid4()}',organization_id=company,module_key='fam',kind='bank_rule',updated_by=user.id,values_json=data.model_dump(mode='json',exclude={'expected_version'}))
    db.add(row);db.flush();audit(db,request,user,company,'bank_rule',row.id,'CREATE',None,public(row));db.commit()
    return public(row)


@router.put('/{ident}')
def update_rule(ident:int,data:Rule,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap,audit
    from app.apps.srm.services.commercial import lock_tenant
    company=bootstrap(db,user);lock_tenant(db,user);validate(db,company,data)
    row=db.query(ServicePolicy).filter_by(id=ident,organization_id=company,kind='bank_rule').with_for_update().first()
    if not row: raise HTTPException(404,'Bank rule not found')
    if row.version!=data.expected_version: raise HTTPException(409,'Bank rule changed; refresh before updating')
    if any(r.id!=ident and r.values_json['name'].casefold()==data.name.casefold() for r in rules(db,company)):
        raise HTTPException(409,'A rule with this name already exists')
    before=row.values_json;row.values_json=data.model_dump(mode='json',exclude={'expected_version'});row.version+=1;row.updated_by=user.id
    audit(db,request,user,company,'bank_rule',row.id,'UPDATE',before,public(row));db.commit()
    return public(row)


@router.get('/statements/{ident}/preview')
def preview(ident:int,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    company=bootstrap(db,user)
    statement=db.query(FAMBankStatement).filter_by(company_id=company,id=ident).first()
    if not statement: raise HTTPException(404,'Statement not found')
    available=sorted([r for r in rules(db,company) if r.values_json['active'] and r.values_json['bank_account_id']==statement.bank_account_id],key=lambda r:(r.values_json['priority'],r.id))
    result=[]
    for line in db.query(FAMBankStatementLine).filter_by(statement_id=ident,matched_status='unmatched').order_by(FAMBankStatementLine.id).all():
        rule=next((r for r in available if matches(r.values_json,line)),None)
        if rule:
            result.append({'line_id':line.id,'line_hash':line.line_hash,'date':line.transaction_date,'description':line.description,
                'amount':str(Decimal(line.debit_amount or 0) or Decimal(line.credit_amount or 0)),
                'rule_id':rule.id,'rule_version':rule.version,'rule_name':rule.values_json['name'],'counter_ledger_id':rule.values_json['counter_ledger_id']})
    return {'statement_id':ident,'suggestions':result}


@router.post('/lines/{ident}/apply')
def apply_rule(ident:int,data:Apply,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_BANKING_MANAGE_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap,create_and_post_voucher,audit
    from app.apps.srm.services.commercial import lock_tenant
    if not has_any_permission(user,FAM_VOUCHER_POST_PERMISSIONS) or not has_any_permission(user,FAM_BANK_RECONCILE_PERMISSIONS):
        raise HTTPException(403,'Voucher posting and bank reconciliation permissions are required to apply a bank rule')
    company=bootstrap(db,user);lock_tenant(db,user)
    pair=db.query(FAMBankStatementLine,FAMBankStatement).join(FAMBankStatement,FAMBankStatement.id==FAMBankStatementLine.statement_id).filter(FAMBankStatement.company_id==company,FAMBankStatementLine.id==ident).with_for_update().first()
    rule=db.query(ServicePolicy).filter_by(id=data.rule_id,organization_id=company,kind='bank_rule').with_for_update().first()
    if not pair or not rule: raise HTTPException(404,'Statement line or rule not found')
    line,statement=pair
    existing=db.query(FAMVoucher).filter_by(company_id=company,source_module='fam',source_record_type='bank_rule_line',source_record_id=str(ident)).first()
    if existing:
        if existing.status=='posted' and line.matched_voucher_id==existing.id:
            return {'voucher_id':existing.id,'idempotent':True}
        raise HTTPException(409,'This bank line was already categorized; review its original voucher')
    if rule.version!=data.expected_version or line.line_hash!=data.line_hash:
        raise HTTPException(409,'The preview changed; review the current rule and statement line')
    values=rule.values_json
    if line.matched_status!='unmatched' or not values['active'] or values['bank_account_id']!=statement.bank_account_id or not matches(values,line):
        raise HTTPException(409,'This line no longer qualifies for the selected bank rule')
    bank,counter=validate(db,company,Rule.model_validate(values))
    bank_ledger=db.query(FAMLedger).filter_by(company_id=company,id=bank.ledger_id,active=True).first()
    if not bank_ledger or bank_ledger.ledger_type!='bank': raise HTTPException(422,'The bank ledger is unavailable')
    withdrawal=values['direction']=='withdrawal'
    amount=Decimal(line.debit_amount or 0) or Decimal(line.credit_amount or 0)
    lines=[{'ledger_id':counter.id,'debit_amount':amount if withdrawal else 0,'credit_amount':0 if withdrawal else amount},
           {'ledger_id':bank.ledger_id,'debit_amount':0 if withdrawal else amount,'credit_amount':amount if withdrawal else 0}]
    voucher=create_and_post_voucher(db,request,user,company,'PV' if withdrawal else 'RV',line.transaction_date,
        line.reference_number or f'BANK-LINE-{line.id}',line.description,'bank_rule_line',line.id,lines,source_module='fam')
    db.flush()
    entry=db.query(FAMLedgerEntry).filter_by(company_id=company,voucher_id=voucher.id,ledger_id=bank.ledger_id).one()
    db.add(FAMBankReconciliationMatch(statement_line_id=line.id,voucher_id=voucher.id,ledger_entry_id=entry.id,
        match_type='confirmed',confidence_score=100,matched_amount=amount,matched_by=user.id))
    line.matched_status='matched';line.matched_voucher_id=voucher.id
    audit(db,request,user,company,'bank_rule',rule.id,'APPLY',None,{'statement_line_id':line.id,'voucher_id':voucher.id})
    db.commit()
    return {'voucher_id':voucher.id,'idempotent':False}
