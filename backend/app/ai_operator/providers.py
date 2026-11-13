"""Fixed-host REST adapters. Never log credentials, prompts or raw error bodies."""
import base64
import hashlib
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from email.utils import parsedate_to_datetime
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from app.core.config import settings
from app.ai_operator.models import OperatorApiLog

_request_attempts = ContextVar("operator_provider_attempts", default=3)
_request_deadline = ContextVar("operator_provider_deadline", default=None)


@contextmanager
def planning_deadline(deadline):
    token = _request_deadline.set(deadline)
    try:
        yield
    finally:
        _request_deadline.reset(token)


@contextmanager
def retry_budget(attempts):
    """Durable workers own retries; synchronous callers retain bounded retries."""
    if attempts not in {1, 2, 3}:
        raise ValueError("Provider attempts must be between one and three")
    token = _request_attempts.set(attempts)
    try:
        yield
    finally:
        _request_attempts.reset(token)


def cipher():
    digest = hashlib.sha256(("ai-operator:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(key):
    if not key.strip() or len(key) > 4096:
        raise HTTPException(422, "Invalid API key")
    return cipher().encrypt(key.strip().encode()).decode()


def circuit_open(db, user, config, usage_scope):
    """Three consecutive transient failures pause this owner's same-scope adapter for 5 minutes."""
    rows = db.query(OperatorApiLog).filter_by(user_id=user.id, scope_key=usage_scope, provider=config.provider, model=config.model).filter(
        OperatorApiLog.created_at >= datetime.now(timezone.utc)-timedelta(minutes=5),
        OperatorApiLog.purpose != 'test',
        or_(OperatorApiLog.error_code.is_(None), OperatorApiLog.error_code != 'PROVIDER_CIRCUIT_OPEN')).order_by(OperatorApiLog.id.desc()).limit(3).all()
    return len(rows) == 3 and all(r.status != 'success' and (r.http_status == 429 or r.http_status and r.http_status >= 500 or r.error_code in {'PROVIDER_TIMEOUT','PROVIDER_CONNECTION_OR_KEY_ERROR'}) for r in rows)


def request_json(url, headers, body, seconds):
    """Retry proposal generation only, within one total wall-clock budget.

    No application tools or business writes run here. Invalid output and permanent
    authentication errors are deliberately not retried.
    """
    deadline = time.monotonic() + seconds
    attempts = _request_attempts.get()
    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.ReadTimeout('Provider planning deadline exceeded')
        try:
            with httpx.Client(timeout=httpx.Timeout(remaining, connect=min(10, remaining)), follow_redirects=False) as client:
                response = client.post(url, headers=headers, json=body)
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt == attempts - 1:
                return response
            delay = 0.5 * (2 ** attempt)
            retry_after = response.headers.get('retry-after')
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    try:
                        delay = max(delay, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError, OverflowError):
                        pass
            if not delay < deadline - time.monotonic():
                return response
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == attempts - 1:
                raise
            delay = 0.5 * (2 ** attempt)
            if delay >= deadline - time.monotonic():
                raise
        time.sleep(delay)


def generate_json(db, user, config, *, prompt, schema, run_id=None, purpose="plan", output_type=None,
                  usage_scope=None, module='PMS', suite_run_id=None):
    started = time.monotonic()
    log = OperatorApiLog(scope_key=usage_scope or config.scope_key, module=module, suite_run_id=suite_run_id, user_id=user.id, run_id=run_id,
        provider=config.provider, model=config.model, purpose=purpose, status="failed", duration_ms=0)
    manifest=None;request_attempted=False
    try:
        from app.ai_operator.prompt_registry import render
        instruction,manifest=render(purpose,schema)
        if suite_run_id and circuit_open(db, user, config, usage_scope or config.scope_key):
            log.error_code = 'PROVIDER_CIRCUIT_OPEN'
            raise HTTPException(503, log.error_code)
        if not config.data_sharing_allowed or (purpose != "test" and not config.enabled):
            raise HTTPException(409, "Provider is disabled or data sharing is blocked")
        key = cipher().decrypt(config.encrypted_key.encode()).decode()
        from app.ai_operator.structured_output import closed_schema,restore_omitted_defaults
        strict_schema=closed_schema(schema)
        if config.provider == "openai":
            url = "https://api.openai.com/v1/responses"
            headers = {"Authorization": f"Bearer {key}"}
            body = {"model": config.model, "instructions": instruction, "input": prompt,
                    "max_output_tokens": config.max_tokens, "store": False, "text": {"format": {"type": "json_object"}}}
            if strict_schema is not None:
                body['text']={'format':{'type':'json_schema','name':'business_action_proposal','strict':True,'schema':strict_schema}}
            if purpose == "assistant":
                # Propose exactly one bounded application tool. The application,
                # not the provider, validates permissions and requests approval.
                body.pop("text", None)
                body.update(tools=[{"type":"function","name":"propose_assistant_action",
                    "description":"Propose a validated PMS read or reviewable action; never execute it.",
                    "parameters":strict_schema if strict_schema is not None else schema,"strict":strict_schema is not None}],
                    tool_choice={"type":"function","name":"propose_assistant_action"},parallel_tool_calls=False)
        elif config.provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            body = {"model": config.model, "max_tokens": config.max_tokens, "system": instruction,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": [{"name": "submit_plan", "description": "Return the proposed plan", "input_schema": schema}],
                    "tool_choice": {"type": "tool", "name": "submit_plan"}}
            if strict_schema is not None:
                body['tools'][0].update(input_schema=strict_schema,strict=True)
        elif config.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
            headers = {"x-goog-api-key": key}
            body = {"systemInstruction": {"parts": [{"text": instruction}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    # The compound PMS schemas exceed Gemini's constrained-
                    # decoding branching limits. JSON mode plus the complete
                    # schema in the instruction remains compatible; the gateway
                    # and domain validator still reject invalid actions before
                    # any approval or execution.
                    "generationConfig": {"maxOutputTokens": config.max_tokens,
                                         "responseMimeType": "application/json"}}
        else:
            raise HTTPException(422, "Unsupported provider")
        from app.ai_agents.security import limits, company
        seconds = min(45, limits(db, company(user))["max_seconds"])
        deadline = _request_deadline.get()
        if deadline is not None:
            seconds = min(seconds, deadline-time.monotonic())
            if seconds <= 0:
                raise httpx.ReadTimeout('Provider planning deadline exceeded')
        from app.ai_operator.request_fingerprints import fingerprint
        manifest={**manifest,'output_contract':{'provider_strict':strict_schema is not None and config.provider in {'openai','claude'},
            'mode':'strict_schema' if strict_schema is not None and config.provider in {'openai','claude'} else 'validated_json',
            'domain_validation_required':True}}
        manifest={**manifest,'request_fingerprint':fingerprint(
            provider=config.provider,model=config.model,purpose=purpose,
            scope_key=log.scope_key,user_id=user.id,endpoint=url,body=body)}
        request_attempted=True
        response = request_json(url, headers, body, seconds)
        log.http_status = response.status_code
        log.provider_request_id = (response.headers.get("x-request-id") or response.headers.get("request-id") or "")[:180] or None
        response.raise_for_status()
        if len(response.content) > 262144:
            raise ValueError("Provider response exceeds the bounded output limit")
        data = response.json()
        if config.provider == "openai":
            usage = data.get("usage", {})
            log.input_tokens, log.output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            if data.get("status") != "completed":
                raise ValueError("Incomplete response")
            if purpose == "assistant":
                calls=[o for o in data.get("output",[]) if o.get("type")=="function_call" and o.get("name")=="propose_assistant_action"]
                if len(calls)!=1:
                    raise ValueError("Expected one bounded function call")
                text=calls[0]["arguments"]
            else:
                text = "".join(p.get("text", "") for o in data.get("output", []) for p in o.get("content", []) if p.get("type") == "output_text")
            result = json.loads(text)
        elif config.provider == "claude":
            usage = data.get("usage", {})
            log.input_tokens, log.output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            if data.get("stop_reason") != "tool_use":
                raise ValueError("Incomplete or refused response")
            result = next(p["input"] for p in data["content"] if p.get("type") == "tool_use" and p.get("name") == "submit_plan")
        else:
            usage = data.get("usageMetadata", {})
            log.input_tokens, log.output_tokens = usage.get("promptTokenCount"), usage.get("candidatesTokenCount")
            if log.output_tokens is not None:
                # Gemini bills generated thinking tokens as output too.
                log.output_tokens += usage.get("thoughtsTokenCount", 0) or 0
            if not log.provider_request_id:
                log.provider_request_id = str(data.get("responseId") or "")[:180] or None
            candidate = data["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Incomplete or refused response")
            result = json.loads("".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought")))
        if log.input_tokens is not None and log.output_tokens is not None and config.input_price is not None and config.output_price is not None:
            log.estimated_cost = (Decimal(log.input_tokens) * config.input_price + Decimal(log.output_tokens) * config.output_price) / Decimal(1000000)
        # Validate at the gateway too, so malformed plans count as failures in API analytics.
        from app.ai_operator.schemas import TaskPlan
        if strict_schema is not None and config.provider in {'openai','claude'}:
            result=restore_omitted_defaults(result,schema)
        (output_type or TaskPlan).model_validate(result)
        log.status = "success"
        return result
    except HTTPException:
        log.error_code = log.error_code or "PROVIDER_NOT_ENABLED"
        raise
    except httpx.HTTPStatusError as exc:
        log.error_code = f"PROVIDER_HTTP_{exc.response.status_code}"
        raise HTTPException(502, log.error_code) from None
    except httpx.TimeoutException:
        log.error_code = "PROVIDER_TIMEOUT"
        raise HTTPException(504, log.error_code) from None
    except (httpx.RequestError, InvalidToken):
        log.error_code = "PROVIDER_CONNECTION_OR_KEY_ERROR"
        raise HTTPException(502, log.error_code) from None
    except (ValueError, KeyError, IndexError, StopIteration, TypeError):
        log.error_code = "PROVIDER_INVALID_OUTPUT"
        raise HTTPException(502, log.error_code) from None
    finally:
        log.duration_ms = int((time.monotonic() - started) * 1000)
        db.add(log)
        db.flush()
        if manifest:
            from app.ai_operator.prompt_provenance import record
            record(db,user,log,manifest,request_attempted)
