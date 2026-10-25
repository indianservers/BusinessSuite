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
    columns: Literal[1, 2, 3] = 1
    intro_enabled: bool = False
    intro_badge: str = Field(default="Build your future", max_length=80)
    intro_title: str = Field(default="Your next chapter starts here.", max_length=200)
    intro_text: str = Field(default="Share your details and take the first step. We look forward to getting to know you.", max_length=1000)
    surface: Literal["minimal", "soft", "gradient"] = "soft"

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
