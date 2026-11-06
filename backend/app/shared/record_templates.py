"""Choose and populate visual templates at a visible CRM record or invoice."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator, ValidationError
from app.core.deps import get_current_user, get_db
from app.apps.srm.services.commercial import tenant
from app.apps.crm.template_models import CRMVisualTemplate
from app.apps.crm.template_studio import Strict, TemplateInput, RenderInput, render, output
from .record_template_context import resolve_context

router = APIRouter(prefix='/record-templates', tags=['Record templates'])
Entity = Literal['lead', 'contact', 'account', 'deal', 'invoice']
Source = Literal['crm', 'srm']


def compatible(template, entity):
    if entity == 'invoice' and template.category == 'inventory':
        return template.document_type == 'invoice'
    return template.module == entity and template.category in ('email', 'mail_merge')


@router.get('/{entity}/{identity}')
def choices(entity: Entity, identity: int, source: Source = 'crm', db=Depends(get_db), user=Depends(get_current_user)):
    # Authorization precedes template discovery, including for nonexistent records.
    resolved = resolve_context(db, user, entity, identity, source)
    rows = db.query(CRMVisualTemplate).filter_by(organization_id=tenant(user), status='ready').order_by(CRMVisualTemplate.name).all()
    return {'items': [output(row) for row in rows if compatible(row, entity)], 'record_name': resolved['record_name']}


class RecordRenderInput(Strict):
    template_id: int | None = Field(default=None, gt=0)
    template: TemplateInput | None = None
    values: dict[str, str] = Field(default_factory=dict, max_length=100)

    @model_validator(mode='after')
    def one_template(self):
        if (self.template_id is None) == (self.template is None):
            raise ValueError('Choose one saved template or starter design')
        return self


@router.post('/{entity}/{identity}/render')
def populate(entity: Entity, identity: int, data: RecordRenderInput, source: Source = 'crm', db=Depends(get_db), user=Depends(get_current_user)):
    resolved = resolve_context(db, user, entity, identity, source)
    if data.template_id:
        row = db.query(CRMVisualTemplate).filter_by(id=data.template_id, organization_id=tenant(user), status='ready').first()
        if not row: raise HTTPException(404, 'Ready template not found')
        template = TemplateInput.model_validate({key: getattr(row, key) for key in TemplateInput.model_fields})
    else: template = data.template
    if not compatible(template, entity): raise HTTPException(422, 'Choose a template for this record type')
    # Manual entries fill gaps only. Financial amounts and other actual record values stay authoritative.
    values = dict(resolved['values'])
    for key, value in data.values.items():
        if not values.get(key): values[key] = value
    try:
        result = render(RenderInput(template=template, values=values, lines=resolved['lines'], sample=False))
    except ValidationError:
        raise HTTPException(422, 'This record exceeds the template layout limits. Use the invoice’s native PDF for the full document.')
    if entity == 'invoice' and resolved['document_status'] in ('draft', 'pending_approval', 'cancelled'):
        label = 'CANCELLED' if resolved['document_status'] == 'cancelled' else 'DRAFT · Not issued'
        banner = f'<div style="font:700 14px Arial;padding:12px 24px;background-color:#fff4db;color:#785b25;text-align:center">{label}</div>'
        result['html'] = result['html'].replace('<body>', '<body>' + banner, 1)
        result['body'] = banner + result['body']
    return {**result, 'record_name': resolved['record_name'], 'snapshot': resolved['snapshot'],
            'document_status': resolved['document_status'], 'template_name': template.name,
            'filled_fields': sorted(key for key, value in resolved['values'].items() if value)}
