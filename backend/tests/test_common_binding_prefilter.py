from types import SimpleNamespace
from fastapi.routing import APIRoute
from app.business_packs import common_binding


def test_unrelated_server_route_skips_canonical_graph(monkeypatch):
    def unexpected(request):
        raise AssertionError("Unrelated inventory reads must not scan canonical Core routes")
    monkeypatch.setattr(common_binding, "canonical_route", unexpected)
    request=SimpleNamespace(method="GET", scope={"route":APIRoute("/inventory/items", lambda: None, methods=["GET"])})
    assert common_binding.request_binding(SimpleNamespace(),request) is None


def test_included_native_route_still_requires_canonical_verification(monkeypatch):
    calls=[]
    monkeypatch.setattr(common_binding,"canonical_route",lambda request:calls.append(request) or "/api/v1/timesheets/projects")
    request=SimpleNamespace(method="GET",scope={"route":APIRoute("/projects",lambda:None,methods=["GET"])})
    result=common_binding.request_binding(SimpleNamespace(id=1,organization_id=1),request)
    assert result.route=="/api/v1/timesheets/projects"
    assert calls==[request]
    monkeypatch.setattr(common_binding,"canonical_route",lambda request:None)
    assert common_binding.request_binding(SimpleNamespace(id=1,organization_id=1),request) is None


def test_converter_route_remains_a_canonical_candidate(monkeypatch):
    from app.business_packs import common_core
    canonical="/api/v1/test/{id}"
    monkeypatch.setattr(common_core,"OPERATIONS",{**common_core.OPERATIONS,("GET",canonical):SimpleNamespace(purpose="hrms.actual_time")})
    monkeypatch.setattr(common_binding,"canonical_route",lambda request:canonical)
    request=SimpleNamespace(method="GET",scope={"route":APIRoute("/test/{id:int}",lambda:None,methods=["GET"])})
    assert common_binding.request_binding(SimpleNamespace(id=1,organization_id=1),request).route==canonical
