from datetime import datetime, timezone
from typing import Literal
from pydantic import Field, field_validator
from .schema import Strict, Definition


class FormSettings(Strict):
    public: bool = False
    captcha: Literal["builtin", "turnstile"] = "builtin"
    max_responses: int | None = Field(default=None, ge=1, le=100000)
    closes_at: datetime | None = None
    layout: Literal["stacked", "pages"] = "stacked"
    font: Literal["system", "serif", "monospace"] = "system"
    button_radius: int = Field(default=10, ge=0, le=24)

    @field_validator("closes_at")
    @classmethod
    def normalize_deadline(cls, value):
        if value is None:
            return None
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )


class FormDefinition(Definition):
    settings: FormSettings = Field(default_factory=FormSettings)
