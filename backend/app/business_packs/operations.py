"""Additive action checks for native services in a freshly bound pack request.

These never replace native permissions or establish record ownership. An
unconfigured legacy request retains its native authorization. Pack identity
comes only from the server's resolved scope, never a role label or JSON field.
"""
from fastapi import HTTPException
from .access import PackScope
from .boundary import _current


def capabilities(db, actor):
    scope = db.info.get('business_pack_scope')
    if scope is None:
        return None
    if (not isinstance(scope, PackScope) or scope.user_id != getattr(actor, 'id', None)
            or scope.company_id != getattr(actor, 'organization_id', None)):
        raise HTTPException(403, 'Business Pack actor does not match native authorization')
    _current(scope, db.connection())
    return frozenset(cap.removeprefix(scope.pack_key + '.') for cap in scope.capabilities)


def require(db, actor, *actions):
    allowed = capabilities(db, actor)
    if allowed is not None and not allowed.intersection(actions):
        raise HTTPException(403, 'Assigned Business Pack role cannot perform this operation')


def can_view_booking_service(scope, actions, source, kind):
    return (scope.pack_key == 'hospital' and source == 'srm' and kind == 'service'
            and 'appointments.schedule' in actions)


def for_record_read(db, actor, kind):
    actions = {
        'appointment': ('appointments.view', 'reservations.schedule'),
        'resource': ('providers.manage', 'settings.manage', 'appointments.schedule', 'reservations.schedule'),
        'boq': ('sites.view', 'boq.prepare', 'boq.approve'),
        'variation': ('sites.view', 'variations.prepare', 'variations.approve'),
        'measurement': ('sites.view', 'measurements.prepare', 'measurements.certify'),
        'site_diary': ('sites.view', 'diary.record'),
        'subcontract': ('sites.view', 'subcontracts.manage'),
        'material_issue': ('sites.view', 'materials.request'),
        'work_package': ('sites.view', 'boq.prepare'),
        'planning_baseline': ('sites.view', 'boq.prepare', 'boq.approve'),
        'payment_certificate': ('billing.view', 'billing.prepare'),
        'handover': ('sites.view', 'diary.record'),
    }
    require(db, actor, *actions.get(kind, ()))


def for_transition(db, actor, kind, status):
    if kind == 'appointment':
        action = {'checked_in': 'appointments.check_in', 'in_service': 'visits.start',
                  'completed': 'visits.complete', 'cancelled': 'appointments.cancel',
                  'no_show': 'appointments.no_show'}.get(status)
    else:
        action = {'boq': 'boq.approve', 'variation': 'variations.approve',
                  'measurement': 'measurements.certify', 'subcontract': 'subcontracts.manage'}.get(kind)
    actions = (action,) if action else ()
    if kind == 'appointment' and status in {'checked_in', 'cancelled', 'no_show'}:
        actions += ('reservations.schedule',)
    require(db, actor, *actions)
