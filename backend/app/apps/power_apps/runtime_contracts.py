"""Bounded runtime contracts. No arbitrary code, URLs or connector dispatch."""

from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RuntimePolicy(Strict):
    concurrency: int = Field(default=4, ge=1, le=20)
    overflow: Literal["queue", "reject", "ignore"] = "queue"
    max_queued: int = Field(default=1000, ge=1, le=1000)
    max_duration_seconds: int = Field(default=86400, ge=1, le=604800)
    identity: Literal["initiator", "owner", "service"] = "initiator"
    delegated_owner: bool = False
    service_user_id: int | None = Field(default=None, ge=1)
    input_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def authority(self):
        if self.identity == "owner" and not self.delegated_owner:
            raise ValueError("Owner execution requires explicit delegated authority")
        if self.identity == "service" and not self.service_user_id:
            raise ValueError("A managed service identity is required")
        if self.identity != "service" and self.service_user_id is not None:
            raise ValueError("Service identity is only valid in service mode")
        return self


class LifecycleRequest(Strict):
    expected_version: int = Field(ge=1)
    policy: RuntimePolicy = Field(default_factory=RuntimePolicy)


class RunRequest(Strict):
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(
        min_length=8, max_length=180, pattern=r"^[A-Za-z0-9_.:@/-]+$"
    )
    confirm: bool = False


class TriggerRequest(Strict):
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(Strict):
    event_key: str = Field(
        min_length=8, max_length=120, pattern=r"^[A-Za-z0-9_.:@/-]+$"
    )


class ScheduleConfig(Strict):
    mode: Literal["once", "minutes", "hourly", "daily", "weekly", "monthly", "cron"]
    timezone: str = "UTC"
    at: datetime | None = None
    every_minutes: int = Field(default=1, ge=1, le=525600)
    hour: int = Field(default=0, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    day: int = Field(default=1, ge=1, le=31)
    cron: str = Field(default="", max_length=120)
    start_at: datetime | None = None
    end_at: datetime | None = None
