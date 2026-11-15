"""Exact matched native operations; no pack role can replace native authority."""
import ast
import inspect
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.requests import Request as StarletteRequest
from app.main import app
from app.business_packs.access import resolve_context
from app.business_packs.request_operations import authorize_request, RULES
from app.business_packs.models import PackUserGrant
from tests.test_business_pack_access import packs


def request(path, method='GET', *, query='', raw=None, headers=()):
    context=next((r for r in iter_route_contexts(app.router.routes) if isinstance(r.original_route,APIRoute) and r.path==path and method in r.methods),None)
    route=context.original_route if context else None
    assert route is not None,(method,path)
    concrete=path
    for key in route.param_convertors:concrete=concrete.replace('{'+key+'}','1')
    return StarletteRequest({'type':'http','http_version':'1.1','method':method,'scheme':'https',
        'path':raw or concrete,'root_path':'','query_string':query.encode(),'headers':headers,
        'server':('guard.test',443),'client':('127.0.0.1',1234),'route':route,'app':app})


def bound(p, role='doctor', actor='doctor'):
    if p.grants[actor].role!=role:
        p.grants[actor].role=role;p.db.commit()
    user=p.users[actor]
    scope=resolve_context(p.db,user,p.ctx(),p.contexts[actor].id)
    p.db.info['business_pack_scope']=scope
    return user,scope


def denied(p,user,scope,path,method='GET',query='',status=403):
    with pytest.raises(HTTPException) as error:authorize_request(p.db,user,request(path,method,query=query),scope)
    assert error.value.status_code==status,error.value.detail
    return error.value.detail


def test_every_declared_rule_is_actual_registered_native_route_with_ast_decorator():
    for (method,path),rule in RULES.items():
        context=next((r for r in iter_route_contexts(app.router.routes) if isinstance(r.original_route,APIRoute) and r.path==path and method in r.methods),None)
        native=context.original_route if context else None
        assert native is not None,(method,path)
        endpoint=inspect.unwrap(native.endpoint)
        tree=ast.parse(Path(inspect.getsourcefile(endpoint)).read_text(encoding='utf-8-sig'))
        functions=[node for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==endpoint.__name__]
        assert any(isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr==method.lower()
            and dec.args and isinstance(dec.args[0],ast.Constant) and path.endswith(dec.args[0].value)
            for function in functions for dec in function.decorator_list),(method,path,endpoint.__name__)


@pytest.mark.parametrize('path',[
 '/api/v1/srm/invoices','/api/v1/srm/invoices/{invoice_id}',
 '/api/v1/srm/invoices/{invoice_id}/pdf','/api/v1/srm/business/invoices/{invoice_id}',
 '/api/v1/srm/receipts','/api/v1/srm/receipts/{receipt_id}',
 '/api/v1/srm/sales-orders','/api/v1/srm/pos/sessions/active',
 '/api/v1/srm/service-checkout/{checkout_id}',
])
@pytest.mark.parametrize('role,actor',[('doctor','doctor'),('chef','chef')])
def test_native_superuser_flag_does_not_promote_specialists_to_financial_readers(packs,path,role,actor):
    p=packs;user,scope=bound(p,role,actor)
    user.is_superuser=True;p.db.commit()
    denied(p,user,scope,path)


def test_known_financial_writes_require_capability_then_honest_integration_blocker(packs):
    p=packs;user,scope=bound(p)
    for path,method in [('/api/v1/srm/receipts','POST'),('/api/v1/srm/receipts/{receipt_id}/allocate','POST'),('/api/v1/srm/invoices/{invoice_id}','PATCH')]:
        denied(p,user,scope,path,method)
    user,scope=bound(p,'hospital_manager')
    for path,method in [('/api/v1/srm/receipts','POST'),('/api/v1/srm/receipts/{receipt_id}/allocate','POST'),('/api/v1/srm/invoices/{invoice_id}','PATCH')]:
        detail=denied(p,user,scope,path,method,status=503)
        assert detail['code']=='business_pack_integration_unavailable' and detail['runtime_ready'] is False
        assert 'grouped checkout' in detail['reason']


@pytest.mark.parametrize('method,path',[
 ('POST','/api/v1/srm/service-checkout'),('GET','/api/v1/srm/service-checkout/{checkout_id}'),
 ('POST','/api/v1/srm/service-checkout/{checkout_id}/payments'),
 ('GET','/api/v1/srm/invoices/{invoice_id}/pdf'),('POST','/api/v1/srm/invoices/{invoice_id}/approve'),
 ('GET','/api/v1/srm/industry/appointments/{ident}/billing'),
 ('POST','/api/v1/srm/industry/appointments/{ident}/payments'),
 ('POST','/api/v1/srm/pos/sessions'),
])
def test_exact_manager_rules_keep_native_authorization_mandatory(packs,method,path):
    p=packs;user,scope=bound(p,'hospital_manager')
    result=authorize_request(p.db,user,request(path,method),scope)
    assert result['native_authorization_required'] is True and result['runtime_ready'] is False
    assert result['route']==path
    assert user.role.permissions==[] and not user.is_superuser


def test_industry_query_kind_and_native_body_action_guard_are_distinct(packs):
    p=packs;user,scope=bound(p)
    authorize_request(p.db,user,request('/api/v1/srm/industry/records',query='kind=appointment'),scope)
    authorize_request(p.db,user,request('/api/v1/srm/industry/records/{ident}/transition','POST'),scope)
    for kind in ('resource','boq','material_issue','unknown'):
        denied(p,user,scope,'/api/v1/srm/industry/records',query='kind='+kind)
    for path,method in [('/api/v1/srm/industry/appointments','POST'),('/api/v1/srm/service-checkout/options','GET'),('/api/v1/srm/service-checkout/policies','PUT')]:
        denied(p,user,scope,path,method)


def test_projected_schedule_and_effective_terms_are_only_narrow_independent_reads(packs):
    p=packs;user,scope=bound(p)
    for path in ('/api/v1/employees/planned-services','/api/v1/employees/{employee_id}/planned-services','/api/v1/access/settings/business-profile/effective','/api/v1/access/settings/defaults/effective'):
        result=authorize_request(p.db,user,request(path),scope)
        assert result['adapter']=='independent_projection'
    for path in ('/api/v1/employees/','/api/v1/crm/{entity}'):
        detail=denied(p,user,scope,path,status=503)
        assert detail['route']==path


def test_unknown_route_no_route_and_caller_aliases_cannot_supply_an_adapter(packs):
    p=packs;user,scope=bound(p)
    denied(p,user,scope,'/api/v1/srm/inventory/items',status=503)
    req=request('/api/v1/srm/invoices')
    req.scope.pop('route')
    with pytest.raises(HTTPException) as error:authorize_request(p.db,user,req,scope)
    assert error.value.status_code==503 and error.value.detail['route'] is None
    req=request('/api/v1/srm/invoices',headers=((b'x-original-url',b'/api/v1/srm/industry/capabilities'),))
    with pytest.raises(HTTPException) as error:authorize_request(p.db,user,req,scope)
    assert error.value.status_code==403
    req=request('/api/v1/srm/invoices',raw='/api/v1/access/me')
    with pytest.raises(HTTPException) as error:authorize_request(p.db,user,req,scope)
    assert error.value.status_code==503


def test_register_close_needs_explicit_registered_sessions_capability(packs):
    p=packs;user,scope=bound(p,'cashier')
    denied(p,user,scope,'/api/v1/srm/pos/cashier-closing','POST')
    user,scope=bound(p,'hospital_manager')
    authorize_request(p.db,user,request('/api/v1/srm/pos/cashier-closing','POST'),scope)
    user,scope=bound(p,'restaurant_manager','chef')
    authorize_request(p.db,user,request('/api/v1/srm/pos/cashier-closing','POST'),scope)
    authorize_request(p.db,user,request('/api/v1/srm/pos/cash-movements','POST'),scope)


def test_anonymous_setup_needs_pack_configuration_and_fresh_native_company_admin(packs):
    from app.access.models import AccessMembership
    p=packs;user,scope=bound(p,'hospital_manager')
    denied(p,user,scope,'/api/v1/srm/anonymous-cash/configuration','PUT')
    membership=p.db.query(AccessMembership).filter_by(company_id=1,user_id=user.id).one()
    membership.is_admin=True;p.db.commit()
    authorize_request(p.db,user,request('/api/v1/srm/anonymous-cash/configuration','PUT'),scope)
    membership.is_admin=False;p.db.commit()
    denied(p,user,scope,'/api/v1/srm/anonymous-cash/configuration','PUT')


def test_revoked_scope_or_different_bound_selection_never_uses_cached_success(packs):
    p=packs;user,scope=bound(p,'hospital_manager')
    authorize_request(p.db,user,request('/api/v1/srm/invoices'),scope)
    p.grants['doctor'].active=False;p.db.commit()
    denied(p,user,scope,'/api/v1/srm/invoices')
    p.db.info['business_pack_scope']=None
    denied(p,user,scope,'/api/v1/srm/invoices')


def test_genuinely_legacy_no_scope_preserves_even_unknown_native_routes(packs):
    p=packs
    req=StarletteRequest({'type':'http','method':'POST','path':'/legacy/unknown','headers':[]})
    assert authorize_request(p.db,p.users['doctor'],req,None) is None
    user,scope=bound(p)
    with pytest.raises(HTTPException) as error:authorize_request(p.db,user,req,None)
    assert error.value.status_code==403


def test_personal_and_control_repair_does_not_require_operational_pack_grant(packs):
    p=packs;user,scope=bound(p)
    p.grants['doctor'].active=False;p.db.commit()
    for path in ('/api/v1/access/me','/api/v1/auth/me'):
        result=authorize_request(p.db,user,request(path),scope)
        assert result['adapter']=='native_control'


@pytest.mark.parametrize('path',('/api/v1/fam/workspace-directory','/api/v1/ai/provider-settings','/api/v1/files-storage','/api/v1/crm/workspace-directory'))
def test_no_broad_optional_module_or_file_adapter_is_implied(packs,path):
    p=packs;user,scope=bound(p,'hospital_manager')
    detail=denied(p,user,scope,path,status=503)
    assert detail['code']=='business_pack_integration_unavailable'
