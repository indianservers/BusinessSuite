"""Typed versioned manifests. Candidates have no executable actions."""

from app.apps.power_apps.integrations.contracts import (
    Manifest,
    ActionSpec,
    HTTPInput,
    OutboundWebhookInput,
    DBInput,
    AIInput,
    ProviderInput,
)

CATEGORIES = [
    "Productivity",
    "Communication",
    "Email",
    "Collaboration",
    "CRM",
    "Project Management",
    "HR",
    "Finance",
    "Databases",
    "File Storage",
    "Developer Tools",
    "AI Services",
    "E-commerce",
    "Payments",
    "Webhooks and APIs",
]
AI_TASKS = {
    "generate_text": "Generate Text",
    "summarize": "Summarize Text",
    "classify": "Classify Content",
    "extract": "Extract Structured Data",
    "sentiment": "Analyze Sentiment",
    "action_items": "Identify Action Items",
    "normalize": "Normalize Data",
    "translate": "Translate Text",
    "compare": "Compare Documents",
    "json": "Generate JSON Output",
    "route": "Route by Classification",
    "explain_error": "Explain an Error",
    "draft_message": "Create Draft Message",
    "form": "Process Form Data",
    "feedback": "Analyze Feedback",
}
REGISTRY = {}
INPUTS = {}


def register(manifest, models):
    manifest = Manifest.model_validate(manifest)
    if manifest.id in REGISTRY or len({a.id for a in manifest.actions}) != len(
        manifest.actions
    ):
        raise ValueError("Duplicate connector registration")
    if set(models) != {a.id for a in manifest.actions}:
        raise ValueError("Each action requires a typed handler input contract")
    REGISTRY[manifest.id] = manifest
    for action_id, model in models.items():
        INPUTS[(manifest.id, action_id)] = model


def action(id, name, model, mutates=False, scopes=None, description=""):
    return ActionSpec(
        id=id,
        name=name,
        description=description or name,
        input_schema=model.model_json_schema(),
        output_schema={"type": "object"},
        mutates=mutates,
        scopes=scopes or [],
        idempotency="reconcile" if mutates else "read",
    )


def add(id, name, category, auth, actions, doc, setup):
    register(
        dict(
            id=id,
            name=name,
            description=f"{name} through governed server-side actions.",
            category=category,
            authentication=auth,
            actions=[a.model_dump() for a, m in actions],
            documentation_url=doc,
            setup=setup,
        ),
        {a.id: m for a, m in actions},
    )


add(
    "http",
    "HTTP API",
    "Webhooks and APIs",
    ["none", "api_key", "bearer", "basic"],
    [(action("request", "Send HTTP request", HTTPInput), HTTPInput)],
    "https://developer.mozilla.org/en-US/docs/Web/HTTP",
    [
        "Approve the exact public HTTPS hosts",
        "Choose authentication and test with a read request",
        "Non-read methods require explicit write authorization",
    ],
)
add(
    "incoming_webhook",
    "Incoming Webhooks",
    "Webhooks and APIs",
    ["signing"],
    [],
    "https://datatracker.ietf.org/doc/html/rfc2104",
    ["Configure an existing published webhook workflow in Webhook Studio"],
)
add(
    "outgoing_webhook",
    "Outgoing Webhooks",
    "Webhooks and APIs",
    ["signing", "none"],
    [(action("deliver", "Deliver webhook", OutboundWebhookInput, True), OutboundWebhookInput)],
    "https://datatracker.ietf.org/doc/html/rfc2104",
    [
        "Approve the destination host",
        "Store a signing secret",
        "Receiver must implement deduplication; uncertain deliveries are not blindly retried",
    ],
)
add(
    "postgresql",
    "PostgreSQL",
    "Databases",
    ["database"],
    [
        (action(a, n, DBInput, a in {"insert", "update", "delete"}), DBInput)
        for a, n in [
            ("test", "Test database"),
            ("inspect", "Inspect approved schema"),
            ("read", "Read records"),
            ("insert", "Insert record"),
            ("update", "Update records"),
            ("delete", "Delete records"),
        ]
    ],
    "https://www.postgresql.org/docs/current/libpq-ssl.html",
    [
        "Use a dedicated least-privilege role and verify-full TLS",
        "Approve exact host, database and table allowlist",
        "Reads are the default; writes require explicit opt-in",
    ],
)
add(
    "ai_gateway",
    "Business Suite AI Gateway",
    "AI Services",
    ["gateway"],
    [(action(a, n, AIInput), AIInput) for a, n in AI_TASKS.items()],
    "https://platform.openai.com/docs/api-reference/responses",
    [
        "Configure an approved company AI provider through the existing gateway",
        "Enable AI governance and data-sharing approval",
        "No connector credential is sent to the model",
    ],
)
add(
    "smtp",
    "Authorized SMTP",
    "Email",
    ["platform_smtp"],
    [
        (
            action("test", "Test authorized SMTP transport", ProviderInput),
            ProviderInput,
        ),
        (action("send", "Send email", ProviderInput, True), ProviderInput),
    ],
    "https://docs.python.org/3/library/smtplib.html",
    [
        "Uses the existing configured mail infrastructure",
        "A module administrator must authorize this connection",
        "Sending requires explicit confirmation and write authorization",
    ],
)
add(
    "github",
    "GitHub",
    "Developer Tools",
    ["bearer"],
    [
        (action("test", "Verify GitHub account", ProviderInput), ProviderInput),
        (
            action(
                "list_issues",
                "List repository issues",
                ProviderInput,
                scopes=["issues:read"],
            ),
            ProviderInput,
        ),
        (
            action(
                "create_issue", "Create issue", ProviderInput, True, ["issues:write"]
            ),
            ProviderInput,
        ),
    ],
    "https://docs.github.com/en/rest/issues/issues",
    [
        "Use a fine-grained personal access token with selected repositories",
        "Grant Issues read or write only as required",
        "Provider access and live verification remain pending until configured",
    ],
)
add(
    "google_sheets",
    "Google Sheets",
    "Productivity",
    ["oauth2", "service_account", "bearer"],
    [
        (
            action(
                "test",
                "Verify spreadsheet access",
                ProviderInput,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            ),
            ProviderInput,
        ),
        (
            action(
                "read_values",
                "Read values",
                ProviderInput,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            ),
            ProviderInput,
        ),
        (
            action(
                "append_rows",
                "Append rows",
                ProviderInput,
                True,
                ["https://www.googleapis.com/auth/spreadsheets"],
            ),
            ProviderInput,
        ),
    ],
    "https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append",
    [
        "Enable Google Sheets API in your own project",
        "Register the exact server callback and consent scopes",
        "Google verification/commercial policies apply to your deployment",
    ],
)
add(
    "google_drive",
    "Google Drive",
    "File Storage",
    ["oauth2", "service_account", "bearer"],
    [
        (
            action(
                "test",
                "List app-visible files",
                ProviderInput,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            ),
            ProviderInput,
        ),
        (
            action(
                "list_files",
                "List app-visible files",
                ProviderInput,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            ),
            ProviderInput,
        ),
        (
            action(
                "file_metadata",
                "Read file metadata",
                ProviderInput,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            ),
            ProviderInput,
        ),
        (
            action(
                "create_file",
                "Create text file",
                ProviderInput,
                True,
                ["https://www.googleapis.com/auth/drive.file"],
            ),
            ProviderInput,
        ),
    ],
    "https://developers.google.com/workspace/drive/api/guides/api-specific-auth",
    [
        "Use drive.file for app-created or explicitly shared files",
        "Register an OAuth application or approved service account",
        "This adapter does not request unrestricted Drive access",
    ],
)
add(
    "outlook",
    "Microsoft Outlook",
    "Email",
    ["oauth2", "bearer"],
    [
        (
            action("test", "Verify account", ProviderInput, scopes=["User.Read"]),
            ProviderInput,
        ),
        (
            action(
                "list_messages",
                "List message summaries",
                ProviderInput,
                scopes=["Mail.ReadBasic"],
            ),
            ProviderInput,
        ),
        (
            action("send_mail", "Submit email", ProviderInput, True, ["Mail.Send"]),
            ProviderInput,
        ),
    ],
    "https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0",
    [
        "Register a confidential Entra application and exact callback",
        "Request only selected delegated scopes and offline_access",
        "A 202 response means accepted, not confirmed delivery",
    ],
)

CANDIDATES = {
    "Slack": "Communication",
    "Microsoft Teams": "Communication",
    "Discord": "Communication",
    "Telegram": "Communication",
    "Gmail": "Email",
    "Google Calendar": "Productivity",
    "Microsoft Calendar": "Productivity",
    "Excel Online": "Productivity",
    "OneDrive": "File Storage",
    "Dropbox": "File Storage",
    "Amazon S3": "File Storage",
    "Jira": "Project Management",
    "Trello": "Project Management",
    "Asana": "Project Management",
    "ClickUp": "Project Management",
    "Monday.com": "Project Management",
    "HubSpot": "CRM",
    "Salesforce": "CRM",
    "Pipedrive": "CRM",
    "Zoho CRM": "CRM",
    "GitLab": "Developer Tools",
    "MySQL": "Databases",
    "Microsoft SQL Server": "Databases",
    "OpenAI-compatible provider": "AI Services",
    "Razorpay": "Payments",
    "Stripe": "Payments",
}
NATIVE = {
    name: {
        "events": events,
        "actions": actions,
        "permission_namespace": permission,
        "active": False,
    }
    for name, events, actions, permission in [
        (
            "PMS",
            ["task.created", "task.updated", "task.completed"],
            ["createTask", "updateTask"],
            "pms",
        ),
        ("CRM", ["lead.created", "deal.updated"], ["createFollowUp"], "crm"),
        (
            "HRMS",
            ["employee.created", "leave.requested"],
            ["createOnboardingTask"],
            "hrms",
        ),
        (
            "InternHub",
            ["intern.approved", "submission.created", "review.completed"],
            [],
            "interns",
        ),
        ("Sales", [], [], "srm"),
        ("Finance", [], [], "fam"),
        ("Documents", [], [], "documents"),
        ("Communication", [], [], "communication"),
    ]
}


def catalog(include_candidates=False):
    items = [m.model_dump() for m in REGISTRY.values()]
    if include_candidates:
        items += [
            Manifest(
                id="candidate_" + name.lower().replace(" ", "_").replace(".", "_"),
                name=name,
                description="Integration candidate; no executor or live connection is claimed.",
                category=category,
                availability="In Development",
                authentication=[],
                documentation_url="",
                setup=[
                    "Provider/authentication review and adapter implementation are pending"
                ],
                live_verification="Not implemented",
            ).model_dump()
            for name, category in CANDIDATES.items() if name not in {m.name for m in REGISTRY.values()}
        ]
    return items


def get_action(connector_id, action_id):
    manifest = REGISTRY.get(connector_id)
    result = (
        next((a for a in manifest.actions if a.id == action_id), None)
        if manifest
        else None
    )
    if not result:
        raise ValueError("Unsupported connector action")
    return result


from app.apps.power_apps.integrations.providers import install as install_providers
install_providers(add, action)
