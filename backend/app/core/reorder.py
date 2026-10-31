"""Shared strict ordering contract. Domain endpoints still own authorization."""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(min_length=1, max_length=1000)
    previous_order: list[int] = Field(min_length=1, max_length=1000)


def apply_order(rows, data: OrderInput, field: str):
    current = [row.id for row in rows]
    if len(set(data.ids)) != len(data.ids) or set(data.ids) != set(current):
        raise HTTPException(422, "Ordering must contain every item in this scope exactly once.")
    if current != data.previous_order:
        raise HTTPException(409, "This list changed. Refresh before reordering.")
    by_id = {row.id: row for row in rows}
    for index, identity in enumerate(data.ids):
        setattr(by_id[identity], field, index)
    return [by_id[identity] for identity in data.ids]
