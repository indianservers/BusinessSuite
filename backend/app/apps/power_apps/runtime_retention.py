"""Metadata-preserving payload retention. Called only by an authorized system worker."""

from datetime import timedelta
from sqlalchemy import func
from app.apps.power_apps.runtime import now, utc, scope_values
from app.apps.power_apps.models import PowerVersion, PowerExecution
from app.apps.power_apps.runtime_models import (
    AutomationRun as Run,
    AutomationStep as Step,
    AutomationEvent as Event,
    AutomationReplay as Replay,
)


def purge_payloads(db, limit=50):
    runs = (
        db.query(Run)
        .join(PowerVersion, PowerVersion.id == Run.version_id)
        .filter(
            Run.finished_at.is_not(None),
            Run.payloads_purged_at.is_(None),
            func.extract("epoch", Run.finished_at)
            + func.coalesce(
                PowerVersion.snapshot["definition"]["settings"][
                    "retention_days"
                ].as_integer(),
                30,
            )
            * 86400
            < now().timestamp(),
        )
        .order_by(Run.finished_at)
        .limit(limit)
        .all()
    )
    count = 0
    for run in runs:
        if run.plan.get("payloads_purged"):
            continue
        version = db.get(PowerVersion, run.version_id)
        days = (
            version.snapshot["definition"].get("settings", {}).get("retention_days", 30)
        )
        if utc(run.finished_at) + timedelta(days=days) > now():
            continue
        db.query(PowerExecution).filter_by(id=run.id).with_for_update().one()
        run.input_payload = {}
        run.variables = {}
        run.plan = {"payloads_purged": True}
        run.payloads_purged_at = now()
        db.query(Step).filter_by(
            run_id=run.id, organization_id=run.organization_id
        ).update(
            {"input_payload": None, "output": None, "local_context": {}},
            synchronize_session="fetch",
        )
        for entry in db.query(Event).filter_by(
            run_id=run.id, organization_id=run.organization_id
        ):
            if entry.kind == "structured_log":
                entry.details = {"payloads_purged": True}
        db.add(
            Event(
                **scope_values(run),
                run_id=run.id,
                resource_id=db.get(PowerExecution, run.id).resource_id,
                kind="payloads_purged",
                details={"retention_days": days}
            )
        )
        count += 1
        if count >= limit:
            break
    # Expired webhook nonces cannot be replayed because HMAC timestamps expire at five minutes.
    db.query(Replay).filter(Replay.created_at < now() - timedelta(days=1)).delete(
        synchronize_session=False
    )
    db.commit()
    return count
