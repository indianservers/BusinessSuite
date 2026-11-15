"""Immutable client-document requests referencing authorized canonical PMS files."""
from app.apps.srm.models import SRMEngagement
from . import service
from .models import AccountsCommand
from .pms_sources import file_source


def _access(db, actor, *, write=False):
    scope = db.info.get('business_pack_scope')
    capability = 'documents.request' if (write or scope is not None and
        'accounting_firm.documents.request' in scope.capabilities) else 'documents.view'
    return service.authority(db, actor, capability, write=write)


def _history(db, scope, period_id):
    return service.scoped(db, AccountsCommand, scope).filter(AccountsCommand.period_id == period_id,
        AccountsCommand.action.in_(('document.request', 'document.attach', 'document.upload'))).order_by(AccountsCommand.id).all()


def _current(db, scope, period_id, key):
    rows = [row for row in _history(db, scope, period_id) if row.result.get('document_key') == str(key)]
    if not rows or rows[0].action != 'document.request' or rows[0].request_key != str(key):
        service.fail('Document request is unavailable', 404)
    return dict(rows[-1].result)


def _project(db, actor, scope, period):
    engagement = db.get(SRMEngagement, period.engagement_id)
    if engagement.pms_project_id is None:
        service.fail('Link a canonical PMS project before supplying documents', 409)
    return engagement.pms_project_id


def listing(ident, db, actor):
    scope = _access(db, actor)
    period = service.record(db, actor, scope, ident)
    latest = {}
    for row in _history(db, scope, ident):
        latest[row.result['document_key']] = dict(row.result)
    for item in latest.values():
        if item['status'] == 'uploaded':
            actual = file_source(db, actor, _project(db, actor, scope, period), item['file']['file_id'])
            if actual != item['file']:
                service.fail('Document changed; supply its current native version', 409)
    return {'items': list(latest.values())}


def _save(db, actor, scope, period, action, identity, data, result):
    db.add(AccountsCommand(**service.fields(scope, actor), period_id=period.id,
        request_key=str(data.request_key), request_sha256=service.fingerprint(action, identity, data),
        action=action, reason='', result=result))
    db.flush()


def request(ident, data, db, actor):
    scope = _access(db, actor, write=True)
    service.lock_tenant(db, actor)
    _access(db, actor, write=True)
    period = service.record(db, actor, scope, ident)
    old = service.replay(db, actor, scope, 'document.request', ident, data)
    if old is not None:
        return old
    service.source(db, actor, scope, period.engagement_id, period.client_id, require_open=True)
    if period.state not in {'draft', 'returned'}:
        service.fail('Reopen preparation before changing its document checklist', 409)
    if period.revision != data.expected_revision:
        service.fail('Period changed; reload its current revision', 409)
    if not data.title.strip() or data.due_on < period.starts_on:
        service.fail('A document title and valid due date are required', 422)
    result = {'document_key': str(data.request_key), 'title': data.title.strip(),
        'due_on': data.due_on.isoformat(), 'status': 'requested', 'revision': 1, 'file': None}
    with db.begin_nested():
        _save(db, actor, scope, period, 'document.request', ident, data, result)
    db.commit()
    return result


def attach(ident, key, data, db, actor):
    scope = _access(db, actor, write=True)
    service.lock_tenant(db, actor)
    _access(db, actor, write=True)
    period = service.record(db, actor, scope, ident)
    current = _current(db, scope, ident, key)
    file = file_source(db, actor, _project(db, actor, scope, period), data.file_id)
    identity = f'{ident}:{key}'
    old = service.replay(db, actor, scope, 'document.attach', identity, data)
    if old is not None:
        return old
    service.source(db, actor, scope, period.engagement_id, period.client_id, require_open=True)
    if period.state not in {'draft', 'returned'}:
        service.fail('Reopen preparation before replacing submitted documents', 409)
    if period.revision != data.expected_revision or current['revision'] != data.expected_document_revision:
        service.fail('Document request changed; reload before supplying a file', 409)
    result = current | {'status': 'uploaded', 'revision': current['revision'] + 1, 'file': file}
    with db.begin_nested():
        _save(db, actor, scope, period, 'document.attach', identity, data, result)
    db.commit()
    return result


def download(ident, key, db, actor):
    scope = _access(db, actor)
    period = service.record(db, actor, scope, ident)
    item = _current(db, scope, ident, key)
    if item['status'] != 'uploaded':
        service.fail('No uploaded document is available', 404)
    project = _project(db, actor, scope, period)
    actual = file_source(db, actor, project, item['file']['file_id'])
    if actual != item['file']:
        service.fail('Document changed; supply its current native version', 409)
    response = file_source(db, actor, project, actual['file_id'], download=True)
    from .cloud_download import pending,finish,abort
    try:
        if pending(response):
            current_scope=_access(db,actor)
            current_period=service.record(db,actor,current_scope,ident)
            if (_current(db,current_scope,ident,key)!=item or _project(db,actor,current_scope,current_period)!=project
                    or file_source(db,actor,project,actual['file_id'])!=actual):
                service.fail('Document source changed during download',409)
            return finish(response,db,actor,current_scope)
        return response
    except BaseException:
        abort(response)
        raise
