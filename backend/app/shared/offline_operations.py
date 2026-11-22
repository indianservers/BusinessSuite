"""Durable receipts for explicitly queued browser writes."""
from hashlib import sha256
from json import dumps
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Table, Column, Integer, String, JSON, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.db.base_class import Base

receipts = Table(
    "offline_operation_receipts", Base.metadata,
    Column("actor_id", Integer, primary_key=True),
    Column("operation_id", String(36), primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    Column("result", JSON),
)


def perform_offline_operation(db, actor, operation_id, action, payload, apply, check_replay, after_commit=None):
    """Reserve the operation and commit its response in the mutation transaction."""
    branch = db.info.get("branch_context")
    pack = db.info.get("business_pack_scope")
    fingerprint = sha256(dumps(jsonable_encoder([
        action, getattr(branch, "company_id", None), getattr(branch, "branch_id", None),
        getattr(pack, "context_id", None), payload,
    ]), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    key = receipts.c.actor_id == actor.id, receipts.c.operation_id == str(operation_id)
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    reserved = db.execute(insert(receipts).values(
        actor_id=actor.id, operation_id=str(operation_id), fingerprint=fingerprint,
    ).on_conflict_do_nothing(index_elements=["actor_id", "operation_id"]))
    if not reserved.rowcount:
        previous = db.execute(select(receipts).where(*key)).mappings().one()
        if previous["fingerprint"] != fingerprint or previous["result"] is None:
            raise HTTPException(409, "This offline operation belongs to a different request.")
        check_replay(previous["result"])
        return previous["result"]
    result = jsonable_encoder(apply())
    db.execute(update(receipts).where(*key).values(result=result))
    db.commit()
    if after_commit is not None:
        after_commit(result)
    return result

