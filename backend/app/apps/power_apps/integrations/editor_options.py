"""Editor options describe the fields actually consumed by each adapter/action.

Keep the shared runtime input models backwards compatible; publish narrow schemas
so both the workflow inspector and Integration Studio render the same options.
"""
from copy import deepcopy

ACTION_FIELDS = {
    "github": {"test": [], "list_issues": ["owner", "repository", "limit", "page_token"], "create_issue": ["owner", "repository", "title", "text"]},
    "google_sheets": {"test": ["spreadsheet_id"], "read_values": ["spreadsheet_id", "range"], "append_rows": ["spreadsheet_id", "range", "values"]},
    "google_drive": {"test": ["limit", "page_token"], "list_files": ["limit", "page_token"], "file_metadata": ["file_id"], "create_file": ["name", "content", "parent_id"]},
    "outlook": {"test": [], "list_messages": ["limit", "page_token"], "send_mail": ["recipient", "subject", "text"]},
    "smtp": {"test": [], "send": ["recipient", "subject", "text"]},
    "postgresql": {"test": [], "inspect": [], "read": ["schema_name", "table", "columns", "where", "limit", "offset"], "insert": ["schema_name", "table", "values"], "update": ["schema_name", "table", "values", "where"], "delete": ["schema_name", "table", "where"]},
}
REQUIRED_FIELDS = {
    ("github", "list_issues"): ["owner", "repository"],
    ("github", "create_issue"): ["owner", "repository", "title"],
    ("google_sheets", "test"): ["spreadsheet_id"],
    ("google_sheets", "read_values"): ["spreadsheet_id", "range"],
    ("google_sheets", "append_rows"): ["spreadsheet_id", "range", "values"],
    ("google_drive", "file_metadata"): ["file_id"],
    ("google_drive", "create_file"): ["name"],
    ("outlook", "send_mail"): ["recipient", "subject", "text"],
    ("smtp", "send"): ["recipient", "subject", "text"],
}
AUTH_FIELDS = {
    "none": {}, "oauth2": {}, "gateway": {}, "platform_smtp": {},
    "bearer": {"access_token": "Access token"},
    "api_key": {"api_key": "API key"},
    "basic": {"username": "Username", "password": "Password"},
    "database": {"username": "Database username", "password": "Database password"},
    "signing": {"signing_secret": "Signing secret"},
    "service_account": {"service_account": "Service account JSON"},
}
TOKEN_LABELS = {
    "telegram": "Bot token", "slack": "Bot OAuth token", "discord": "Bot token",
    "github": "Personal access token", "gitlab": "Personal access token",
    "google_sheets": "Google access token", "google_drive": "Google access token",
    "gmail": "Google access token", "outlook": "Microsoft access token",
    "openai": "OpenAI API key", "anthropic": "Anthropic API key",
    "groq": "Groq API key", "openrouter": "OpenRouter API key",
    "stripe": "Stripe secret key", "sendgrid": "SendGrid API key",
    "resend": "Resend API key", "brevo": "Brevo API key", "postmark": "Server API token",
}


def narrow_action_schemas(registry):
    from app.apps.power_apps.integrations.automation_catalog import INSTALLED
    for connector in registry.values():
        for action in connector.actions:
            if (connector.id, action.id) in INSTALLED and connector.id in ACTION_FIELDS:
                ACTION_FIELDS[connector.id][action.id] = list(action.input_schema.get("properties", {}))
            fields = ACTION_FIELDS.get(connector.id, {}).get(action.id)
            if connector.id == "ai_gateway":
                fields = ["input", "instruction", "token_budget"]
                if action.id in {"classify", "route"}: fields += ["categories"]
                if action.id == "translate": fields += ["target_language"]
                if action.id == "compare": fields += ["document_b"]
                if action.id in {"extract", "normalize", "json", "form"}: fields += ["output_schema"]
            if fields is None:
                continue
            schema = deepcopy(action.input_schema)
            properties = schema.get("properties", {})
            schema["properties"] = {key: properties[key] for key in fields}
            required = REQUIRED_FIELDS.get((connector.id, action.id), [key for key in schema.get("required", []) if key in fields])
            if connector.id == "postgresql" and action.id not in {"test", "inspect"}:
                required = ["table"] + (["values"] if action.id in {"insert", "update"} else []) + (["where"] if action.id in {"update", "delete"} else [])
            if connector.id == "ai_gateway":
                required = ["input"] + [key for key in fields if key in {"categories", "document_b", "output_schema"}]
            schema["required"] = required
            action.input_schema = schema


def connection_schema(connector):
    properties = {}
    required = []
    if connector.id in {"http", "outgoing_webhook", "postgresql"}:
        properties["hosts"] = {"type": "array", "title": "Allowed hostnames", "items": {"type": "string"}, "default": []}
        required.append("hosts")
    if "api_key" in connector.authentication:
        properties["header_name"] = {"type": "string", "title": "API key header", "default": "X-API-Key"}
    if connector.id == "postgresql":
        properties.update(database={"type": "string", "title": "Database name"}, port={"type": "integer", "title": "Port", "default": 5432}, tables={"type": "array", "title": "Approved tables (schema.table)", "items": {"type": "string"}, "default": []})
        required += ["database", "tables"]
    if connector.id == "google_sheets":
        properties["spreadsheet_id"] = {"type": "string", "title": "Default spreadsheet ID"}
    if connector.id == "ai_gateway":
        properties["provider"] = {"type": "string", "title": "Approved company AI provider", "default": "openai"}
    if connector.id in {"salesforce", "jira", "zoho_crm"}:
        properties["provider_host"] = {"type": "string", "title": "Provider hostname (without https://)"}
        required.append("provider_host")
    if connector.id == "dropbox":
        properties["team_member_id"] = {"type": "string", "title": "Team member ID (optional)"}
        properties["namespace_id"] = {"type": "string", "title": "Root namespace ID (optional)"}
    return {"type": "object", "properties": properties, "required": required}


def editor_options(connector):
    credentials = {auth: deepcopy(AUTH_FIELDS[auth]) for auth in connector.authentication}
    if "bearer" in credentials:
        credentials["bearer"]["access_token"] = TOKEN_LABELS.get(connector.id, f"{connector.name} API token")
    if connector.id == "razorpay":
        credentials["basic"] = {"username": "Razorpay key ID", "password": "Razorpay key secret"}
    writes = [action.name for action in connector.actions if action.mutates]
    return {
        "credentials": credentials,
        "config_schema": connection_schema(connector),
        "write_actions": writes,
        "dynamic_writes": connector.id == "http",
    }
