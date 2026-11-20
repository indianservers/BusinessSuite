"""Bounded JSON responses for Google and Outlook calendar requests."""

import httpx

from app.core.provider_responses import read_provider_json


EVENT_RESPONSE_LIMIT = 4 * 1024 * 1024
IDENTITY_RESPONSE_LIMIT = 256 * 1024


def calendar_request(client, method, url, *, expected=(200,), limit=EVENT_RESPONSE_LIMIT, headers=None, **kwargs):
    headers = httpx.Headers(headers)
    headers["Accept-Encoding"] = "identity"
    with client.stream(method, url, headers=headers, **kwargs) as response:
        data = None
        if response.status_code in expected:
            data = read_provider_json(response, limit)
            if not isinstance(data, dict):
                raise ValueError("Calendar provider must return a JSON object")
        return response.status_code, response.headers, data
