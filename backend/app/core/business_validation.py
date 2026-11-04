"""Shared company/legal field validation; format checks never assert verification."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BUSINESS = json.loads(Path(__file__).with_name("business_forms.json").read_text(encoding="utf-8"))


def business_type(value):
    if not value: return None
    key = re.sub(r"[^a-z0-9]", "", value.casefold())
    for item in BUSINESS["businessTypes"]:
        if value == item["id"] or key == re.sub(r"[^a-z0-9]", "", item["label"].casefold()): return item["id"]
    if key in BUSINESS["aliases"]: return BUSINESS["aliases"][key]
    raise ValueError("Choose a business type from the controlled list")


def website(value):
    if not value: return None
    value = value.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value): value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or "." not in parsed.hostname or parsed.username or parsed.password or re.search(r"\s", value):
        raise ValueError("Enter an HTTP/HTTPS website or domain name")
    parsed.port
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, parsed.fragment))


def registration(kind, value, country="IN"):
    value = re.sub(r"\s", "", value or "").upper()
    if not value: return value
    kind = kind.upper().replace(" ", "")
    kind = {"GST":"GSTIN", "UAETRN":"TRN"}.get(kind, kind)
    patterns = {"PAN":r"[A-Z]{5}[0-9]{4}[A-Z]", "GSTIN":r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
                "CIN":r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}", "LLPIN":r"(?:[A-Z]{3}-[0-9]{4}|F[A-Z]{2}-[0-9]{4})", "TRN":r"[0-9]{15}"}
    if kind in patterns:
        required_country = "AE" if kind == "TRN" else "IN"
        if country not in {required_country, "India" if required_country == "IN" else "United Arab Emirates"}:
            raise ValueError(f"{kind} is not applicable to the selected country")
        if not re.fullmatch(patterns[kind], value): raise ValueError(f"Enter a valid {kind} format")
    if kind == "GSTIN":
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        total = sum((n // 36 + n % 36) for n in (alphabet.index(c) * (1 + i % 2) for i, c in enumerate(value[:14])))
        if value[-1] != alphabet[(36 - total % 36) % 36]: raise ValueError("GSTIN checksum is invalid")
    return value


def bank_code(kind, value, country=None):
    value = re.sub(r"\s", "", value or "").upper()
    if not value: return value
    if kind == "IFSC" and (country and country != "IN" or not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value)):
        raise ValueError("Enter a valid Indian IFSC (11 characters)")
    if kind == "BIC" and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?", value): raise ValueError("Enter an 8- or 11-character SWIFT/BIC")
    if kind == "IBAN":
        if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", value): raise ValueError("Enter a valid IBAN")
        if country and value[:2] != country: raise ValueError("IBAN country does not match the bank country")
        expected = BUSINESS["ibanLengths"].get(value[:2])
        if expected is None or len(value) != expected: raise ValueError("IBAN length is invalid for its country")
        digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value[4:] + value[:4])
        if int(digits) % 97 != 1: raise ValueError("IBAN checksum is invalid")
    return value


def postal(value, country):
    if not value: return value
    patterns = {"IN":r"[1-9][0-9]{5}", "US":r"[0-9]{5}(?:-[0-9]{4})?", "DE":r"[0-9]{5}", "CA":r"[A-Z][0-9][A-Z] ?[0-9][A-Z][0-9]", "GB":r"[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}"}
    if country in patterns and not re.fullmatch(patterns[country], value.upper().strip()): raise ValueError("Postal code is invalid for its country")
    return value.strip()
