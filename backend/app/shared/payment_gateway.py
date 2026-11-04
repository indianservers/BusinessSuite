"""Provider boundary. Razorpay remains disconnected until explicitly configured.

Official API: https://razorpay.com/docs/api/payments/payment-links/
Credentials are server-only and bound to one explicit seller organization.
"""
import hashlib
import re
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from app.core.config import settings


def provider_reference(row):
    # Razorpay reference IDs are bounded; namespace client idempotency keys by
    # organization even if a deployment later moves to a different merchant.
    value = f"{row.organization_id}:{row.request_id}"
    return "bs_" + hashlib.sha256(value.encode()).hexdigest()[:36]


def gateway_for(organization_id):
    if (settings.PAYMENT_GATEWAY_PROVIDER == "razorpay"
        and settings.PAYMENT_GATEWAY_ORGANIZATION_ID == organization_id
        and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        return RazorpayGateway(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    return None


class RazorpayGateway:
    name = "razorpay"
    currencies = {"INR"}

    def __init__(self, key_id, secret):
        self.key_id, self.secret = key_id, secret
        self.account = hashlib.sha256(key_id.encode()).hexdigest()
        self.test_mode = key_id.startswith("rzp_test_")

    def request(self, method, path, *, body=None, params=None):
        # Fixed provider host, TLS verification, no redirects, no client-supplied URLs.
        try:
            with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
                response = client.request(method, "https://api.razorpay.com/v1/payment_links/" + path,
                    auth=(self.key_id, self.secret), json=body, params=params)
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError("Oversized provider response")
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid provider response")
                return data
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "Payment provider outcome is unavailable. Reconcile the existing request before trying another payment link.") from None

    def find(self, reference):
        result = self.request("GET", "", params={"reference_id": reference})
        rows = result.get("payment_links", [])
        if not isinstance(rows, list):
            raise HTTPException(502, "Payment provider returned an invalid link list.")
        return next((row for row in rows if isinstance(row, dict) and row.get("reference_id") == reference), None)

    def create(self, row):
        if row.currency != "INR":
            raise HTTPException(422, "This Razorpay connection currently supports INR payment requests.")
        return self.request("POST", "", body={
            "reference_id": provider_reference(row),
            "amount": int(row.amount * 100), "currency": row.currency,
            "accept_partial": False, "description": f"Payment for {row.reference}"[:255],
            "notify": {"sms": False, "email": False}, "reminder_enable": False,
        })

    def fetch(self, provider_id):
        if not re.fullmatch(r"plink_[A-Za-z0-9]+", provider_id or ""):
            raise HTTPException(409, "Payment link reference is invalid.")
        return self.request("GET", provider_id)

    def cancel(self, provider_id):
        if not re.fullmatch(r"plink_[A-Za-z0-9]+", provider_id or ""):
            raise HTTPException(409, "Payment link reference is invalid.")
        return self.request("POST", provider_id + "/cancel", body={})


def verified_link(row, data):
    """Never trust browser redirects, or mismatched provider references/amounts."""
    from decimal import Decimal
    if (not isinstance(data, dict) or data.get("reference_id") != provider_reference(row)
        or data.get("currency") != row.currency or type(data.get("amount")) is not int or data.get("amount") != int(row.amount * 100)
        or not re.fullmatch(r"plink_[A-Za-z0-9]+", str(data.get("id", "")))
        or row.provider_id and row.provider_id != data.get("id")):
        raise HTTPException(409, "Payment provider returned a different reference, currency or amount. Reconciliation is required.")
    try:
        url = urlsplit(str(data.get("short_url") or ""))
        safe_url = url.scheme == "https" and url.hostname in {"rzp.io", "rzp.es", "razorpay.com"} and not url.username and not url.password and url.port in {None, 443}
    except ValueError:
        safe_url = False
    if not safe_url:
        raise HTTPException(409, "Payment provider did not return a valid hosted payment link.")
    paid = data.get("amount_paid", 0)
    if not isinstance(paid, int) or isinstance(paid, bool) or not 0 <= paid <= int(row.amount * 100):
        raise HTTPException(409, "Payment provider returned an invalid paid amount.")
    status = data.get("status")
    if status == "paid" and paid != int(row.amount * 100):
        raise HTTPException(409, "Payment total has not been verified.")
    states = {"created": "link_ready", "paid": "gateway_paid", "partially_paid": "partially_paid", "cancelled": "cancelled", "expired": "expired"}
    if status not in states:
        raise HTTPException(409, "Payment provider status requires reconciliation.")
    row.provider_id, row.payment_url = data["id"], data["short_url"]
    row.amount_paid, row.status = Decimal(paid) / 100, states[status]
