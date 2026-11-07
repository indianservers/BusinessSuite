from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from copy import deepcopy
import httpx
import pytest

from app.apps.crm.calendar_transport import CalendarTransport, CalendarSyncError, remote_value, PROPERTY
from app.apps.crm.google_calendar import store_tokens

UTC = timezone.utc


def transport(monkeypatch, provider, handler):
    real = httpx.Client
    monkeypatch.setattr("app.apps.crm.calendar_transport.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    row = SimpleNamespace(id=2, organization_id=1, provider=provider, access_token_encrypted=None, refresh_token_encrypted=None)
    store_tokens(row, {"access_token":"token","refresh_token":"refresh"})
    return CalendarTransport(row)


def test_google_pagination_checkpoint_and_conditional_write(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        if request.method == "GET":
            assert request.url.params["syncToken"] == "previous"
            assert "timeMin" not in request.url.params
            if "pageToken" not in request.url.params:
                return httpx.Response(200, json={"items":[{"id":"one","status":"cancelled"}],"nextPageToken":"page2"})
            return httpx.Response(200,json={"items":[],"nextSyncToken":"final"})
        assert request.headers["If-Match"] == '"etag"'
        return httpx.Response(412)
    t = transport(monkeypatch,"google",handler)
    try:
        now = datetime.now(UTC)
        pages = list(t.changes("previous",now,now+timedelta(days=1)))
        assert pages[0][2] is False and pages[1][1] == "final"
        with pytest.raises(CalendarSyncError) as error:
            t.write("crm",1,{"deleted":True},"one",'"etag"')
        assert error.value.conflict
    finally: t.close()


def test_outlook_delta_links_and_marker_lookup(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        assert 'IdType="ImmutableId"' in request.headers["Prefer"]
        if request.url.path.endswith('/events'):
            assert "singleValueExtendedProperties/Any" in request.url.params["$filter"]
            assert PROPERTY in request.url.params["$filter"]
            return httpx.Response(200,json={"value":[{"id":"found"}]})
        if "page" not in request.url.params:
            return httpx.Response(200,json={"value":[],"@odata.nextLink":"https://graph.microsoft.com/v1.0/me/calendarView/delta?page=2"})
        return httpx.Response(200,json={"value":[],"@odata.deltaLink":"https://graph.microsoft.com/v1.0/me/calendarView/delta?token=done"})
    t = transport(monkeypatch,"outlook",handler)
    try:
        now = datetime.now(UTC)
        pages = list(t.changes(None,now,now+timedelta(days=1)))
        assert pages[-1][1].endswith('token=done')
        assert t.find("pms",4)["id"] == "found"
    finally: t.close()


@pytest.mark.parametrize("status,attribute", [(410,"reset"),(429,"retry_after"),(412,"conflict")])
def test_provider_error_classification(monkeypatch,status,attribute):
    t = transport(monkeypatch,"google",lambda request:httpx.Response(status,headers={"Retry-After":"120"},json={"error":"sensitive provider response"}))
    try:
        with pytest.raises(CalendarSyncError) as error: t.request("GET",t.base)
        assert getattr(error.value,attribute)
        assert "sensitive" not in str(error.value)
    finally: t.close()


def test_untrusted_continuation_never_receives_credentials(monkeypatch):
    calls = []
    t = transport(monkeypatch,"outlook",lambda request:calls.append(request))
    try:
        with pytest.raises(CalendarSyncError): t.request("GET","https://attacker.example/steal")
        assert calls == []
    finally: t.close()


def test_refresh_rotation_persisted_before_network_failure(monkeypatch):
    def failure(request): raise httpx.ConnectError("offline", request=request)
    t = transport(monkeypatch,"outlook",failure)
    t.integration.expires_at = datetime.now(UTC)-timedelta(seconds=1)
    monkeypatch.setattr(t.auth,"token_request",lambda data:{"access_token":"new","refresh_token":"rotated"})
    saved = []
    t.persist_tokens = lambda:saved.append(t.integration.refresh_token_encrypted)
    try:
        with pytest.raises(CalendarSyncError): t.get("id")
        assert t.auth.cipher().decrypt(saved[0].encode()) == b"rotated"
    finally: t.close()


def test_all_day_dates_and_utc_normalization():
    value = remote_value("google",{"summary":"Holiday","start":{"date":"2026-11-10"},"end":{"date":"2026-11-11"}})
    assert value["all_day"] and value["start"] == "2026-11-10T00:00:00+00:00"
    value = remote_value("outlook",{"subject":"Call","start":{"dateTime":"2026-11-10T09:00:00.0000000","timeZone":"UTC"},"end":{"dateTime":"2026-11-10T10:00:00","timeZone":"UTC"}})
    assert value["start"] == "2026-11-10T09:00:00+00:00"


def test_outlook_title_edit_preserves_all_day_timezone(monkeypatch):
    import json
    bodies = []
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id":"event"})
    t = transport(monkeypatch, "outlook", handler)
    try:
        t.write("crm", 1, {"title":"Renamed", "description":"", "location":"", "all_day":True,
            "start":"2026-11-09T18:30:00+00:00", "end":"2026-11-10T18:30:00+00:00", "preserve_schedule":True}, "event", "etag")
        assert bodies[0]["subject"] == "Renamed"
        assert not {"start","end","isAllDay"}.intersection(bodies[0])
    finally: t.close()
