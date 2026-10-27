"""Server-side adapters. Provider responses are validated, bounded and scrubbed."""

import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode
from app.apps.power_apps.integrations.contracts import (
    HTTPInput,
    ProviderInput,
    IntegrationFailure,
)
from app.apps.power_apps.integrations.registry import INPUTS, get_action
from app.apps.power_apps.integrations.transport import (
    HttpTransport,
    encode_request,
    scrub,
    SENSITIVE,
)
from app.apps.power_apps.authoring import path

HTTP_FACTORY = HttpTransport


def status_error(response, mutates=False):
    if 200 <= response.status < 300:
        return
    retry_after = 0
    try:
        retry_after = int(response.headers.get("retry-after", "0"))
    except ValueError:
        from email.utils import parsedate_to_datetime
        from app.apps.power_apps.runtime import now

        try:
            retry_after = max(
                0,
                int(
                    (
                        parsedate_to_datetime(response.headers["retry-after"]) - now()
                    ).total_seconds()
                ),
            )
        except (ValueError, KeyError, TypeError):
            pass
    category = (
        "authentication"
        if response.status in {401, 403}
        else "rate_limit" if response.status == 429 else "remote"
    )
    safe_retry = not mutates and response.status in {429, 500, 502, 503, 504}
    raise IntegrationFailure(
        category,
        f"Remote service returned HTTP {response.status}",
        retryable=safe_retry,
        retry_after=retry_after,
        uncertain=mutates and response.status >= 500,
        http_status=response.status,
    )


def decode(response, secrets):
    try:
        value = json.loads(response.body) if response.body else {}
    except (ValueError, UnicodeDecodeError):
        try:
            value = response.body.decode("utf-8")
        except UnicodeDecodeError:
            raise IntegrationFailure(
                "response", "Binary responses require a dedicated file adapter"
            ) from None
    return scrub(value, secrets)


def http_action(conn, data, transport, headers, secrets, operation_key, signed=False):
    data, custom, body = encode_request(data)
    if data.method not in {"GET", "HEAD"} and not conn.writes_enabled:
        raise IntegrationFailure("permission", "Connection writes are not enabled")
    parsed = urlsplit(data.url)
    if any(
        SENSITIVE.search(k)
        for k in [*(k for k, v in parse_qsl(parsed.query)), *data.query]
    ):
        raise IntegrationFailure(
            "credential", "Put credentials in the vault, not URL query parameters"
        )
    if data.method not in {"GET", "HEAD"} and data.max_pages > 1:
        raise IntegrationFailure(
            "pagination", "Mutating requests cannot use automatic pagination"
        )
    result = []
    started = time.monotonic()
    last = None
    for index in range(data.max_pages):
        query = [
            *parse_qsl(parsed.query, keep_blank_values=True),
            *[(k, str(v)) for k, v in data.query.items()],
        ]
        if data.page_parameter:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,49}", data.page_parameter):
                raise IntegrationFailure(
                    "pagination", "Use a simple page parameter name"
                )
            query.append((data.page_parameter, str(data.page + index)))
        elif data.max_pages > 1:
            raise IntegrationFailure(
                "pagination", "Pagination requires a named page parameter"
            )
        url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
        )
        outgoing = {**custom, **headers, "Idempotency-Key": operation_key}
        if signed:
            from app.apps.power_apps.runtime import now

            stamp = str(int(now().timestamp()))
            signing_key = secrets.get("signing_secret")
            if signing_key:
                outgoing.update(
                    {
                        "X-Power-Timestamp": stamp,
                        "X-Power-Nonce": operation_key,
                        "X-Power-Signature": hmac.new(
                            signing_key.encode(),
                            stamp.encode()
                            + b"."
                            + operation_key.encode()
                            + b"."
                            + (body or b""),
                            hashlib.sha256,
                        ).hexdigest(),
                    }
                )
        remaining = data.timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise IntegrationFailure(
                "timeout",
                "HTTP pagination exceeded its bounded deadline",
                retryable=data.method in {"GET", "HEAD"},
                uncertain=data.method not in {"GET", "HEAD"},
            )
        last = transport.request(
            data.method,
            url,
            outgoing,
            body,
            timeout=remaining,
            redirects=data.redirects,
        )
        if not data.route_status:
            status_error(last, data.method not in {"GET", "HEAD"})
        value = decode(last, [*secrets.values(), *headers.values()])
        if data.response_path:
            value = path(value, data.response_path)
        result.append(value)
        if value in ([], {}, "") or data.max_pages == 1:
            break
    return {
        "status_code": last.status,
        "headers": scrub(last.headers, [*secrets.values(), *headers.values()]),
        "body": result[0] if len(result) == 1 else result,
        "pages": len(result),
        "pagination_capped": len(result) == data.max_pages and data.max_pages > 1,
    }


def provider_action(conn, action, data, transport, headers, secrets, operation_key):
    data = ProviderInput.model_validate(data)
    mutates = get_action(conn.connector_id, action).mutates
    method = "GET"
    body = None
    if conn.connector_id == "github":
        headers = {
            **headers,
            "Accept": "application/vnd.github+json",
            "User-Agent": "BusinessSuite-PowerApps",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if action == "test":
            url = "https://api.github.com/user"
        else:
            if not re.fullmatch(
                r"[A-Za-z0-9_.-]{1,100}", data.owner
            ) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", data.repository):
                raise IntegrationFailure(
                    "schema", "Choose a valid repository owner and name"
                )
            url = f'https://api.github.com/repos/{quote(data.owner,safe="")}/{quote(data.repository,safe="")}/issues'
            if action == "create_issue":
                if not data.title:
                    raise IntegrationFailure("schema", "Issue title is required")
                method = "POST"
                body = {"title": data.title, "body": data.text}
            elif action == "list_issues":
                url += "?" + urlencode(
                    {"per_page": data.limit, "page": int(data.page_token or "1")}
                )
    elif conn.connector_id == "google_sheets":
        spreadsheet = data.spreadsheet_id or conn.config.get("spreadsheet_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", spreadsheet):
            raise IntegrationFailure("schema", "Spreadsheet ID is required")
        url = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(
            spreadsheet, safe=""
        )
        if action == "test":
            url += "?fields=spreadsheetId,properties.title"
        else:
            url += "/values/" + quote(data.range, safe="")
            if action == "append_rows":
                if not data.values:
                    raise IntegrationFailure("schema", "Rows are required")
                url += ":append?valueInputOption=RAW&includeValuesInResponse=false"
                method = "POST"
                body = {"values": data.values, "majorDimension": "ROWS"}
    elif conn.connector_id == "google_drive":
        url = "https://www.googleapis.com/drive/v3/files"
        if action in {"test", "list_files"}:
            url += "?" + urlencode(
                {
                    "pageSize": data.limit,
                    "fields": "files(id,name,mimeType),nextPageToken",
                    **({"pageToken": data.page_token} if data.page_token else {}),
                }
            )
        elif action == "file_metadata":
            if not re.fullmatch(r"[A-Za-z0-9_-]{5,200}", data.file_id):
                raise IntegrationFailure("schema", "File ID is required")
            url += (
                "/"
                + quote(data.file_id, safe="")
                + "?fields=id,name,mimeType,size,modifiedTime"
            )
        elif action == "create_file":
            if not data.name:
                raise IntegrationFailure("schema", "File name is required")
            method = "POST"
            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType"
            import secrets as rand

            boundary = "power_" + rand.token_hex(16)
            metadata = {"name": data.name, "mimeType": "text/plain"}
            if data.parent_id:
                if not re.fullmatch(r"[A-Za-z0-9_-]{5,200}", data.parent_id):
                    raise IntegrationFailure("schema", "Invalid parent folder")
                metadata["parents"] = [data.parent_id]
            body = (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                + json.dumps(metadata)
                + f"\r\n--{boundary}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n"
                + data.content
                + f"\r\n--{boundary}--\r\n"
            ).encode()
            headers = {
                **headers,
                "Content-Type": "multipart/related; boundary=" + boundary,
            }
    elif conn.connector_id == "outlook":
        url = "https://graph.microsoft.com/v1.0/me"
        if action == "test":
            url += "?$select=id,displayName"
        elif action == "list_messages":
            url += "/messages?" + urlencode(
                {
                    "$top": data.limit,
                    "$select": "id,subject,from,receivedDateTime",
                    "$skip": int(data.page_token or "0"),
                }
            )
        elif action == "send_mail":
            if (
                not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data.recipient)
                or "\r" in data.recipient
                or "\n" in data.recipient
                or not data.subject
            ):
                raise IntegrationFailure(
                    "schema", "A recipient and subject are required"
                )
            method = "POST"
            url += "/sendMail"
            body = {
                "message": {
                    "subject": data.subject,
                    "body": {"contentType": "Text", "content": data.text},
                    "toRecipients": [{"emailAddress": {"address": data.recipient}}],
                },
                "saveToSentItems": True,
            }
    else:
        raise IntegrationFailure("action", "Unsupported provider adapter")
    if isinstance(body, dict):
        body = json.dumps(body, allow_nan=False).encode()
        headers = {**headers, "Content-Type": "application/json"}
    response = transport.request(
        method, url, {**headers, "client-request-id": operation_key}, body, timeout=15
    )
    status_error(response, mutates)
    result = decode(response, [*secrets.values(), *headers.values()])
    if conn.connector_id == "outlook" and action == "send_mail":
        return {
            "accepted": True,
            "http_status": response.status,
            "delivery_confirmed": False,
        }
    if not isinstance(result, (dict, list)):
        raise IntegrationFailure(
            "response_schema",
            "Provider returned an invalid structured response",
            uncertain=mutates,
        )
    if action in {"create_issue", "create_file"} and not result.get("id"):
        raise IntegrationFailure(
            "response_schema",
            "Provider did not return a created-resource ID",
            uncertain=True,
        )
    if (
        conn.connector_id == "google_sheets"
        and action == "append_rows"
        and not isinstance(result.get("updates"), dict)
    ):
        raise IntegrationFailure(
            "response_schema",
            "Provider did not return an append result",
            uncertain=True,
        )
    return result


def smtp_action(action, data):
    from app.core.config import settings
    from app.core.email import send_smtp_message
    from email.message import EmailMessage

    data = ProviderInput.model_validate(data)
    if not all(
        [
            settings.MAIL_SERVER,
            settings.MAIL_USERNAME,
            settings.MAIL_PASSWORD,
            settings.MAIL_FROM,
        ]
    ) or not (settings.MAIL_SSL_TLS or settings.MAIL_STARTTLS):
        raise IntegrationFailure(
            "configuration", "Authorized SMTP infrastructure is not configured with TLS"
        )
    try:
        if action == "test":
            import smtplib, ssl

            cls = smtplib.SMTP_SSL if settings.MAIL_SSL_TLS else smtplib.SMTP
            with cls(
                settings.MAIL_SERVER,
                settings.MAIL_PORT,
                timeout=10,
                **(
                    {"context": ssl.create_default_context()}
                    if settings.MAIL_SSL_TLS
                    else {}
                ),
            ) as client:
                if not settings.MAIL_SSL_TLS:
                    client.ehlo()
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                client.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                code, _ = client.noop()
                if code != 250:
                    raise ValueError()
            return {"authenticated": True, "message_sent": False}
        if (
            not data.recipient
            or not data.subject
            or "\n" in data.subject
            or "\r" in data.subject
        ):
            raise IntegrationFailure(
                "schema", "A safe recipient and subject are required"
            )
        from email_validator import validate_email

        recipient = validate_email(
            data.recipient, check_deliverability=False
        ).normalized
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = data.subject
        message.set_content(data.text)
        send_smtp_message(message, recipient)
        return {"accepted": True, "delivery_confirmed": False}
    except IntegrationFailure:
        raise
    except Exception:
        raise IntegrationFailure(
            "smtp",
            "SMTP operation failed; inspect server configuration",
            uncertain=action == "send",
        ) from None
