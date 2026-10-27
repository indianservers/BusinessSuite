"""Atomic, bounded, shared PostgreSQL/SQLite throttles (no process-local counters)."""

import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException
from sqlalchemy import delete
from app.core.config import settings
from app.models.security_boundary import SecurityRateBucket, SecurityWorkLease


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
    for name, maximum, seconds in specifications:
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
    # Bounded cleanup; even a large backlog never creates unbounded request work.
    keys = (
        db.query(SecurityRateBucket.key, SecurityRateBucket.window)
        .filter(SecurityRateBucket.expires < now)
        .limit(100)
        .all()
    )
    for key, window in keys:
        db.execute(
            delete(SecurityRateBucket).where(
                SecurityRateBucket.key == key, SecurityRateBucket.window == window
            )
        )
    return 0


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
    from app.db.session import SessionLocal

    return getattr(request.app.state, "security_session_factory", SessionLocal)


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
        (f"user:{user.id}", settings.RATE_LIMIT_PER_MINUTE, 60),
        (f"company:{user.organization_id}", settings.RATE_LIMIT_PER_MINUTE * 20, 60),
    ]
    leases = []
    try:
        with factory(request)() as db:
            db.info["security_store_timeout"] = True
            retry = consume(db, specifications)
            if not retry and expensive(request.url.path):
                for name in (
                    f"work-user:{user.id}",
                    f"work-company:{user.organization_id}",
                ):
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
                    leases.append(lease)
            db.commit()
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
        with factory(request)() as db:
            db.info["security_store_timeout"] = True
            for key, slot, token in leases:
                db.execute(
                    delete(SecurityWorkLease).where(
                        SecurityWorkLease.key == key,
                        SecurityWorkLease.slot == slot,
                        SecurityWorkLease.token == token,
                    )
                )
            db.commit()
    except Exception:
        # Expiring ownership tokens prevent an old request from releasing a new lease.
        import logging

        logging.getLogger("businesssuite.security").warning(
            "security_event=work_lease_release_failed"
        )
