"""Fixed-origin provider actions; no user-supplied URLs or executable code."""

import json
import re
from urllib.parse import quote, urlencode
from pydantic import Field, create_model
from app.apps.power_apps.integrations.contracts import Strict, IntegrationFailure

# Path slots are escaped as individual segments. Body fields remain provider JSON.
PROFILES = {}
MODELS = {}


def profile(
    id,
    name,
    category,
    host,
    doc,
    actions,
    *,
    headers=None,
    auth="bearer",
    prefix="Bearer",
    scopes=None
):
    PROFILES[id] = dict(
        id=id,
        name=name,
        category=category,
        host=host,
        documentation=doc,
        actions=actions,
        headers=headers or {},
        auth=auth,
        prefix=prefix,
        scopes=scopes or [],
    )


def a(id, label, method, path, fields="", *, body=None, query=None, transform=None):
    return dict(
        id=id,
        label=label,
        method=method,
        path=path,
        fields=fields.split(),
        body=body or {},
        query=query or {},
        transform=transform,
    )


G = "https://www.googleapis.com/auth/"
profile(
    "google_forms",
    "Google Forms",
    "Productivity",
    "forms.googleapis.com",
    "https://developers.google.com/workspace/forms/api/reference/rest",
    [
        a("get_form", "Read form", "GET", "/v1/forms/{form_id}", "form_id"),
        a(
            "list_responses",
            "Read form responses",
            "GET",
            "/v1/forms/{form_id}/responses",
            "form_id",
        ),
        a("create_form", "Create form", "POST", "/v1/forms", "title", transform="form"),
    ],
    scopes=[G + "forms.body", G + "forms.responses.readonly"],
)
profile(
    "gmail",
    "Gmail",
    "Email",
    "gmail.googleapis.com",
    "https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send",
    [
        a("test", "Verify Gmail account", "GET", "/gmail/v1/users/me/profile"),
        a(
            "send_mail",
            "Send email",
            "POST",
            "/gmail/v1/users/me/messages/send",
            "to subject text",
            transform="gmail",
        ),
    ],
    scopes=[G + "gmail.send", G + "gmail.metadata"],
)
profile(
    "google_calendar",
    "Google Calendar",
    "Productivity",
    "www.googleapis.com",
    "https://developers.google.com/workspace/calendar/api/v3/reference/events/insert",
    [
        a(
            "list_events",
            "List calendar events",
            "GET",
            "/calendar/v3/calendars/{calendar_id}/events",
            "calendar_id",
        ),
        a(
            "create_event",
            "Create event",
            "POST",
            "/calendar/v3/calendars/{calendar_id}/events",
            "calendar_id summary starts_at ends_at",
            transform="calendar",
        ),
    ],
    scopes=[G + "calendar.events"],
)
profile(
    "google_docs",
    "Google Docs",
    "Productivity",
    "docs.googleapis.com",
    "https://developers.google.com/workspace/docs/api/reference/rest/v1/documents",
    [
        a(
            "get_document",
            "Read document",
            "GET",
            "/v1/documents/{document_id}",
            "document_id",
        ),
        a(
            "create_document",
            "Create document",
            "POST",
            "/v1/documents",
            "title",
            body={"title": "title"},
        ),
    ],
    scopes=[G + "documents"],
)
profile(
    "google_slides",
    "Google Slides",
    "Productivity",
    "slides.googleapis.com",
    "https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations",
    [
        a(
            "get_presentation",
            "Read presentation",
            "GET",
            "/v1/presentations/{presentation_id}",
            "presentation_id",
        ),
        a(
            "create_presentation",
            "Create presentation",
            "POST",
            "/v1/presentations",
            "title",
            body={"title": "title"},
        ),
    ],
    scopes=[G + "presentations"],
)
profile(
    "google_tasks",
    "Google Tasks",
    "Productivity",
    "tasks.googleapis.com",
    "https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert",
    [
        a(
            "list_tasks",
            "List tasks",
            "GET",
            "/tasks/v1/lists/{task_list_id}/tasks",
            "task_list_id",
        ),
        a(
            "create_task",
            "Create task",
            "POST",
            "/tasks/v1/lists/{task_list_id}/tasks",
            "task_list_id title",
            body={"title": "title"},
        ),
    ],
    scopes=[G + "tasks"],
)
profile(
    "google_contacts",
    "Google Contacts",
    "Productivity",
    "people.googleapis.com",
    "https://developers.google.com/people/api/rest/v1/people/createContact",
    [
        a(
            "list_contacts",
            "List contacts",
            "GET",
            "/v1/people/me/connections",
            query={"personFields": "names,emailAddresses"},
        ),
        a(
            "create_contact",
            "Create contact",
            "POST",
            "/v1/people:createContact",
            "name email",
            transform="contact",
        ),
    ],
    scopes=[G + "contacts"],
)
profile(
    "google_chat",
    "Google Chat",
    "Communication",
    "chat.googleapis.com",
    "https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create",
    [
        a("list_spaces", "List spaces", "GET", "/v1/spaces"),
        a(
            "send_message",
            "Send message",
            "POST",
            "/v1/spaces/{space_id}/messages",
            "space_id text",
            body={"text": "text"},
        ),
    ],
    scopes=[G + "chat.spaces.readonly", G + "chat.messages.create"],
)
profile(
    "slack",
    "Slack",
    "Communication",
    "slack.com",
    "https://docs.slack.dev/reference/methods/chat.postMessage",
    [
        a("test", "Verify Slack identity", "POST", "/api/auth.test"),
        a(
            "send_message",
            "Send channel message",
            "POST",
            "/api/chat.postMessage",
            "channel text",
            body={"channel": "channel", "text": "text"},
        ),
    ],
)
profile(
    "telegram",
    "Telegram Bot",
    "Communication",
    "api.telegram.org",
    "https://core.telegram.org/bots/api#sendmessage",
    [
        a("test", "Verify bot", "GET", "/bot{bot_token}/getMe"),
        a(
            "send_message",
            "Send message",
            "POST",
            "/bot{bot_token}/sendMessage",
            "chat_id text",
            body={"chat_id": "chat_id", "text": "text"},
        ),
    ],
)
profile(
    "discord",
    "Discord",
    "Communication",
    "discord.com",
    "https://discord.com/developers/docs/resources/channel#create-message",
    [
        a("test", "Verify bot", "GET", "/api/v10/users/@me"),
        a(
            "send_message",
            "Send channel message",
            "POST",
            "/api/v10/channels/{channel_id}/messages",
            "channel_id text",
            body={"content": "text"},
        ),
    ],
    prefix="Bot",
)
profile(
    "notion",
    "Notion",
    "Collaboration",
    "api.notion.com",
    "https://developers.notion.com/reference/post-page",
    [
        a("test", "Verify integration", "GET", "/v1/users/me"),
        a(
            "create_page",
            "Create child page",
            "POST",
            "/v1/pages",
            "parent_page_id title",
            transform="notion",
        ),
    ],
    headers={"Notion-Version": "2025-09-03"},
)
profile(
    "airtable",
    "Airtable",
    "Databases",
    "api.airtable.com",
    "https://airtable.com/developers/web/api/create-records",
    [
        a(
            "list_records",
            "List records",
            "GET",
            "/v0/{base_id}/{table_id}",
            "base_id table_id",
        ),
        a(
            "create_record",
            "Create record",
            "POST",
            "/v0/{base_id}/{table_id}",
            "base_id table_id fields_json",
            transform="airtable",
        ),
    ],
)
profile(
    "asana",
    "Asana",
    "Project Management",
    "app.asana.com",
    "https://developers.asana.com/reference/createtask",
    [
        a("test", "Verify account", "GET", "/api/1.0/users/me"),
        a(
            "create_task",
            "Create task",
            "POST",
            "/api/1.0/tasks",
            "workspace_id title",
            transform="asana",
        ),
    ],
)
profile(
    "clickup",
    "ClickUp",
    "Project Management",
    "api.clickup.com",
    "https://developer.clickup.com/reference/createtask",
    [
        a("test", "Verify account", "GET", "/api/v2/user"),
        a(
            "create_task",
            "Create task",
            "POST",
            "/api/v2/list/{list_id}/task",
            "list_id title",
            body={"name": "title"},
        ),
    ],
    prefix="",
)
profile(
    "monday",
    "monday.com",
    "Project Management",
    "api.monday.com",
    "https://developer.monday.com/api-reference/reference/items",
    [
        a("test", "Verify account", "POST", "/v2", transform="monday_test"),
        a(
            "create_item",
            "Create board item",
            "POST",
            "/v2",
            "board_id title",
            transform="monday",
        ),
    ],
    prefix="",
    headers={"API-Version": "2025-10"},
)
profile(
    "todoist",
    "Todoist",
    "Project Management",
    "api.todoist.com",
    "https://developer.todoist.com/api/v1/",
    [
        a("list_tasks", "List tasks", "GET", "/api/v1/tasks"),
        a(
            "create_task",
            "Create task",
            "POST",
            "/api/v1/tasks",
            "title",
            body={"content": "title"},
        ),
    ],
)
profile(
    "linear",
    "Linear",
    "Project Management",
    "api.linear.app",
    "https://linear.app/developers/graphql",
    [
        a("test", "Verify account", "POST", "/graphql", transform="linear_test"),
        a(
            "create_issue",
            "Create issue",
            "POST",
            "/graphql",
            "team_id title",
            transform="linear",
        ),
    ],
    prefix="",
)
profile(
    "gitlab",
    "GitLab",
    "Developer Tools",
    "gitlab.com",
    "https://docs.gitlab.com/api/issues/",
    [
        a("test", "Verify account", "GET", "/api/v4/user"),
        a(
            "create_issue",
            "Create project issue",
            "POST",
            "/api/v4/projects/{project_id}/issues",
            "project_id title",
            body={"title": "title"},
        ),
    ],
)
profile(
    "bitbucket",
    "Bitbucket",
    "Developer Tools",
    "api.bitbucket.org",
    "https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/",
    [
        a("test", "Verify account", "GET", "/2.0/user"),
        a(
            "list_repositories",
            "List workspace repositories",
            "GET",
            "/2.0/repositories/{workspace_id}",
            "workspace_id",
        ),
    ],
)
profile(
    "hubspot",
    "HubSpot",
    "CRM",
    "api.hubapi.com",
    "https://developers.hubspot.com/docs/api-reference/crm-contacts-v3/basic/post-crm-v3-objects-contacts",
    [
        a("list_contacts", "List contacts", "GET", "/crm/v3/objects/contacts"),
        a(
            "create_contact",
            "Create contact",
            "POST",
            "/crm/v3/objects/contacts",
            "email name",
            transform="hubspot",
        ),
    ],
)
profile(
    "pipedrive",
    "Pipedrive",
    "CRM",
    "api.pipedrive.com",
    "https://developers.pipedrive.com/docs/api/v1/Persons",
    [
        a("list_people", "List people", "GET", "/api/v2/persons"),
        a(
            "create_person",
            "Create person",
            "POST",
            "/api/v2/persons",
            "name",
            body={"name": "name"},
        ),
    ],
)
profile(
    "stripe",
    "Stripe",
    "Payments",
    "api.stripe.com",
    "https://docs.stripe.com/api/customers/create",
    [
        a("test", "Verify Stripe account", "GET", "/v1/account"),
        a(
            "create_customer",
            "Create customer",
            "POST",
            "/v1/customers",
            "email name",
            transform="stripe",
        ),
    ],
)
profile(
    "razorpay",
    "Razorpay",
    "Payments",
    "api.razorpay.com",
    "https://razorpay.com/docs/api/customers/create/",
    [
        a("list_customers", "List customers", "GET", "/v1/customers"),
        a(
            "create_customer",
            "Create customer",
            "POST",
            "/v1/customers",
            "email name",
            body={"email": "email", "name": "name"},
        ),
    ],
    auth="basic",
)
profile(
    "sendgrid",
    "SendGrid",
    "Email",
    "api.sendgrid.com",
    "https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send",
    [
        a(
            "send_mail",
            "Send email",
            "POST",
            "/v3/mail/send",
            "from_email to subject text",
            transform="sendgrid",
        )
    ],
)
profile(
    "resend",
    "Resend",
    "Email",
    "api.resend.com",
    "https://resend.com/docs/api-reference/emails/send-email",
    [
        a(
            "send_mail",
            "Send email",
            "POST",
            "/emails",
            "from_email to subject text",
            transform="resend",
        )
    ],
)
profile(
    "brevo",
    "Brevo",
    "Email",
    "api.brevo.com",
    "https://developers.brevo.com/reference/sendtransacemail",
    [
        a("test", "Verify account", "GET", "/v3/account"),
        a(
            "send_mail",
            "Send transactional email",
            "POST",
            "/v3/smtp/email",
            "from_email to subject text",
            transform="brevo",
        ),
    ],
    prefix="",
    headers={"credential_header": "api-key"},
)
profile(
    "postmark",
    "Postmark",
    "Email",
    "api.postmarkapp.com",
    "https://postmarkapp.com/developer/api/email-api",
    [
        a(
            "send_mail",
            "Send transactional email",
            "POST",
            "/email",
            "from_email to subject text",
            transform="postmark",
        )
    ],
    headers={"credential_header": "X-Postmark-Server-Token"},
)
profile(
    "groq",
    "Groq",
    "AI Services",
    "api.groq.com",
    "https://console.groq.com/docs/api-reference",
    [
        a("list_models", "List models", "GET", "/openai/v1/models"),
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/openai/v1/chat/completions",
            "model prompt",
            transform="chat",
        ),
    ],
)
profile(
    "anthropic",
    "Anthropic",
    "AI Services",
    "api.anthropic.com",
    "https://docs.anthropic.com/en/api/messages",
    [
        a("list_models", "List models", "GET", "/v1/models"),
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/v1/messages",
            "model prompt",
            transform="anthropic",
        ),
    ],
    headers={"anthropic-version": "2023-06-01", "credential_header": "x-api-key"},
)
profile(
    "mistral",
    "Mistral AI",
    "AI Services",
    "api.mistral.ai",
    "https://docs.mistral.ai/api/",
    [
        a("list_models", "List models", "GET", "/v1/models"),
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/v1/chat/completions",
            "model prompt",
            transform="chat",
        ),
    ],
)
profile(
    "cohere",
    "Cohere",
    "AI Services",
    "api.cohere.com",
    "https://docs.cohere.com/reference/chat",
    [
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/v2/chat",
            "model prompt",
            transform="chat",
        )
    ],
)
profile(
    "openrouter",
    "OpenRouter",
    "AI Services",
    "openrouter.ai",
    "https://openrouter.ai/docs/api-reference/chat-completion",
    [
        a("list_models", "List models", "GET", "/api/v1/models"),
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/api/v1/chat/completions",
            "model prompt",
            transform="chat",
        ),
    ],
)
profile(
    "deepseek",
    "DeepSeek",
    "AI Services",
    "api.deepseek.com",
    "https://api-docs.deepseek.com/api/create-chat-completion",
    [
        a("list_models", "List models", "GET", "/models"),
        a(
            "generate_text",
            "Generate text",
            "POST",
            "/chat/completions",
            "model prompt",
            transform="chat",
        ),
    ],
)


def install(add, action):
    for p in PROFILES.values():
        entries = []
        for spec in p["actions"]:
            fields = {
                key: (
                    str,
                    Field(
                        min_length=1,
                        max_length=(
                            16000 if key in {"text", "prompt", "fields_json"} else 1000
                        ),
                    ),
                )
                for key in spec["fields"]
            }
            model = create_model(p["id"] + "_" + spec["id"], __base__=Strict, **fields)
            MODELS[p["id"], spec["id"]] = model
            # GraphQL/auth probes are POST but read-only; every actual creation is a write.
            mutates = spec["method"] not in {"GET", "HEAD"} and spec["id"] != "test"
            scopes = p["scopes"]
            if scopes:
                if p["id"] == "google_forms":
                    scopes = [
                        G
                        + (
                            {
                                "get_form": "forms.body.readonly",
                                "list_responses": "forms.responses.readonly",
                                "create_form": "forms.body",
                            }[spec["id"]]
                        )
                    ]
                elif p["id"] == "gmail":
                    scopes = [G + ("gmail.send" if mutates else "gmail.metadata")]
                elif p["id"] == "google_chat":
                    scopes = [
                        G
                        + (
                            "chat.messages.create"
                            if mutates
                            else "chat.spaces.readonly"
                        )
                    ]
                elif not mutates:
                    scopes = [scope + ".readonly" for scope in scopes]
            entries.append(
                (action(spec["id"], spec["label"], model, mutates, scopes), model)
            )
        add(
            p["id"],
            p["name"],
            p["category"],
            (["oauth2", "service_account", "bearer"] if p["scopes"] else [p["auth"]]),
            entries,
            p["documentation"],
            [
                "Create a provider credential with only the required scopes",
                "Save the credential in the encrypted connection vault",
                "Enable writes only for intended external actions",
                "Live verification requires your authorized provider account",
            ],
        )


def execute(conn, action_id, parsed, transport, headers, secrets, operation_key):
    from app.apps.power_apps.integrations.adapters import status_error, decode
    from app.apps.power_apps.integrations.transport import encode_request

    p = PROFILES[conn.connector_id]
    spec = next(x for x in p["actions"] if x["id"] == action_id)
    data = (
        MODELS[conn.connector_id, action_id]
        .model_validate(
            parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        )
        .model_dump()
    )
    path = spec["path"]
    for slot in re.findall(r"\{([a-z_]+)\}", path):
        value = (
            secrets.get("access_token", "")
            if slot == "bot_token"
            else data.get(slot, "")
        )
        if (
            not value
            or any(c in value for c in "\r\n")
            or (slot != "bot_token" and value in {".", ".."})
        ):
            raise IntegrationFailure(
                "schema", "Required provider resource identifier is missing or unsafe"
            )
        path = path.replace("{" + slot + "}", quote(value, safe=""))
    headers = {**headers, "Accept": "application/json", **p["headers"]}
    special = headers.pop("credential_header", None)
    if special:
        headers.pop("Authorization", None)
        headers[special] = secrets["access_token"]
    elif p["auth"] == "bearer":
        headers["Authorization"] = (p["prefix"] + " " if p["prefix"] else "") + secrets[
            "access_token"
        ]
    if conn.connector_id == "telegram":
        headers.pop("Authorization", None)
    body = {remote: data[local] for remote, local in spec["body"].items()}
    t = spec["transform"]
    if t in {"chat", "anthropic"}:
        body = {
            "model": data["model"],
            "messages": [{"role": "user", "content": data["prompt"]}],
            "max_tokens": 800,
        }
    elif t == "form":
        body = {"info": {"title": data["title"]}}
    elif t == "calendar":
        from datetime import datetime

        for field in ("starts_at", "ends_at"):
            if (
                datetime.fromisoformat(data[field].replace("Z", "+00:00")).tzinfo
                is None
            ):
                raise IntegrationFailure(
                    "schema", "Calendar timestamps need timezone offsets"
                )
        body = {
            "summary": data["summary"],
            "start": {"dateTime": data["starts_at"]},
            "end": {"dateTime": data["ends_at"]},
        }
    elif t == "gmail":
        import base64
        from email.message import EmailMessage

        message = EmailMessage()
        message["To"] = data["to"]
        message["Subject"] = data["subject"]
        message.set_content(data["text"])
        body = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    elif t == "contact":
        body = {
            "names": [{"givenName": data["name"]}],
            "emailAddresses": [{"value": data["email"]}],
        }
    elif t == "notion":
        body = {
            "parent": {"page_id": data["parent_page_id"]},
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"type": "text", "text": {"content": data["title"]}}],
                }
            },
        }
    elif t == "airtable":
        try:
            fields = json.loads(data["fields_json"])
        except ValueError:
            raise IntegrationFailure(
                "schema", "Record fields must be a JSON object"
            ) from None
        if not isinstance(fields, dict):
            raise IntegrationFailure("schema", "Record fields must be a JSON object")
        body = {"records": [{"fields": fields}]}
    elif t == "asana":
        body = {"data": {"name": data["title"], "workspace": data["workspace_id"]}}
    elif t == "hubspot":
        body = {"properties": {"email": data["email"], "firstname": data["name"]}}
    elif t == "monday_test":
        body = {"query": "query { me { id name } }"}
    elif t == "monday":
        body = {
            "query": "mutation($board: ID!, $name: String!) { create_item(board_id:$board, item_name:$name) { id } }",
            "variables": {"board": data["board_id"], "name": data["title"]},
        }
    elif t == "linear_test":
        body = {"query": "query { viewer { id name } }"}
    elif t == "linear":
        body = {
            "query": "mutation($input: IssueCreateInput!) { issueCreate(input:$input) { success issue { id identifier } } }",
            "variables": {"input": {"teamId": data["team_id"], "title": data["title"]}},
        }
    elif t == "sendgrid":
        body = {
            "personalizations": [{"to": [{"email": data["to"]}]}],
            "from": {"email": data["from_email"]},
            "subject": data["subject"],
            "content": [{"type": "text/plain", "value": data["text"]}],
        }
    elif t == "resend":
        body = {
            "from": data["from_email"],
            "to": [data["to"]],
            "subject": data["subject"],
            "text": data["text"],
        }
    elif t == "brevo":
        body = {
            "sender": {"email": data["from_email"]},
            "to": [{"email": data["to"]}],
            "subject": data["subject"],
            "textContent": data["text"],
        }
    elif t == "postmark":
        body = {
            "From": data["from_email"],
            "To": data["to"],
            "Subject": data["subject"],
            "TextBody": data["text"],
        }
    if spec["query"]:
        path += "?" + urlencode(spec["query"])
    content = None
    if spec["method"] not in {"GET", "HEAD"}:
        if t == "stripe":
            content = urlencode({"email": data["email"], "name": data["name"]}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            content = json.dumps(body, allow_nan=False).encode()
            headers["Content-Type"] = "application/json"
    if conn.connector_id in {"stripe", "resend"}:
        headers["Idempotency-Key"] = operation_key
    response = transport.request(
        spec["method"],
        "https://" + p["host"] + path,
        headers=headers,
        body=content,
        timeout=15,
    )
    mutates = spec["method"] not in {"GET", "HEAD"} and action_id != "test"
    status_error(response, mutates)
    result = decode(response, [*secrets.values(), *headers.values()])
    if isinstance(result, dict) and (
        result.get("ok") is False
        or result.get("errors")
        or result.get("success") is False
        or result.get("ErrorCode", 0) != 0
        or (
            isinstance(result.get("data"), dict)
            and any(
                isinstance(v, dict) and v.get("success") is False
                for v in result["data"].values()
            )
        )
    ):
        raise IntegrationFailure(
            "remote", "Provider rejected the action", uncertain=mutates
        )
    text = None
    if t in {"chat", "anthropic"} and isinstance(result, dict):
        if isinstance(result.get("choices"), list) and result["choices"]:
            text = result["choices"][0].get("message", {}).get("content")
        elif isinstance(result.get("content"), list):
            text = "".join(
                str(v.get("text", "")) for v in result["content"] if isinstance(v, dict)
            )
        elif isinstance(result.get("message"), dict):
            text = "".join(
                str(v.get("text", ""))
                for v in result["message"].get("content", [])
                if isinstance(v, dict)
            )
    return {
        "data": result,
        "text": text,
        "http_status": response.status,
        "delivery": "accepted" if mutates else "read",
    }
