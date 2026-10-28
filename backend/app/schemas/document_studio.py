from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomField(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    label: str = Field(min_length=1, max_length=100)
    type: Literal["text", "multiline", "date", "number"] = "text"
    required: bool = True
    default: str = Field(default="", max_length=2000)


class TemplateInput(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    document_type: str = Field(min_length=1, max_length=80)
    kind: Literal["letter", "certificate"] = "letter"
    orientation: Literal["portrait", "landscape"] = "portrait"
    recipient_scope: Literal["employee", "application", "both"] = "both"
    title: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=20000)
    custom_fields: list[CustomField] = Field(default_factory=list, max_length=20)
    letterhead_id: int | None = None
    is_active: bool = True
    version: int | None = None


class LetterheadInput(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    header_text: str = Field(default="", max_length=1000)
    footer_text: str = Field(default="", max_length=1000)
    accent_color: str = Field(default="#173b56", pattern=r"^#[0-9a-fA-F]{6}$")
    show_company_header: bool = True
    logo_asset_id: int | None = None
    background_asset_id: int | None = None
    signature_asset_id: int | None = None
    signatory_name: str = Field(default="", max_length=150)
    signatory_title: str = Field(default="Authorized Signatory", max_length=150)
    top_margin_mm: int = Field(default=44, ge=30, le=90)
    bottom_margin_mm: int = Field(default=25, ge=20, le=60)
    is_active: bool = True
    version: int | None = None


class GenerateInput(StrictModel):
    template_id: int
    template_version: int
    letterhead_id: int
    letterhead_version: int
    recipient_type: Literal["employee", "application"]
    recipient_id: int
    issue_date: date
    variables: dict[str, str] = Field(default_factory=dict, max_length=20)
    request_key: str = Field(min_length=8, max_length=100)


class RevokeInput(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)
