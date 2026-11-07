from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.models.user import User
from app.access.api import company_access
from app.access.models import AccessPolicy
from app.apps.industry_packs import service

router = APIRouter(prefix='/industry-packs', tags=['Industry packs and onboarding'])
READ = RequirePermission('crm_view', 'crm_manage', 'crm_admin')
WRITE = RequirePermission('settings_manage', 'company_manage', 'crm_admin')


class Install(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_as_user_id: int = Field(gt=0, strict=True)
    modules: list[str] = Field(default_factory=lambda: ['crm'], max_length=8)
    expected_version: int | None = Field(None, ge=1)


@router.get('/catalog')
def catalog(user=Depends(READ)):
    return {'items': [{k: v for k, v in row.items() if k not in {'sampleDeals', 'futureAutomations', 'futureReports'}} for row in service.CATALOG.values()]}


@router.get('/installed')
def installed(db: Session = Depends(get_db), user=Depends(READ)):
    from app.models.platform import DomainPackRegistry
    company = user.organization_id
    rows = db.query(DomainPackRegistry).filter_by(company_id=company).all()
    return {'items': [service.output(row) for row in rows if (row.config_json or {}).get('kind') == 'industry_pack']}


@router.get('/execution-identities')
def identities(db: Session = Depends(get_db), user=Depends(WRITE)):
    company = user.organization_id
    company_access(db, user, company)
    result = []
    for policy in db.query(AccessPolicy).filter_by(company_id=company, status='active').all():
        try:
            person = service.identity(db, user, company, policy.user_id)
        except HTTPException:
            continue
        result.append({'id': person.id, 'name': person.email})
    return {'items': result}


@router.post('/{key}/preflight')
def preflight(key: str, data: Install, db: Session = Depends(get_db), user=Depends(WRITE)):
    return service.preflight(db, user, user.organization_id, key, data.run_as_user_id, data.modules)


@router.post('/{key}/install')
def install(key: str, data: Install, request: Request, db: Session = Depends(get_db), user=Depends(WRITE)):
    from app.shared.api import change
    change(db, user, user.organization_id, request)
    with db.begin_nested():
        result = service.install(db, user, user.organization_id, key, data.run_as_user_id, data.modules, data.expected_version)
    db.commit()
    return result


@router.post('/{key}/disable')
def disable(key: str, request: Request, db: Session = Depends(get_db), user=Depends(WRITE)):
    from app.shared.api import change
    change(db, user, user.organization_id, request)
    RequirePermission('automation_manage', 'automation_admin')(user)
    with db.begin_nested():
        result = service.disable(db, user, user.organization_id, key)
    db.commit()
    return result


@router.post('/{key}/sample-data')
def sample_data(key: str, request: Request, db: Session = Depends(get_db), user=Depends(WRITE)):
    from app.shared.api import change
    change(db, user, user.organization_id, request)
    company_access(db, user, user.organization_id)
    from app.apps.crm.api import router as crm
    from app.apps.crm.models import CRMDeal
    row = service.get_install(db, user.organization_id, key)
    if row.status != 'Enabled':
        raise HTTPException(409, 'Enable the pack before adding sample data')
    if row.config_json.get('sample_deal_ids'):
        return {'ids': row.config_json['sample_deal_ids'], 'created': False}
    db.query(service.Company).filter_by(id=user.organization_id).with_for_update().one()
    db.refresh(row)
    if row.config_json.get('sample_deal_ids'):
        return {'ids': row.config_json['sample_deal_ids'], 'created': False}
    # Explicit opt-in, transactional, and excluded from automatic event capture.
    # Demo rows must not generate real work for staff.
    previous = db.info.get('shared_capture_disabled')
    db.info['shared_capture_disabled'] = True
    try:
        with db.begin_nested():
            crm._assert_entity_permission('deals', user, 'manage')
            config = row.config_json
            pipeline = next(a['id'] for a in config['assets'] if a['kind'] == 'pipeline')
            stages = [a['id'] for a in config['assets'] if a['kind'] == 'stage']
            spec = service.template(key)
            deals = spec.get('sampleDeals') or [{'name': spec.get('sampleRecord') or 'Sample enquiry', 'amount': 1000}]
            ids = []
            from app.shared.settings import effective
            currency = effective(db, user.organization_id, 'crm')['values']['currency']
            for sample in deals[:3]:
                payload = {'name': '[Sample] '+sample['name'], 'pipeline_id': pipeline,
                    'stage_id': stages[0], 'amount': sample['amount'], 'status': 'Open', 'currency': currency,
                    'expected_close_date': date.today()+timedelta(days=7), 'owner_user_id': config['run_as_user_id']}
                resource = crm._get_resource('deals')
                crm._assert_write_scope(resource, payload, user, db)
                crm._validate_required_custom_fields(db, 'deals', None, user.organization_id, {})
                deal = CRMDeal(organization_id=user.organization_id, created_by_user_id=user.id, **payload)
                db.add(deal)
                db.flush()
                ids.append(deal.id)
            row.config_json = {**config, 'sample_deal_ids': ids}
        db.commit()
        return {'ids': ids, 'created': True}
    finally:
        if previous is None:
            db.info.pop('shared_capture_disabled', None)
        else:
            db.info['shared_capture_disabled'] = previous
