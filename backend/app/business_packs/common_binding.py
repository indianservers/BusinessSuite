"""Exact, independent native-purpose binding; never a Business Pack grant.

Only reviewed canonical server routes may enter this realm. The caller first
binds native identity/company/branch authority; native actions are checked later
by the CommonCore adapter. Raw pack selectors do not select this purpose.
"""
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import HTTPException
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import Match

MARKER='business_pack_request_binding'
_ABSENT=object()


@dataclass(frozen=True)
class CoreRequestBinding:
    user_id: int
    company_id: int
    method: str
    route: str
    purpose: str = 'hrms.actual_time'

    def __post_init__(self):
        if (type(self.user_id) is not int or self.user_id<=0
                or type(self.company_id) is not int or self.company_id<=0
                or self.method not in {'GET','POST','PUT','DELETE'}
                or not isinstance(self.route,str) or not self.route.startswith('/api/v1/')
                or self.purpose not in {'hrms.actual_time','hrms.employee_management','hrms.employee_references','hrms.leave','hrms.leave_encashment','hrms.payroll_register','hrms.payroll_review','hrms.payroll_variance','hrms.payroll_payslip','hrms.home','crm.company_master'}):
            raise ValueError('Native Core binding requires fixed native actor/company and canonical route metadata')


def canonical_route(request):
    route=request.scope.get('route')
    router=getattr(request.scope.get('app'),'router',None)
    if not isinstance(route,APIRoute) or router is None:return None
    paths={context.path for context in iter_route_contexts(router.routes)
        if context.original_route is route and request.method in (context.methods or ())
        and context.matches(request.scope)[0] is Match.FULL}
    return paths.pop() if len(paths)==1 else None


def request_binding(actor,request):
    from .common_core import OPERATIONS
    route=canonical_route(request)
    if (request.method,route) not in OPERATIONS:return None
    if OPERATIONS[(request.method,route)].purpose=='crm.company_master' and request.query_params.get('source','crm')!='crm':
        return None  # Other native modules retain their independently reviewed route gates.
    if type(getattr(actor,'id',None)) is not int or actor.id<=0 or type(getattr(actor,'organization_id',None)) is not int or actor.organization_id<=0:
        raise HTTPException(403,'A verified native actor and company are required for Core purpose')
    return CoreRequestBinding(actor.id,actor.organization_id,request.method,route,OPERATIONS[(request.method,route)].purpose)


@contextmanager
def bind_core_request(db,binding):
    from .common_core import OPERATIONS
    if not isinstance(binding,CoreRequestBinding) or (binding.method,binding.route) not in OPERATIONS or OPERATIONS[(binding.method,binding.route)].purpose!=binding.purpose:
        raise HTTPException(403,'A server-registered native Core purpose is required')
    previous=db.info.get('business_pack_scope',_ABSENT)
    marker=db.info.get(MARKER,_ABSENT)
    if (previous is not _ABSENT and previous is not None) or (marker is not _ABSENT and marker!=binding):
        raise HTTPException(403,'A bound operational realm cannot change to native Core')
    db.info['business_pack_scope']=None
    db.info[MARKER]=binding
    try:yield binding
    finally:
        for key,value in (('business_pack_scope',previous),(MARKER,marker)):
            if value is _ABSENT:db.info.pop(key,None)
            else:db.info[key]=value


def authorization_fingerprint(binding):
    if not isinstance(binding,CoreRequestBinding):raise TypeError('An explicit native Core binding is required')
    return ('native-common-core-v1',binding.company_id,binding.user_id,binding.purpose)
