"""Provider change feeds and conditional writes used by the local sync worker."""
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import httpx

from . import google_calendar, outlook_calendar

UTC = timezone.utc
PROPERTY = "String {4a19d149-9d27-4c40-8666-a57867578598} Name BusinessSuiteKey"


class CalendarSyncError(Exception):
    def __init__(self, message, *, retry_after=0, conflict=False, reset=False):
        super().__init__(message)
        self.retry_after = retry_after
        self.conflict = conflict
        self.reset = reset


def iso(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def remote_value(provider, event):
    if event.get("status") == "cancelled" or event.get("isCancelled") or "@removed" in event:
        return {"deleted": True}
    if provider == "google":
        def stamp(part):
            value = part.get("dateTime") or part.get("date")
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(part.get("timeZone") or "UTC"))
            return iso(dt)
        return {"title": event.get("summary") or "Untitled event", "description": event.get("description") or "",
                "location": event.get("location") or "", "start": stamp(event["start"]), "end": stamp(event["end"]),
                "deleted": False, "all_day": "date" in event["start"]}
    def stamp(part):
        # Requests explicitly ask Graph to return UTC; never treat local machine time as event time.
        dt = datetime.fromisoformat(part["dateTime"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC if part.get("timeZone") in (None, "UTC", "Etc/UTC") else ZoneInfo(part["timeZone"]))
        return iso(dt)
    return {"title": event.get("subject") or "Untitled event",
            "description": (event.get("body") or {}).get("content") or event.get("bodyPreview") or "",
            "location": (event.get("location") or {}).get("displayName") or "",
            "start": stamp(event["start"]), "end": stamp(event["end"]), "deleted": False,
            "all_day": bool(event.get("isAllDay"))}


class CalendarTransport:
    def __init__(self, integration, persist_tokens=lambda: None):
        self.integration = integration
        self.provider = integration.provider
        self.auth = google_calendar if self.provider == "google" else outlook_calendar
        self.persist_tokens = persist_tokens
        self.base = ("https://www.googleapis.com/calendar/v3/calendars/primary/events" if self.provider == "google"
                     else "https://graph.microsoft.com/v1.0/me/events")
        self.client = httpx.Client(timeout=20, follow_redirects=False)

    def close(self):
        self.client.close()

    def token(self, force=False):
        row = self.integration
        expires = row.expires_at
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if force or not expires or expires <= datetime.now(UTC) + timedelta(seconds=60):
            if not row.refresh_token_encrypted:
                raise CalendarSyncError("Calendar access expired. Reconnect your account.")
            refresh = self.auth.cipher().decrypt(row.refresh_token_encrypted.encode()).decode()
            self.auth.store_tokens(row, self.auth.token_request({"grant_type": "refresh_token", "refresh_token": refresh}))
            # Refresh token rotation must survive later request failures.
            self.persist_tokens()
        return self.auth.cipher().decrypt(row.access_token_encrypted.encode()).decode()

    def request(self, method, url, *, allow_missing=False, **kwargs):
        parsed = urlparse(url)
        expected = urlparse(self.base)
        if parsed.scheme != "https" or parsed.netloc != expected.netloc or parsed.username or parsed.password:
            raise CalendarSyncError("Calendar returned an invalid continuation URL.")
        extra = kwargs.pop("headers", {})
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self.token(force=bool(attempt))}", **extra}
            if self.provider == "outlook":
                headers["Prefer"] = 'outlook.timezone="UTC", outlook.body-content-type="text", IdType="ImmutableId"'
            try:
                response = self.client.request(method, url, headers=headers, **kwargs)
            except httpx.RequestError:
                raise CalendarSyncError("Calendar could not be reached. Automatic retry is scheduled.") from None
            if response.status_code != 401 or attempt:
                break
        if allow_missing and response.status_code in (404, 410):
            return None
        if response.status_code == 410:
            raise CalendarSyncError("Calendar checkpoint expired; a fresh scan is scheduled.", reset=True)
        if response.status_code in (409, 412):
            raise CalendarSyncError("Both copies changed. Review this event's conflict.", conflict=True)
        if response.status_code >= 400:
            try:
                delay = min(86400, max(0, int(response.headers.get("Retry-After", "0"))))
            except ValueError:
                delay = 60
            raise CalendarSyncError(f"Calendar request failed (HTTP {response.status_code}). Reconnect if access was revoked.", retry_after=delay)
        return response.json() if response.status_code != 204 else {}

    def get(self, event_id):
        return self.request("GET", f"{self.base}/{quote(event_id, safe='')}", allow_missing=True)

    def changes(self, cursor, start, end):
        """Yield pages; only the final page's checkpoint is a completed change round."""
        if self.provider == "google":
            url = self.base
            params = {"showDeleted": "true", "singleEvents": "true", "maxResults": 250}
            if cursor:
                params["syncToken"] = cursor
            else:
                params.update(timeMin=iso(start), timeMax=iso(end))
        else:
            url = cursor or "https://graph.microsoft.com/v1.0/me/calendarView/delta"
            params = None if cursor else {"startDateTime": iso(start), "endDateTime": iso(end)}
        seen = set()
        while True:
            signature = (url, str(params))
            if signature in seen:
                raise CalendarSyncError("Calendar repeated a continuation page. Automatic retry is scheduled.")
            seen.add(signature)
            result = self.request("GET", url, params=params)
            if self.provider == "google":
                next_page = result.get("nextPageToken")
                yield result.get("items", []), result.get("nextSyncToken"), not next_page
                if not next_page:
                    break
                params = {**params, "pageToken": next_page}
            else:
                next_page = result.get("@odata.nextLink")
                yield result.get("value", []), result.get("@odata.deltaLink"), not next_page
                if not next_page:
                    break
                url, params = next_page, None

    def identity(self, module, local_id):
        local_key = str(local_id) if module == "crm" else f"pms:{local_id}"
        return hashlib.sha256(f"business-suite:{self.integration.organization_id}:{self.integration.id}:{local_key}".encode()).hexdigest()

    def find(self, module, local_id, key=None):
        key = key or self.identity(module, local_id)
        if self.provider == "google":
            return self.get(key)
        # Graph transactionId is an idempotency key, not a supported query filter.
        result = self.request("GET", self.base, params={
            "$filter": f"singleValueExtendedProperties/Any(ep: ep/id eq '{PROPERTY}' and ep/value eq '{key}')",
            "$expand": f"singleValueExtendedProperties($filter=id eq '{PROPERTY}')",
        })
        return next(iter(result.get("value", [])), None)

    def write(self, module, local_id, value, event_id=None, etag=None, create_key=None):
        headers = {"If-Match": etag} if etag else {}
        if value.get("deleted"):
            if event_id:
                self.request("DELETE", f"{self.base}/{quote(event_id, safe='')}", headers=headers, allow_missing=True)
            return {"id": event_id, "status": "cancelled"}
        key = create_key or self.identity(module, local_id)
        if self.provider == "google":
            def part(stamp):
                return {"date": stamp[:10]} if value.get("all_day") else {"dateTime": stamp}
            body = {"summary": value["title"], "description": value["description"], "location": value["location"],
                    "start": part(value["start"]), "end": part(value["end"]),
                    "extendedProperties": {"private": {"businessSuiteKey": key}}}
        else:
            def part(stamp):
                return {"dateTime": datetime.fromisoformat(stamp).astimezone(UTC).replace(tzinfo=None).isoformat(), "timeZone": "UTC"}
            body = {"subject": value["title"], "body": {"contentType": "text", "content": value["description"]},
                    "location": {"displayName": value["location"]}, "isAllDay": bool(value.get("all_day")),
                    "start": part(value["start"]), "end": part(value["end"])}
            if value.get("all_day"):
                # Graph requires midnight boundaries for all-day writes. Date edits in the
                # local planner select UTC calendar dates; title-only edits retain provider timezone.
                body["start"]["dateTime"] = value["start"][:10] + "T00:00:00"
                body["end"]["dateTime"] = value["end"][:10] + "T00:00:00"
                if body["end"]["dateTime"] <= body["start"]["dateTime"]:
                    body["end"]["dateTime"] = (datetime.fromisoformat(body["start"]["dateTime"]) + timedelta(days=1)).isoformat()
        if event_id:
            if value.get("preserve_schedule"):
                for field in ("start", "end", "isAllDay"):
                    body.pop(field, None)
            return self.request("PATCH", f"{self.base}/{quote(event_id, safe='')}", json=body, headers=headers)
        if self.provider == "google":
            body["id"] = key
        else:
            body.update(transactionId=key, singleValueExtendedProperties=[{"id": PROPERTY, "value": key}])
        return self.request("POST", self.base, json=body)
