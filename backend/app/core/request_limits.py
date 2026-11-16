"""Atomic, bounded, shared PostgreSQL/SQLite throttles (no process-local counters)."""

import hashlib
import hmac
import secrets
import time
import logging
from threading import Lock
from fastapi import HTTPException
from sqlalchemy import delete, tuple_
from app.core.config import settings
from app.models.security_boundary import SecurityRateBucket, SecurityWorkLease

logger = logging.getLogger('businesssuite.security')
_cleanup_lock = Lock()
_next_cleanup_at = 0.0
_retryable_states = {'55P03', '40P01', '40001'}


def security_transaction(request, operation, *, cleanup=True):
    """Retry only explicitly aborted store transactions, never business handlers."""
    started = time.monotonic()
    for attempt in range(1, 4):
        try:
            with factory(request)() as db:
                db.info['security_store_timeout'] = True
                result = operation(db)
                db.commit()
            break
        except Exception as error:
            original = getattr(error, 'orig', None)
            state = getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None)
            retry = state in _retryable_states and attempt < 3 and time.monotonic() - started < 4
            # Never log exception strings: DB exceptions can contain SQL parameters.
            logger.warning('security_event=security_store_%s phase=reserve error_type=%s sqlstate=%s attempt=%s request_id=%s',
                'retry' if retry else 'failure', type(error).__name__, state or 'unknown', attempt,
                getattr(request.state, 'request_id', 'unknown') if hasattr(request, 'state') else 'unknown')
            if not retry:
                raise
            time.sleep(0.025 * attempt + secrets.randbelow(26) / 1000)
            if time.monotonic() - started >= 4:
                raise
    if cleanup:
        _cleanup_after_commit(request)
    return result


def _cleanup_after_commit(request):
    # Maintenance scheduling is local; all enforcement decisions remain shared.
    global _next_cleanup_at
    now = time.monotonic()
    with _cleanup_lock:
        if now < _next_cleanup_at:
            return
        _next_cleanup_at = now + 1
    try:
        with factory(request)() as db:
            db.info['security_store_timeout'] = True
            cleanup_expired(db)
            db.commit()
    except Exception as error:
        logger.warning('security_event=security_cleanup_failed error_type=%s', type(error).__name__)


def digest(value):
    return hmac.new(
        settings.SECRET_KEY.encode(), str(value).encode(), hashlib.sha256
    ).hexdigest()


def insert_for(db, model):
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif db.get_bind().dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("Shared security counters require PostgreSQL")
    return insert(model)


def consume(db, specifications, now=None):
    now = int(time.time()) if now is None else int(now)
    # Overlapping budgets must take row locks in the same order on every worker.
    for name, maximum, seconds in sorted(specifications, key=lambda item: (digest(item[0]), now // item[2])):
        window = now // seconds
        table = SecurityRateBucket
        statement = insert_for(db, table).values(
            key=digest(name), window=window, count=1, expires=(window + 2) * seconds
        )
        statement = statement.on_conflict_do_update(
            index_elements=[table.key, table.window],
            set_={"count": table.count + 1},
            where=table.count < maximum,
        ).returning(table.count)
        if db.execute(statement).scalar_one_or_none() is None:
            return max(1, seconds - now % seconds)
    return 0


def cleanup_expired(db, now=None):
    """Opportunistic maintenance must not hold active reservation row locks."""
    now = int(time.time()) if now is None else int(now)
    keys = (
        db.query(SecurityRateBucket.key, SecurityRateBucket.window)
        .filter(SecurityRateBucket.expires < now)
        .order_by(SecurityRateBucket.key, SecurityRateBucket.window)
        .limit(100)
        .with_for_update(skip_locked=True)
        .all()
    )
    if keys:
        db.execute(
            delete(SecurityRateBucket).where(
                tuple_(SecurityRateBucket.key, SecurityRateBucket.window).in_(keys)
            )
        )


def acquire(db, name, maximum, seconds, now=None):
    now = int(time.time()) if now is None else int(now)
    key, token = digest(name), secrets.token_hex(24)
    for slot in range(maximum):
        table = SecurityWorkLease
        statement = insert_for(db, table).values(
            key=key, slot=slot, token=token, expires=now + seconds
        )
        statement = statement.on_conflict_do_update(
            index_elements=[table.key, table.slot],
            set_={"token": token, "expires": now + seconds},
            where=table.expires <= now,
        ).returning(table.token)
        if db.execute(statement).scalar_one_or_none() == token:
            return key, slot, token
    return None


def enabled(request):
    return settings.SECURITY_RATE_LIMIT_ENABLED and (
        settings.ENVIRONMENT != "test"
        or getattr(request.app.state, "security_enforce_tests", False)
    )


def factory(request):
    from app.db.session import ControlSessionLocal

    return getattr(request.app.state, "security_session_factory", ControlSessionLocal)


def expensive(path):
    return any(
        part in path.lower()
        for part in (
            "/export",
            "/report",
            "/search",
            "/ai/",
            "/ai-",
            "/bulk",
            "/import",
            "/upload",
            "/recompute",
            "/generate",
            "/analytics",
        )
    )


def enforce_actor(request, user):
    if not enabled(request):
        return lambda: None
    specifications = [
        (f"user:{user.organization_id}:{user.id}", settings.RATE_LIMIT_PER_MINUTE, 60),
        (f"company:{user.organization_id}", settings.RATE_LIMIT_PER_MINUTE * 20, 60),
    ]
    leases = []
    try:
        def reserve(db):
            attempt_leases = []
            retry = consume(db, specifications)
            if not retry and expensive(request.url.path):
                for name in sorted((
                    f"work-user:{user.organization_id}:{user.id}",
                    f"work-company:{user.organization_id}",
                ), key=digest):
                    lease = acquire(
                        db,
                        name,
                        settings.SECURITY_EXPENSIVE_CONCURRENCY,
                        max(
                            settings.SECURITY_WORK_LEASE_SECONDS,
                            settings.SECURITY_REQUEST_TIMEOUT_SECONDS * 2,
                        ),
                    )
                    if lease is None:
                        retry = 5
                        break
                    attempt_leases.append(lease)
            return retry, attempt_leases
        retry, leases = security_transaction(request, reserve)
        if retry:
            import logging

            logging.getLogger("businesssuite.security").warning(
                "security_event=actor_throttled actor=%s company=%s retry_seconds=%s",
                user.id,
                user.organization_id,
                retry,
            )
            release(request, leases)
            raise HTTPException(
                429,
                "Request limit reached. Try again shortly.",
                headers={"Retry-After": str(retry)},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            503,
            "Security enforcement is temporarily unavailable",
            headers={"Retry-After": "5"},
        ) from None
    return lambda: release(request, leases)


def release(request, leases):
    if not leases:
        return
    try:
        def clear(db):
            for key, slot, token in sorted(leases):
                db.execute(
                    delete(SecurityWorkLease).where(
                        SecurityWorkLease.key == key,
                        SecurityWorkLease.slot == slot,
                        SecurityWorkLease.token == token,
                    )
                )
        security_transaction(request, clear, cleanup=False)
    except Exception:
        # Expiring ownership tokens prevent an old request from releasing a new lease.
        import logging

        logging.getLogger("businesssuite.security").warning(
            "security_event=work_lease_release_failed"
        )
