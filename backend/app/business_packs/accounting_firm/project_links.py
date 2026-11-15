"""One audited None-to-project transition on the canonical native engagement."""
from weakref import WeakKeyDictionary
from sqlalchemy import event, inspect
from app.apps.srm.models import SRMEngagement, SRMInvoice
from .models import AccountsCommand, AccountsPeriod, AccountsEngagementCommand
from . import service
from .pms_sources import project_for_action

_LINKS = WeakKeyDictionary()


class IncompatibleCommercialSource(Exception):
    """A visible PMS source belongs to another canonical commercial engagement."""


def reconcile_commercial(db, scope, engagement_id, client_id, project_id, *, project_source):
    from sqlalchemy import select
    from app.apps.srm.commercial_models import ProjectCommercial, CustomerLink
    from app.apps.project_management.models import PMSProject
    project = PMSProject.__table__
    links = CustomerLink.__table__
    client_link = db.connection().execute(select(links.c.customer_id, links.c.organization_id).join(
        project, project.c.client_id == links.c.source_id).where(project.c.id == project_id,
        links.c.source_type == "pms_client")).first()
    if client_link is not None and (client_link.customer_id != client_id
            or client_link.organization_id != scope.company_id):
        raise IncompatibleCommercialSource()
    table = ProjectCommercial.__table__
    commercial = db.connection().execute(select(table.c.customer_id, table.c.seller_id,
        table.c.currency).where(table.c.project_id == project_id)).first()
    engagement = db.get(SRMEngagement, engagement_id)
    if project_source.id != project_id or project_source.currency != engagement.currency:
        raise IncompatibleCommercialSource()
    if commercial is not None and (commercial.customer_id != client_id
            or commercial.seller_id != scope.company_id or commercial.currency != engagement.currency):
        raise IncompatibleCommercialSource()


def require_commercial(db, scope, engagement_id, client_id, project_id, *, project_source):
    try:
        reconcile_commercial(db, scope, engagement_id, client_id, project_id, project_source=project_source)
    except IncompatibleCommercialSource:
        service.fail('Canonical project commercial client, seller or currency differs from engagement', 409)


def _commands(db, scope, engagement_id):
    return service.scoped(db, AccountsCommand, scope).join(AccountsPeriod,
        AccountsPeriod.id == AccountsCommand.period_id).filter(AccountsPeriod.engagement_id == engagement_id,
        AccountsCommand.action == 'project.link').all()


def validate_birth_project(db, actor, scope, birth, actual):
    links = _commands(db, scope, birth.engagement_id)
    if not links and actual['pms_project_id'] == birth.source_snapshot['pms_project_id']:
        return
    if len(links) != 1:
        service.fail('Canonical engagement project requires its immutable link command', 409)
    result = links[0].result
    if (result.get('engagement_id') != birth.engagement_id or result.get('client_id') != birth.client_id
            or result.get('birth_sha256') != birth.source_sha256 or result.get('old_project_id') is not None
            or result.get('project_id') != actual['pms_project_id'] or birth.source_snapshot['pms_project_id'] is not None):
        service.fail('Canonical engagement project differs from its certified transition', 409)
    project_for_action(db, actor, actual['pms_project_id'])


def reference(db, scope, item, parent, pairs):
    from app.apps.project_management.models import PMSProject
    from app.models.user import User
    if (type(item) is not SRMEngagement or parent is not PMSProject.__table__ or len(pairs) != 1
            or pairs[0][0] != 'pms_project_id' or pairs[0][1] is not PMSProject.__table__.c.id):
        return False
    actor = db.get(User, scope.user_id)
    plan = _LINKS.get(db)
    if plan is not None and plan['engagement'] is item:
        if item.pms_project_id != plan['project_id'] or scope is not plan['scope']:
            service.fail('Accounts project link source changed')
    else:
        from .engagements import _snapshot
        actual = _snapshot(db, item.id)
        if actual is None or actual['pms_project_id'] != item.pms_project_id:
            return False
    project_for_action(db, actor, item.pms_project_id)
    return True


@event.listens_for(AccountsCommand, 'before_insert')
def certify_link(mapper, connection, command):
    if command.action != 'project.link':
        return
    from .engagements import _snapshot
    db = inspect(command).session
    plan = _LINKS.get(db)
    if (plan is None or plan.get('command') is not command or command.result != plan['result']
            or command.period_id != plan['period_id'] or command.created_by != plan['actor'].id):
        service.fail('A genuinely minted canonical project transition is required')
    actual = _snapshot(db, plan['engagement'].id)
    previous = plan['before']
    if (actual is None or actual['pms_project_id'] != plan['project_id'] or previous['pms_project_id'] is not None
            or {k:v for k,v in actual.items() if k not in {'pms_project_id','updated_at'}} !=
               {k:v for k,v in previous.items() if k not in {'pms_project_id','updated_at'}}):
        service.fail('Project linking changed unrelated canonical engagement fields', 409)
    project_for_action(db, plan['actor'], plan['project_id'])


def link(ident, data, db, actor):
    from .engagements import _snapshot
    scope = service.authority(db, actor, 'engagements.manage', write=True)
    service.lock_tenant(db, actor)
    service.authority(db, actor, 'engagements.manage', write=True)
    period = service.record(db, actor, scope, ident)
    project = project_for_action(db, actor, data.project_id)
    require_commercial(db, scope, period.engagement_id, period.client_id, data.project_id, project_source=project)
    old = service.replay(db, actor, scope, 'project.link', ident, data)
    if old is not None:
        return old
    service.source(db, actor, scope, period.engagement_id, period.client_id, require_open=True)
    engagement = db.get(SRMEngagement, period.engagement_id)
    if (period.revision != data.expected_revision or engagement.pms_project_id is not None
            or _commands(db, scope, engagement.id)
            or service.scoped(db, AccountsPeriod, scope).filter(AccountsPeriod.engagement_id == engagement.id,
                AccountsPeriod.work_revision > 0).first()
            or db.query(SRMInvoice).filter_by(engagement_id=engagement.id).first()):
        service.fail('Link delivery once before preparation or billing begins', 409)
    birth = service.scoped(db, AccountsEngagementCommand, scope).filter_by(engagement_id=engagement.id).one_or_none()
    result = {'engagement_id': engagement.id, 'client_id': period.client_id, 'project_id': data.project_id,
        'old_project_id': None, 'birth_sha256': birth.source_sha256 if birth else None}
    plan = dict(scope=scope, actor=actor, period_id=period.id, engagement=engagement,
        project_id=data.project_id, before=_snapshot(db, engagement.id), result=result)
    if db in _LINKS:
        service.fail('Accounts project linking cannot nest')
    with db.begin_nested():
        _LINKS[db] = plan
        try:
            engagement.pms_project_id = data.project_id
            db.flush()
            command = AccountsCommand(**service.fields(scope, actor), period_id=period.id,
                request_key=str(data.request_key), request_sha256=service.fingerprint('project.link', ident, data),
                action='project.link', reason='', result=result)
            plan['command'] = command
            db.add(command); db.flush()
        finally:
            _LINKS.pop(db, None)
    db.commit()
    return result
