"""Finite native FAM posting lease for a proven original-sale return.

No public switch and no company-table grant: the lease is registered only for
one session, scope, actor and immutable server-computed posting plan.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
from weakref import WeakKeyDictionary, ref
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import with_loader_criteria
from app.apps.fam import models as fam

_ACTIVE = WeakKeyDictionary()
_PLANS = {}
_VOUCHER_LINKS = WeakKeyDictionary()
_EMAILS = WeakKeyDictionary()


def _certify(plan,db,scope,actor,source):
    """Only the closed source-plan builder calls this; never a request flag."""
    state=inspect(source)
    if state.session is not db or not state.persistent or state.identity!=(plan.return_id,):fail()
    if len(plan.specs)!=2 or tuple((spec.code,spec.category) for spec in plan.specs)!=(('CN','credit_note'),('PV','payment')):
        fail('A return must use exactly one native credit note and one native payment voucher')
    if len({spec.type_id for spec in plan.specs})!=2:fail()
    for spec in plan.specs:
        if len(spec.lines)<2 or any(debit<0 or credit<0 or bool(debit)==bool(credit)
                or party not in (None,plan.party_id) for ledger,debit,credit,party in spec.lines):fail()
        if sum(line[1] for line in spec.lines)!=plan.amount or sum(line[2] for line in spec.lines)!=plan.amount:fail()
    ident=id(plan)
    _PLANS[ident]=(ref(plan,lambda ignored:_PLANS.pop(ident,None)),ref(db),scope,actor.id,source,sha256(repr(plan).encode()).digest())
    return plan


def fail(message='Native return accounting purpose is unavailable', status=403):
    raise HTTPException(status,message)


@dataclass(frozen=True)
class VoucherSpec:
    code: str
    type_id: int
    category: str
    lines: tuple  # (ledger_id, debit, credit, party_id)


@dataclass(frozen=True)
class PostingPlan:
    return_id: int
    company_id: int
    branch_id: int
    context_id: int
    actor_id: int
    financial_year_id: int
    period_id: int | None
    party_id: int
    posting_date: object
    reference: str
    amount: Decimal
    specs: tuple[VoucherSpec,...]
    snapshots: tuple  # (mapped native type, immutable row projection)
    lock_policy_ids: tuple[int,...]


def authority(db,actor,scope,*,write=True):
    from app.apps.srm.service_checkout import _authority
    from app.apps.fam.access import FAM_SRM_POSTING_MANAGE_PERMISSIONS
    from app.apps.srm.services.commercial import require
    from app.access.service import check_background_access
    company,branch,current=_authority(db,actor,payments=True,write=write)
    if current is None or current!=scope or current.pack_key!='retail':fail()
    if 'retail.returns.approve' not in current.capabilities:fail('Assigned Retail role cannot approve returns')
    require(actor,*FAM_SRM_POSTING_MANAGE_PERMISSIONS)
    check_background_access(db,actor,'fam','create' if write else 'view')
    if write:check_background_access(db,actor,'fam','approve')
    if (company,branch)!=(scope.company_id,scope.branch_id):fail()


@dataclass
class _Lease:
    db: object
    scope: object
    actor: object
    plan: PostingPlan
    vouchers: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    entries: list = field(default_factory=list)
    audit_rows: list = field(default_factory=list)
    active_spec: VoucherSpec | None = None
    active_voucher: object = None

    def ids(self):
        from app.shared.models import ServicePolicy
        result={model:set() for model in (fam.FAMCompanyFinancialSettings,fam.FAMFinancialYear,
            fam.FAMAccountingPeriod,fam.FAMParty,fam.FAMVoucherType,fam.FAMLedger)}
        for model,row in self.plan.snapshots:result[model].add(row['id'])
        result[ServicePolicy]=set(self.plan.lock_policy_ids)
        for model,rows in ((fam.FAMVoucher,self.vouchers),(fam.FAMVoucherLine,self.lines),
                           (fam.FAMLedgerEntry,self.entries)):
            result[model]={row.id for row in rows if row.id is not None}
        return result

    def assert_current(self):
        if _ACTIVE.get(self.db) is not self or self.db.info.get('business_pack_scope') is not self.scope:
            fail('Native return accounting lease is no longer active')
        permit=_PLANS.get(id(self.plan))
        if permit is None or sha256(repr(self.plan).encode()).digest()!=permit[5]:
            fail('Certified native posting plan changed')
        with self.db.no_autoflush:
            authority(self.db,self.actor,self.scope)
        source=_PLANS[id(self.plan)][4]
        from .models import RetailReturn
        keys=('organization_id','branch_id','pack_context_id','checkout_id','sales_order_id','invoice_id',
              'created_by','collection_session_id','refund_method','net_amount','tax_amount','refund_amount')
        actual=self.db.connection().execute(select(*(RetailReturn.__table__.c[key] for key in keys)).where(
            RetailReturn.id==self.plan.return_id)).mappings().first()
        if actual is None or any(actual[key]!=getattr(source,key) for key in keys):
            fail('Certified return source changed')
        # The enclosing PackBoundary checks grant/context revisions first. Also
        # reject config or source mutations in the identity map before native
        # helpers can reuse an already-loaded instance.
        for model,original in self.plan.snapshots:
            cached=self.db.identity_map.get((model,(original['id'],),None))
            mutable={'current_balance_dr','current_balance_cr','updated_at'} if model is fam.FAMLedger else {'numbering_sequence','updated_at'} if model is fam.FAMVoucherType else set()
            persisted=self.db.connection().execute(select(model.__table__).where(model.id==original['id'])).mappings().first()
            if persisted is None or any(persisted[key]!=value for key,value in original.items() if key not in mutable):
                fail('Certified accounting configuration changed')
            if cached is None:continue
            state=inspect(cached)
            for key,value in original.items():
                if key in mutable:continue
                if state.attrs[key].history.has_changes():fail('Native accounting configuration changed during return')
                if key not in state.unloaded and getattr(cached,key)!=value:fail('Native accounting identity differs from the posting plan')


@contextmanager
def _lease(db,actor,scope,plan):
    if db in _ACTIVE:fail('Native financial purposes cannot be nested')
    permit=_PLANS.get(id(plan))
    if permit is None or permit[0]() is not plan or permit[1]() is not db or permit[2] is not scope or permit[3]!=actor.id:
        fail('Return accounting requires its original certified source plan')
    source=permit[4]
    from .models import RetailReturn
    from app.apps.srm.service_checkout import _source_scope
    if type(source) is not RetailReturn or inspect(source).session is not db or source.state!='draft':fail()
    _source_scope(db,scope,plan.company_id,plan.branch_id,RetailReturn,plan.return_id)
    if any(inspect(source).attrs[key].history.has_changes() for key in ('organization_id','branch_id','pack_context_id','checkout_id','invoice_id','refund_amount')):fail()
    if (source.organization_id,source.branch_id,source.pack_context_id,source.created_by,Decimal(source.refund_amount))!=(
            plan.company_id,plan.branch_id,plan.context_id,plan.actor_id,plan.amount):fail()
    authority(db,actor,scope)
    if (plan.company_id,plan.branch_id,plan.context_id,plan.actor_id)!=(scope.company_id,scope.branch_id,scope.context_id,actor.id):fail()
    # Starting with arbitrary pending financial writes must never make them
    # eligible just because an otherwise valid return begins posting.
    financial_types={model for model,_ in plan.snapshots}|{fam.FAMVoucher,fam.FAMVoucherLine,fam.FAMLedgerEntry,fam.FAMVoucherAuditLog,fam.FAMAuditLog}
    if any(type(row) in financial_types for row in db.new|db.dirty|db.deleted):
        fail('Complete other financial changes before posting this return')
    lease=_Lease(db,scope,actor,plan)
    _ACTIVE[db]=lease
    try:
        lease.assert_current()
        yield lease
    finally:
        if _ACTIVE.get(db) is lease:del _ACTIVE[db]


def _restrict(execution,scope):
    """Called by the installed pack guard; no lease means no exception."""
    lease=_ACTIVE.get(execution.session)
    if lease is None:return False
    if lease.scope is not scope:fail()
    if not execution.is_orm_statement or not execution.is_select:return False
    from app.business_packs.common_queries import assert_mapped_sources
    from sqlalchemy.sql import visitors
    allowed=lease.ids()
    present=set()
    for node in visitors.iterate(execution.statement):
        for key in ('parentmapper','parententity'):
            entity=getattr(node,'_annotations',{}).get(key)
            mapped=inspect(entity,raiseerr=False) if entity is not None else None
            present.add(getattr(getattr(mapped,'mapper',mapped),'class_',None))
    financial={model for model in present if model in allowed}
    if not financial:return False
    lease.assert_current()
    # Retain exact structural source auditing. A mapper occurrence cannot
    # authorize an extra raw table, unrelated alias, subquery or literal SQL.
    assert_mapped_sources(execution.statement,frozenset(allowed))
    for model in financial:
        execution.statement=execution.statement.options(with_loader_criteria(
            model,model.id.in_(tuple(allowed[model])),include_aliases=True,propagate_to_loaders=False))
    return True


def _line_tuple(row):
    return (row.ledger_id,Decimal(row.debit_amount or 0),Decimal(row.credit_amount or 0),row.party_id)


def _derived_delivery(db,scope,item):
    from app.models.email_outbox import EmailOutbox
    if type(item) is not EmailOutbox:return False
    source=getattr(item,'_suite_source_record',None)
    if type(source) is not fam.FAMVoucher:return False
    lease=_ACTIVE.get(db)
    if lease is None or lease.scope is not scope:fail('Native voucher delivery requires its active return posting lease')
    lease.assert_current()
    state=inspect(source)
    if source not in lease.vouchers or state.session is not db or not state.persistent or source in db.deleted:
        fail('Native return delivery requires its actual issued voucher')
    plan=lease.plan
    if (source.company_id,source.source_module,source.source_record_type,str(source.source_record_id),
            source.posted_by,source.status,Decimal(source.total_debit),Decimal(source.total_credit))!=(
            plan.company_id,'srm','retail_return',str(plan.return_id),plan.actor_id,'posted',plan.amount,plan.amount):fail()
    from app.models.user import User
    user=User.__table__
    recipient=db.connection().execute(select(user.c.email).where(user.c.id==plan.actor_id,user.c.is_active.is_(True))).scalar_one_or_none()
    from app.core.config import settings
    body=f'Accounting voucher #{source.id} has an update.\nCurrent status: posted.\nSign in to review details: {settings.FRONTEND_PUBLIC_URL.rstrip("/")}/fam'
    import re
    event_suffix=sha256((recipient or '').casefold().encode()).hexdigest()
    if (item.organization_id,item.module,item.recipient_user_id,item.recipient,item.subject,item.body,item.is_html)!=(
            plan.company_id,'fam',plan.actor_id,recipient,'Accounting voucher: posted',body,False):
        fail('Native return delivery differs from the canonical voucher event')
    if not re.fullmatch(r'event:[0-9a-f]{32}:'+event_suffix,item.event_key or ''):fail()
    columns=('event_key','organization_id','module','recipient_user_id','recipient','subject','body','is_html')
    snapshot=tuple(getattr(item,key) for key in columns)
    previous=_EMAILS.get(item)
    if previous is None:
        if item not in db.new:fail('Native voucher delivery cannot adopt an existing row')
        _EMAILS[item]=(ref(lease),source,snapshot)
    elif previous[0]() is not lease or previous[1] is not source or previous[2]!=snapshot:fail()
    return True


def _reference(db,scope,item,parent,pairs):
    from .models import RetailReturn
    if type(item) is not RetailReturn or parent is not fam.FAMVoucher.__table__:
        return False
    if len(pairs)!=1 or pairs[0][0] not in ('credit_voucher_id','refund_voucher_id'):
        return False
    proof=_VOUCHER_LINKS.get(item)
    if proof is None or proof[0]() is not db or proof[1] is not scope or inspect(item).session is not db:
        fail('Return accounting references require the completed native posting lease')
    field=pairs[0][0];index=0 if field=='credit_voucher_id' else 1
    ident=getattr(item,field)
    if ident!=proof[2][index] or (item.organization_id,item.branch_id,item.pack_context_id)!=(scope.company_id,scope.branch_id,scope.context_id):fail()
    table=fam.FAMVoucher.__table__;kind=fam.FAMVoucherType.__table__
    row=db.connection().execute(select(table.c.id).join(kind,kind.c.id==table.c.voucher_type_id).where(
        table.c.id==ident,table.c.company_id==scope.company_id,table.c.source_module=='srm',
        table.c.source_record_type=='retail_return',table.c.source_record_id==str(item.id),table.c.status=='posted',
        table.c.total_debit==item.refund_amount,table.c.total_credit==item.refund_amount,
        kind.c.company_id==scope.company_id,kind.c.voucher_type_code==('CN' if index==0 else 'PV'),
        kind.c.category==('credit_note' if index==0 else 'payment'))).first()
    if row is None:fail('Generated native refund voucher source changed')
    return True


def _write(db,scope,row):
    lease=_ACTIVE.get(db)
    if lease is None:return False
    known={fam.FAMVoucher,fam.FAMVoucherLine,fam.FAMLedgerEntry,fam.FAMLedger,fam.FAMVoucherType,fam.FAMVoucherAuditLog,fam.FAMAuditLog}
    if type(row) not in known:return False
    if lease.scope is not scope:fail()
    lease.assert_current()
    if row in db.deleted:fail('Return posting cannot delete financial history')
    plan=lease.plan
    if type(row) is fam.FAMVoucher:
        if row not in db.new and row not in lease.vouchers:fail()
        if row not in db.new and any(inspect(row).attrs[attr.key].history.has_changes() for attr in inspect(row).mapper.column_attrs):fail('Issued native refund vouchers cannot be rewritten')
        spec=lease.active_spec
        if spec is None or (row.company_id,row.voucher_type_id,row.financial_year_id,row.accounting_period_id,
                row.source_module,row.source_record_type,str(row.source_record_id),row.posted_by,row.status,
                row.voucher_date,row.reference_number)!=(plan.company_id,spec.type_id,plan.financial_year_id,
                plan.period_id,'srm','retail_return',str(plan.return_id),plan.actor_id,'posted',plan.posting_date,plan.reference):fail()
        if Decimal(row.total_debit)!=plan.amount or Decimal(row.total_credit)!=plan.amount:fail()
        original=next((value for model,value in plan.snapshots if model is fam.FAMVoucherType and value['id']==spec.type_id),None)
        if original is None or row.voucher_number!=f"{original['numbering_prefix']}-{int(original['numbering_sequence'] or 1):05d}":fail()
        if row.narration!='Original-sale Retail return '+plan.reference or any(getattr(row,key) is not None for key in ('branch_id','reference_date','cancelled_by','cancelled_at','cancellation_reason','reversed_voucher_id')):fail()
        if any(other is not row and other.voucher_type_id==spec.type_id for other in lease.vouchers):fail()
        if row not in lease.vouchers:lease.vouchers.append(row)
        lease.active_voucher=row
    elif type(row) is fam.FAMVoucherLine:
        if row not in db.new and row not in lease.lines:fail()
        if row not in db.new and any(inspect(row).attrs[attr.key].history.has_changes() for attr in inspect(row).mapper.column_attrs):fail()
        voucher=lease.active_voucher;spec=lease.active_spec
        if voucher is None or row.voucher_id!=voucher.id or not 1<=row.line_number<=len(spec.lines):fail()
        if _line_tuple(row)!=spec.lines[row.line_number-1] or row.narration!='Original-sale Retail return '+plan.reference or any(getattr(row,key) is not None for key in ('cost_center_id','branch_id','tax_component_id')):fail()
        if any(other is not row and (other.voucher_id,other.line_number)==(row.voucher_id,row.line_number) for other in lease.lines):fail()
        if row not in lease.lines:lease.lines.append(row)
    elif type(row) is fam.FAMLedgerEntry:
        source=next((line for line in lease.lines if line.id==row.voucher_line_id),None)
        voucher=next((item for item in lease.vouchers if item.id==row.voucher_id),None)
        if row not in db.new and row not in lease.entries:fail()
        if source is None or voucher is None or (row.company_id,row.financial_year_id,row.accounting_period_id,
                row.source_module,row.source_record_type,str(row.source_record_id),row.voucher_number,row.voucher_date)!=(
                plan.company_id,plan.financial_year_id,plan.period_id,'srm','retail_return',str(plan.return_id),voucher.voucher_number,plan.posting_date):fail()
        if (row.ledger_id,Decimal(row.debit_amount or 0),Decimal(row.credit_amount or 0))!=_line_tuple(source)[:3]:fail()
        if any(other is not row and other.voucher_line_id==row.voucher_line_id for other in lease.entries):fail()
        original=next((value for model,value in plan.snapshots if model is fam.FAMLedger and value['id']==row.ledger_id),None)
        if original is None:fail()
        order={voucher.id:index for index,voucher in enumerate(lease.vouchers)}
        position=(order[row.voucher_id],source.line_number)
        cumulative=Decimal(original['current_balance_dr'] or 0)-Decimal(original['current_balance_cr'] or 0)
        seen=set()
        for entry in [*lease.entries,*(item for item in db.new if type(item) is fam.FAMLedgerEntry)]:
            if entry.voucher_line_id in seen:continue
            seen.add(entry.voucher_line_id)
            native_line=next((line for line in lease.lines if line.id==entry.voucher_line_id),None)
            if native_line is not None and native_line.ledger_id==row.ledger_id and (order.get(native_line.voucher_id,10**12),native_line.line_number)<=position:
                cumulative+=Decimal(native_line.debit_amount or 0)-Decimal(native_line.credit_amount or 0)
        if Decimal(row.running_balance)!=cumulative:fail('Native return running balance differs from its ordered voucher entries')
        if row not in lease.entries:lease.entries.append(row)
    elif type(row) is fam.FAMLedger:
        original=next((value for model,value in plan.snapshots if model is fam.FAMLedger and value['id']==row.id),None)
        if original is None or row in db.new:fail()
        changed={attr.key for attr in inspect(row).mapper.column_attrs if inspect(row).attrs[attr.key].history.has_changes()}
        if not changed<={'current_balance_dr','current_balance_cr'}:fail()
        entries=list(lease.entries)
        for item in db.new:
            if type(item) is fam.FAMLedgerEntry and item not in entries:
                _write(db,scope,item);entries.append(item)
        for name,entry_name in (('current_balance_dr','debit_amount'),('current_balance_cr','credit_amount')):
            expected=Decimal(original[name] or 0)+sum((Decimal(getattr(item,entry_name) or 0) for item in entries if item.ledger_id==row.id),Decimal(0))
            if Decimal(getattr(row,name) or 0)!=expected:fail('Native return ledger movement differs from its voucher source')
    elif type(row) is fam.FAMVoucherType:
        original=next((value for model,value in plan.snapshots if model is fam.FAMVoucherType and value['id']==row.id),None)
        if original is None or row in db.new:fail()
        changed={attr.key for attr in inspect(row).mapper.column_attrs if inspect(row).attrs[attr.key].history.has_changes()}
        if not changed<={'numbering_sequence'}:fail()
        if row.numbering_sequence!=original['numbering_sequence']+sum(item.voucher_type_id==row.id for item in lease.vouchers):fail()
    else:
        if row not in db.new:fail('Return accounting audit history is append-only')
        if row.performed_by!=plan.actor_id or row.old_value_json is not None:fail()
        voucher_id=row.voucher_id if type(row) is fam.FAMVoucherAuditLog else row.record_id
        voucher=next((item for item in lease.vouchers if item.id==voucher_id),None)
        if voucher is None:fail()
        if type(row) is fam.FAMAuditLog and (row.company_id,row.module_name,row.record_type,row.action)!=(plan.company_id,'fam','voucher','POST_FROM_SRM'):fail()
        if type(row) is fam.FAMVoucherAuditLog and row.action!='CREATE_POSTED_FROM_SRM':fail()
        snapshot=row.new_value_json or {}
        if snapshot.get('id')!=voucher.id or snapshot.get('source_record_type')!='retail_return' or str(snapshot.get('source_record_id'))!=str(plan.return_id):fail()
        lease.audit_rows.append(row)
    return True


def post(plan,db,actor,request,scope):
    """Execute only the two reviewed native vouchers; caller owns transaction."""
    from app.apps.fam.api.router import create_and_post_voucher,validate_voucher_payload
    from app.apps.fam.schemas import VoucherPayload
    result=[]
    with _lease(db,actor,scope,plan) as lease:
        for spec in plan.specs:
            lease.active_spec=spec;lease.active_voucher=None
            lines=[dict(ledger_id=ledger,debit_amount=debit,credit_amount=credit,party_id=party,
                narration='Original-sale Retail return '+plan.reference) for ledger,debit,credit,party in spec.lines]
            payload=VoucherPayload(financial_year_id=plan.financial_year_id,accounting_period_id=plan.period_id,
                voucher_type_id=spec.type_id,voucher_date=plan.posting_date,lines=lines)
            validate_voucher_payload(db,plan.company_id,payload,for_posting=True)
            voucher=create_and_post_voucher(db,request,actor,plan.company_id,spec.code,plan.posting_date,
                plan.reference,'Original-sale Retail return '+plan.reference,'retail_return',plan.return_id,lines)
            db.flush();result.append(voucher.id)
        _VOUCHER_LINKS[_PLANS[id(plan)][4]]=(ref(db),scope,tuple(result))
    return tuple(result)
