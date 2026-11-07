"""Transactional pack installation using native CRM, forms, analytics and workflows."""
import copy
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from app.access import service as access
from app.access.api import authority, company_access
from app.access.catalog import permission_names
from app.apps.crm.models import CRMPipeline, CRMPipelineStage, CRMCustomField, CRMDeal
from app.apps.automation.models import AutomationWorkflow, AutomationScheduledJob
from app.apps.analytics.models import AnalyticsReport
from app.forms.models import SuiteForm
from app.forms.settings import FormDefinition
from app.models.company import Company
from app.models.platform import DomainPackRegistry
from app.models.user import User
from app.access.models import AccessTemplate
from app.shared.models import WorkflowVersion
from app.shared.contracts import authorize, service_identity
from app.shared.workflow_publication import publish_definition

CATALOG = {row['key']: row for row in json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))}
MODELS = {'pipeline': CRMPipeline, 'stage': CRMPipelineStage, 'field': CRMCustomField,
    'workflow': AutomationWorkflow, 'report': AnalyticsReport, 'form': SuiteForm, 'role': AccessTemplate}
MANAGED = {
    'pipeline': ('name', 'description', 'active'),
    'stage': ('name', 'pipeline_id', 'position', 'probability', 'is_won', 'is_lost', 'active'),
    'field': ('entity', 'field_key', 'label', 'field_type', 'options_json', 'is_required', 'is_active'),
    'workflow': ('name', 'graph_json', 'run_as_user_id', 'published_version', 'is_active'),
    'report': ('name', 'module_name', 'fields_json', 'filters_json', 'grouping_json', 'data_source_json'),
    'form': ('name', 'draft', 'published', 'open', 'revision', 'version'),
    'role': ('name', 'description', 'grants', 'active', 'version'),
}


def fingerprint(kind, row):
    values = {key: getattr(row, key) for key in MANAGED[kind]}
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def template(key):
    if key not in CATALOG:
        raise HTTPException(404, 'Industry pack not found')
    return CATALOG[key]


def get_install(db, company, key, required=True):
    row = db.query(DomainPackRegistry).filter_by(company_id=company, pack_key='industry:'+key).first()
    if required and (not row or (row.config_json or {}).get('kind') != 'industry_pack'):
        raise HTTPException(404, 'Industry pack installation not found')
    return row


def identity(db, actor, company, identifier):
    person = db.query(User).filter_by(id=identifier, is_active=True).first()
    person = service_identity(db, person, company, 'crm')
    grants = access.resolved_grants(db, access.policy_for(db, person, company))
    crm = grants.get('crm', {})
    if 'create' not in crm.get('actions', []) or not set(crm.get('permissions', [])) & {'crm_admin', 'crm_manage', 'crm_activities_manage'}:
        raise HTTPException(422, 'Execution identity needs native CRM task creation permission')
    authority(actor, grants)
    return person


def preflight(db, actor, company, key, run_as=None, modules=None):
    definition = template(key)
    company_access(db, actor, company)
    from app.core.deps import RequirePermission
    RequirePermission('crm_manage', 'crm_admin')(actor)
    RequirePermission('analytics_report_builder', 'analytics_manage')(actor)
    RequirePermission('automation_manage', 'automation_admin')(actor)
    selected = set(modules or ['crm']) | {'crm'}
    if selected - set(['crm', *definition['recommendedModules']]):
        raise HTTPException(422, 'Select only the modules offered by this pack')
    for module in selected:
        authorize(db, actor, company, module)
    if run_as is not None:
        identity(db, actor, company, run_as)
    existing = get_install(db, company, key, required=False)
    conflicts = []
    if existing:
        if (existing.config_json or {}).get('kind') != 'industry_pack':
            raise HTTPException(409, 'This key is already used by another domain pack')
        digest = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        if existing.config_json['version'] == definition['version'] and existing.config_json.get('catalog_digest') != digest:
            conflicts.append({'kind': 'catalog_version', 'id': existing.id})
        for asset in existing.config_json['assets']:
            row = db.query(MODELS[asset['kind']]).filter_by(id=asset['id']).first()
            if row is None or fingerprint(asset['kind'], row) != asset['fingerprint']:
                conflicts.append({'kind': asset['kind'], 'id': asset['id']})
    return {'pack_key': key, 'version': definition['version'], 'installed_version': (existing.config_json or {}).get('version') if existing else None,
        'status': existing.status if existing else 'Not installed', 'conflicts': conflicts,
        'modules': sorted(selected), 'workflows': definition['automations'], 'reports': definition['reports'],
        'sample_data': False, 'requires_execution_identity': True}


def graph(pipeline, stage, who, pack_name, kind):
    nodes = [{'id': 'start', 'type': 'start', 'config': {}},
        {'id': 'scope', 'type': 'condition', 'config': {'condition': {'field': 'pipeline_id', 'operator': 'equals', 'value': pipeline}}}]
    edges = [{'source': 'start', 'target': 'scope'}]
    previous = 'scope'
    if kind == 1:
        nodes.extend([{'id': 'wait', 'type': 'delay', 'config': {'seconds': 86400}},
            {'id': 'open', 'type': 'condition', 'config': {'condition': {'field': 'status', 'operator': 'equals', 'value': 'Open'}}}])
        edges.extend([{'source': previous, 'target': 'wait', 'when': 'true'}, {'source': 'wait', 'target': 'open'}])
        previous = 'open'
        action = {'id': 'action', 'type': 'notification', 'config': {'recipientId': who,
            'title': f'{pack_name}: open record follow-up'[:200], 'message': 'This record is still open after 24 hours. Review its next action.', 'channels': ['in_app']}}
    else:
        if kind == 2:
            nodes.append({'id': 'stage', 'type': 'condition', 'config': {'condition': {'field': 'stage_id', 'operator': 'equals', 'value': stage}}})
            edges.append({'source': previous, 'target': 'stage', 'when': 'true'})
            previous = 'stage'
        action = {'id': 'action', 'type': 'create_record', 'config': {'tool': 'crm.create_task', 'payload': {
            'title': f'{pack_name}: {"stage handoff" if kind == 2 else "new record follow-up"}'[:220],
            'description': 'Review the linked record and agree the next action.', 'deal_id': {'$record': 'id'}}}}
    nodes.extend([action, {'id': 'end', 'type': 'end', 'config': {}}])
    edges.extend([{'source': previous, 'target': 'action', 'when': 'true'}, {'source': 'action', 'target': 'end'}])
    return {'nodes': nodes, 'edges': edges}


def install(db, actor, company, key, run_as, modules, expected_version=None):
    # Company row serializes first installation as well as repeat/upgrade calls.
    db.query(Company).filter_by(id=company).with_for_update().one()
    info = preflight(db, actor, company, key, run_as, modules)
    if info['conflicts']:
        raise HTTPException(409, {'message': 'Pack assets were edited or removed; resolve these before changing the installation', 'conflicts': info['conflicts']})
    definition = template(key)
    row = get_install(db, company, key, required=False)
    if expected_version is not None and info['installed_version'] != expected_version:
        raise HTTPException(409, 'Installed version changed; refresh onboarding')
    if row and row.config_json['run_as_user_id'] != run_as:
        raise HTTPException(409, 'Changing an execution identity requires an explicit workflow governance change')
    if row and row.config_json['version'] > definition['version']:
        raise HTTPException(409, 'Pack downgrades are not supported')
    if row and row.config_json['version'] < definition['version'] and expected_version is None:
        raise HTTPException(409, 'Review the installed version before upgrading this pack')
    if row and row.status == 'Enabled' and row.config_json['version'] == definition['version']:
        return output(row)
    from app.apps.business_os.services.module_service import enabled_module_keys, update_enabled_modules
    update_enabled_modules(db, company, enabled_module_keys(db, company) | set(info['modules']), actor)
    assets = []
    old = {(a['kind'], a['key']): a for a in row.config_json['assets']} if row else {}
    def asset(kind, key, **values):
        existing = old.get((kind, key))
        item = db.query(MODELS[kind]).filter_by(id=existing['id']).one() if existing else MODELS[kind](**values)
        if not existing:
            db.add(item)
        else:
            if kind == 'role':
                values['version'] = item.version + 1
            if kind == 'field':
                if item.field_type != values['field_type']:
                    raise HTTPException(409, 'Field type changes require an explicit data migration')
                previous_options = (item.options_json or {}).get('values', [])
                if set(previous_options) - set((values.get('options_json') or {}).get('values', [])):
                    raise HTTPException(409, 'Removing existing field options requires an explicit data migration')
            for name, value in values.items():
                if name in {'owner_id', 'created_by', 'created_by_user_id'}:
                    continue
                setattr(item, name, value)
        db.flush()
        assets.append({'kind': kind, 'key': key, 'id': item.id, 'fingerprint': fingerprint(kind, item)})
        return item
    pipeline = asset('pipeline', 'pipeline', organization_id=company, name=definition['name'],
        description=f'Industry pack {key}; installed workflows are CRM follow-ups, not specialist operating engines.', active=True,
        created_by_user_id=actor.id)
    stages = []
    for index, stage in enumerate(definition['stages']):
        stages.append(asset('stage', str(index), organization_id=company, pipeline_id=pipeline.id, name=stage['name'],
            probability=stage['probability'], position=index+1, order_index=index+1, color=stage['color'],
            is_won=stage.get('isWon', False), is_lost=stage.get('isLost', False), active=True, created_by_user_id=actor.id))
    prefix = 'ip_' + key.replace('-', '_')[:35] + '_'
    explicit = {f['fieldName'].lower(): f for f in definition.get('customFields', []) if f['entityType'] == 'deals'}
    fields = []
    labels = {}
    for label in [*definition['fields'], *[f['fieldName'] for f in explicit.values()]]:
        labels.setdefault(label.lower(), label)
    for index, label in enumerate(labels.values()):
        spec = explicit.get(label.lower(), {})
        field_key = prefix + (spec.get('fieldKey') or re.sub('[^a-z0-9]+', '_', label.lower()).strip('_'))[:55]
        fields.append(asset('field', field_key, organization_id=company, entity='deals', field_key=field_key,
            field_name=label, label=label, field_type=spec.get('fieldType', 'text'),
            options_json={'values': spec.get('options', []), 'ui': {'section': definition['name'], 'pipeline_id': pipeline.id}},
            is_required=False, is_unique=False, is_visible=True, is_filterable=True, is_active=True, position=index,
            created_by_user_id=actor.id))
    for index, title in enumerate(definition['automations']):
        before = old.get(('workflow', str(index)))
        existing = db.query(AutomationWorkflow).filter_by(id=before['id']).one() if before else None
        version = (existing.draft_version or 0) + 1 if existing else 1
        workflow = asset('workflow', str(index), organization_id=company, name=f'{definition["name"]}: {title}'[:180],
            description='Installed by a versioned industry pack using the shared workflow runner.', module_name='crm', record_type='deal',
            trigger_type='stage.changed' if index == 2 else 'record.created', graph_json=graph(pipeline.id, stages[min(1, len(stages)-1)].id, run_as, definition['name'], index),
            run_as_user_id=run_as, draft_version=version, is_active=False, created_by=actor.id)
        publish_definition(db, actor, company, workflow)
        db.flush()
        assets[-1]['fingerprint'] = fingerprint('workflow', workflow)
    report_specs = [
        ('crm_deals', ['id', 'name', 'amount', 'status', 'stage_id', 'expected_close_date', *['custom:'+f.field_key for f in fields]], {'pipeline_id': pipeline.id}, None),
        ('crm_deals', ['stage_id', 'record_count', 'total_value'], {'pipeline_id': pipeline.id}, {'group_by': ['stage_id'], 'aggregates': {'record_count': {'function': 'count'}, 'total_value': {'function': 'sum', 'field': 'amount'}}}),
        ('crm_tasks', ['id', 'title', 'status', 'priority', 'due_date', 'deal_id'], {'pack_pipeline_id': pipeline.id}, None),
    ]
    for index, (source, columns, filters, grouping) in enumerate(report_specs):
        asset('report', str(index), name=f'{definition["name"]}: {definition["reports"][index]}'[:180], module_name=source,
            fields_json=columns, filters_json=filters, grouping_json=grouping, visibility='team', owner_id=actor.id,
            data_source_json={'industry_pack': key, 'company_id': company, 'locked_filters': filters})
    form_definition = FormDefinition(name=f'{definition["name"]} intake'[:120], description='Private intake; review responses before creating commercial records.',
        fields=[{'id': 'customer_name', 'label': 'Customer name', 'type': 'text', 'required': True},
            {'id': 'request_details', 'label': 'Request details', 'type': 'textarea', 'required': True}]).model_dump(mode='json')
    asset('form', 'intake', organization_id=company, owner_id=actor.id, module_key='crm', name=form_definition['name'],
        draft=form_definition, published=form_definition, revision=1, version=1, open=True,
        slug=(db.query(SuiteForm).filter_by(id=old['form', 'intake']['id']).one().slug if ('form', 'intake') in old else secrets.token_urlsafe(24)))
    for role_key, names in [('viewer', ['crm_view', 'analytics_view']), ('operator', ['crm_view', 'crm_manage', 'analytics_view'])]:
        grants = access.validate_grants(db, {
            'crm': {'enabled': True, 'role': role_key.title(), 'scope': 'own', 'permissions': [n for n in names if n.startswith('crm_')],
                'actions': ['view', 'create', 'edit'] if role_key == 'operator' else ['view']},
            'analytics': {'enabled': True, 'role': 'Report viewer', 'scope': 'own', 'permissions': ['analytics_view'], 'actions': ['view']},
        }, company)
        authority(actor, grants)
        asset('role', role_key, company_id=company, name=f'{definition["name"]} {role_key}'[:100],
            description='Industry pack access template; assign through central access governance', grants=grants, active=True, version=1)
    retained = {(a['kind'], a['key']) for a in assets}
    if set(old) - retained:
        raise HTTPException(409, 'This pack update removes installed assets and requires an explicit migration')
    previous_config = copy.deepcopy(row.config_json) if row else None
    config = {'kind': 'industry_pack', 'version': definition['version'], 'catalog_digest': hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest(),
        'run_as_user_id': run_as, 'modules': info['modules'],
        'assets': assets, 'sample_deal_ids': (previous_config or {}).get('sample_deal_ids', []),
        'history': [*((previous_config or {}).get('history', [])), *([{'version': previous_config['version'], 'at': datetime.now(timezone.utc).isoformat()}] if previous_config else [])][-10:]}
    if row is None:
        row = DomainPackRegistry(company_id=company, pack_key='industry:'+key, pack_name=definition['name'], enabled_by=actor.id)
        db.add(row)
    row.config_json, row.status, row.disabled_at = config, 'Enabled', None
    db.flush()
    access.audit(db, actor, company, 'industry_pack.installed', 'Install industry workflows and reports', after={'pack': key, 'version': definition['version']})
    return output(row)


def output(row):
    return {'id': row.id, 'pack_key': row.pack_key.removeprefix('industry:'), 'name': row.pack_name, 'status': row.status, **(row.config_json or {})}


def disable(db, actor, company, key):
    company_access(db, actor, company)
    db.query(Company).filter_by(id=company).with_for_update().one()
    row = get_install(db, company, key)
    if row.status == 'Disabled':
        return output(row)
    config = copy.deepcopy(row.config_json)
    for asset in config['assets']:
        if asset['kind'] in {'workflow', 'pipeline', 'form'}:
            item = db.query(MODELS[asset['kind']]).filter_by(id=asset['id']).first()
            if item:
                unchanged = fingerprint(asset['kind'], item) == asset['fingerprint']
                setattr(item, {'workflow': 'is_active', 'pipeline': 'active', 'form': 'open'}[asset['kind']], False)
                if unchanged:
                    asset['fingerprint'] = fingerprint(asset['kind'], item)
    workflow_ids = [a['id'] for a in config['assets'] if a['kind'] == 'workflow']
    versions = [v.id for v in db.query(WorkflowVersion).filter(WorkflowVersion.workflow_id.in_(workflow_ids)).all()]
    # Queue rows are created by background workers and may have no branch stamp.
    # This company-admin operation is deliberately constrained by BOTH company
    # and this installation's published version IDs, not a user's branch view.
    jobs = AutomationScheduledJob.__table__
    db.connection().execute(jobs.update().where(jobs.c.organization_id == company,
        jobs.c.job_type == 'shared_workflow', jobs.c.status.in_(['scheduled', 'running']),
        jobs.c.payload_json['versionId'].as_integer().in_(versions)).values(status='cancelled', last_error='Industry pack disabled'))
    row.config_json = config
    row.status, row.disabled_at = 'Disabled', datetime.now(timezone.utc)
    access.audit(db, actor, company, 'industry_pack.disabled', 'Disable pack without deleting business records', after={'pack': key})
    return output(row)
