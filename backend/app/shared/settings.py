"""Layered policy resolution. Lower layers may tighten mandatory limits."""

from fastapi import HTTPException
from app.shared.models import ServicePolicy
from app.models.company import Company

DEFAULTS = {
    "country": "India",
    "currency": "INR",
    "timezone": "Asia/Kolkata",
    "language": "en",
    "date_format": "yyyy-MM-dd",
    "upload_limit_mb": 10,
    "workflow_max_nodes": 60,
    "workflow_max_steps": 200,
    "workflow_retries": 3,
    "notification_channels": ["in_app"],
    "quiet_start": None,
    "quiet_end": None,
    "ai_daily_requests": 100,
    "security_notifications_required": True,
}
LIMITS = {
    "upload_limit_mb",
    "workflow_max_nodes",
    "workflow_max_steps",
    "workflow_retries",
    "ai_daily_requests",
}


def validate(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise HTTPException(422, "Unknown shared setting")
    for key in LIMITS & values.keys():
        if type(values[key]) is not int or not 1 <= values[key] <= 10000:
            raise HTTPException(422, "Limits must be positive bounded integers")
    if "notification_channels" in values and (
        not isinstance(values["notification_channels"], list)
        or any(
            not isinstance(channel, str) for channel in values["notification_channels"]
        )
        or set(values["notification_channels"]) - {"in_app", "email"}
    ):
        raise HTTPException(
            422, "Only in-app and configured email channels are supported"
        )
    if (
        "security_notifications_required" in values
        and values["security_notifications_required"] is not True
    ):
        raise HTTPException(422, "Security notifications cannot be disabled")
    for key in ("quiet_start", "quiet_end"):
        if values.get(key) is not None and (
            type(values[key]) is not int or not 0 <= values[key] <= 23
        ):
            raise HTTPException(422, "Quiet hours must be hours from 0 to 23")
    if "timezone" in values:
        from app.access.control import validate_timezone

        validate_timezone(values["timezone"])
    for key in (
        set(values)
        - LIMITS
        - {
            "notification_channels",
            "security_notifications_required",
            "quiet_start",
            "quiet_end",
        }
    ):
        if not isinstance(values[key], str) or not 1 <= len(values[key]) <= 100:
            raise HTTPException(422, "Invalid configuration text")


def effective(db, company, module):
    result = dict(DEFAULTS)
    org = db.get(Company, company)
    source = {}
    for key in ("platform", f"company:{company}", f"company:{company}:module:{module}"):
        if key == f"company:{company}" and org:
            result.update(
                country=org.country,
                currency=org.default_currency,
                timezone=org.default_timezone,
            )
        policy = (
            db.query(ServicePolicy).filter_by(scope_key=key, kind="settings").first()
        )
        if policy:
            for name, value in policy.values_json.items():
                if name in LIMITS:
                    result[name] = min(result[name], value)
                elif name == "notification_channels":
                    result[name] = (
                        list(set(result[name]) & set(value))
                        if key != "platform"
                        else value
                    )
                elif name == "security_notifications_required":
                    result[name] = True
                else:
                    result[name] = value
                source[name] = {"scope": key, "version": policy.version}
    return {
        "values": result,
        "sources": source,
        "precedence": ["platform", "company", "module", "authorized user preference"],
        "userOverridesSupported": False,
    }
