"""Bound remote JSON responses before parsing them."""

import json

import httpx


class ProviderResponseTooLarge(ValueError):
    pass


def read_provider_json(response: httpx.Response, max_bytes: int):
    """Read an identity-encoded response without buffering it in HTTPX."""
    encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
    if encoding != "identity":
        raise ValueError("Unexpected provider response encoding")
    body = bytearray()
    for chunk in response.iter_bytes():
        if len(body) + len(chunk) > max_bytes:
            raise ProviderResponseTooLarge("Provider response exceeds the size limit")
        body.extend(chunk)
    return json.loads(body)
