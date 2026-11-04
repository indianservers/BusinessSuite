"""Provider-owned event capabilities. No external event relay is involved."""

POLLING = {"telegram", "google_sheets", "excel_online"}
GRAPH = {"outlook", "onedrive", "sharepoint", "microsoft_calendar", "microsoft_teams"}
SHARED_APPS = {"slack", "whatsapp_business"}
MODES = {
    "gmail": "native_pubsub",
    "google_forms": "native_pubsub",
    "google_drive": "native_webhook",
    "google_calendar": "native_webhook",
    **{key: "native_webhook" for key in GRAPH},
    "github": "native_webhook",
    "clickup": "native_webhook",
    "box": "native_webhook",
    "airtable": "native_webhook",
    "zoho_crm": "native_webhook",
    "jira": "native_webhook",
    "slack": "native_webhook",
    "whatsapp_business": "native_webhook",
    "dropbox": "native_polling",
    "notion": "native_polling",
    "hubspot": "native_journal",
    "salesforce": "native_stream",
    "http": "native_webhook",
}
REQUIRED = {
    "gmail": ["cloud_project_id"],
    "google_forms": ["cloud_project_id", "form_id"],
    "google_calendar": ["calendar_id"],
    "onedrive": ["drive_id"],
    "sharepoint": ["site_id"],
    "microsoft_teams": ["team_id", "channel_id"],
    "github": ["owner", "repository"],
    "clickup": ["team_id"],
    "box": ["folder_id"],
    "airtable": ["base_id", "table_id"],
    "zoho_crm": ["module"],
    "slack": ["app_id"],
    "whatsapp_business": ["app_id", "business_account_id", "api_version"],
    "hubspot": ["object_type"],
    "salesforce": ["object_type", "api_version"],
}
SECRET_FIELDS = {
    "gmail": {"cloud_service_account": "Google Cloud service account JSON"},
    "google_forms": {"cloud_service_account": "Google Cloud service account JSON"},
    "slack": {
        "signing_secret": "Slack signing secret",
        "configuration_token": "Slack app configuration token",
    },
    "whatsapp_business": {"app_secret": "Meta app secret"},
    "box": {"primary_signature_key": "Box primary webhook signing key"},
    "hubspot": {"client_id":"HubSpot developer app client ID", "client_secret":"HubSpot developer app client secret"},
}
EXTRA_FIELDS = {
    "subscription_mode":{"type":"string","enum":["journal","polling"],"default":"journal","title":"HubSpot event source"},
    "cloud_project_id": {"type": "string", "title": "Google Cloud project ID"},
    "app_id": {"type": "string", "title": "Provider app ID"},
    "business_account_id": {"type": "string", "title": "WhatsApp Business Account ID"},
    "api_version": {
        "type": "string",
        "title": "Provider API version (for example v68.0)",
    },
    "stream_channel": {
        "type": "string",
        "title": "Salesforce event channel (for example /event/Order__e)",
    },
    "path": {"type": "string", "title": "Dropbox folder path (defaults to root)"},
    "request": {"type": "object", "title": "HTTP polling request"},
    "condition": {
        "type": "object",
        "title": "Column or response path/value conditions",
    },
}


def mode(module_id, setup=None):
    setup = setup or {}
    if module_id=="hubspot" and setup.get("subscription_mode")=="polling": return "native_polling"
    if module_id == "http" and setup.get("event") == "response_condition_matched":
        return "native_polling"
    if module_id == "salesforce" and setup.get("event") != "platform_event":
        return "native_polling"
    return MODES.get(module_id, "polling")


def augment_schema(module_id, schema):
    if module_id not in MODES:
        return schema
    properties = schema["properties"]
    for key in REQUIRED.get(module_id, []):
        properties.setdefault(key, EXTRA_FIELDS.get(key, {"type": "string"}))
    for key in {
        "hubspot":["subscription_mode"],
        "notion": ["condition"],
        "airtable": ["condition"],
        "salesforce": ["stream_channel"],
        "dropbox": ["path"],
        "http": ["request", "condition"],
    }.get(module_id, []):
        properties[key] = EXTRA_FIELDS[key]
    # Resource requirements can depend on the chosen event (Teams chat vs channel,
    # SharePoint list vs library). Validate them when enabling the subscription.
    properties.setdefault(
        "interval_seconds",
        {"type": "integer", "minimum": 15, "maximum": 3600, "default": 30},
    )
    return schema


def secret_fields(module_id,setup):
    if module_id=="hubspot" and mode(module_id,setup)=="native_polling": return {}
    return SECRET_FIELDS.get(module_id,{})


def validate_native(module_id, setup):
    required = list(REQUIRED.get(module_id, []))
    if module_id == "microsoft_teams" and setup.get("chat_id"):
        required = [key for key in required if key not in {"team_id", "channel_id"}]
    if module_id == "sharepoint" and not (
        setup.get("list_id") or setup.get("drive_id")
    ):
        raise ValueError("Select a SharePoint list or document-library drive")
    if module_id == "salesforce" and setup.get("event") == "platform_event":
        required = ["stream_channel", "api_version"]
    if module_id == "http" and setup.get("event") == "response_condition_matched":
        required = ["request", "condition"]
        from app.apps.power_apps.integrations.contracts import HTTPInput

        request = HTTPInput.model_validate(setup.get("request", {}))
        if request.method not in {"GET", "HEAD"} or request.max_pages != 1:
            raise ValueError("An HTTP event watch requires a single read-only request")
    missing = [key for key in required if not setup.get(key)]
    if missing:
        raise ValueError("Native trigger setup requires: " + ", ".join(missing))
    if module_id == "box" and setup["folder_id"] == "0":
        raise ValueError("Box v2 webhooks require a non-root folder")
