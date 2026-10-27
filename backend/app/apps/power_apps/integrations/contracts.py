"""Strict public contracts; secrets are write-only and excluded from representations."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ActionSpec(Strict):
    id: str
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    mutates: bool = False
    scopes: list[str] = Field(default_factory=list)
    permission: str = "power_apps_execute"
    idempotency: Literal["read", "provider", "reconcile"] = "read"
    timeout_seconds: int = 15
    retryable_statuses: list[int] = Field(default_factory=lambda: [429, 502, 503, 504])


class Manifest(Strict):
    id: str
    name: str
    description: str
    version: int = 1
    category: str
    availability: Literal[
        "Available", "Requires Configuration", "In Development", "Unsupported"
    ] = "Requires Configuration"
    authentication: list[str]
    actions: list[ActionSpec] = Field(default_factory=list)
    triggers: list[dict] = Field(default_factory=list)
    rate_per_minute: int = 30
    max_concurrent: int = 2
    timeout_seconds: int = 15
    setup: list[str] = Field(default_factory=list)
    documentation_url: str
    live_verification: str = "Pending authorized credentials"


class ConnectionCreate(Strict):
    connector_id: str = Field(max_length=80)
    name: str = Field(min_length=1, max_length=180)
    auth_type: Literal[
        "none",
        "api_key",
        "bearer",
        "basic",
        "oauth2",
        "service_account",
        "database",
        "signing",
        "gateway",
        "platform_smtp",
    ]
    secrets: dict[str, SecretStr] = Field(
        default_factory=dict, max_length=20, repr=False
    )
    config: dict[str, Any] = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list, max_length=20)
    sharing: list[int] = Field(default_factory=list, max_length=100)
    writes_enabled: bool = False


class ConnectionUpdate(Strict):
    expected_revision: int = Field(ge=1)
    enabled: bool
    sharing: list[int] = Field(default_factory=list, max_length=100)
    writes_enabled: bool = False


class SecretRotate(Strict):
    expected_version: int = Field(ge=1)
    secrets: dict[str, SecretStr] = Field(min_length=1, max_length=20, repr=False)


class Probe(Strict):
    connection_id: int = Field(ge=1)
    action_id: str = Field(max_length=80)
    input: dict[str, Any] = Field(default_factory=dict)
    confirm_side_effect: bool = False
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")


class OAuthStart(Strict):
    scopes: list[str] = Field(default_factory=list, max_length=20)


class HTTPInput(Strict):
    url: str = Field(max_length=4096)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict, max_length=30)
    query: dict[str, str | int | bool] = Field(default_factory=dict, max_length=30)
    body: Any = None
    form: dict[str, str] | None = None
    files: list[dict[str, str]] = Field(default_factory=list, max_length=3)
    timeout_seconds: int = Field(default=10, ge=1, le=15)
    redirects: int = Field(default=0, ge=0, le=2)
    page_parameter: str | None = Field(default=None, max_length=50)
    page: int = Field(default=1, ge=1, le=10000)
    max_pages: int = Field(default=1, ge=1, le=5)
    route_status: bool = False
    response_path: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def one_body(self):
        if sum([self.body is not None, self.form is not None, bool(self.files)]) > 1:
            raise ValueError("Choose one body encoding")
        return self


class DBInput(Strict):
    schema_name: str = Field(default="public", max_length=63)
    table: str = Field(default="", max_length=63)
    columns: list[str] = Field(default_factory=list, max_length=50)
    where: dict[str, Any] = Field(default_factory=dict, max_length=20)
    values: dict[str, Any] = Field(default_factory=dict, max_length=50)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=10000)


class AIInput(Strict):
    input: str = Field(min_length=1, max_length=16000)
    instruction: str = Field(default="", max_length=2000)
    categories: list[str] = Field(default_factory=list, max_length=30)
    target_language: str = Field(default="English", max_length=80)
    document_b: str = Field(default="", max_length=16000)
    output_schema: dict | None = None
    token_budget: int = Field(default=800, ge=32, le=2000)


class ProviderInput(Strict):
    owner: str = Field(default="", max_length=100)
    repository: str = Field(default="", max_length=100)
    title: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=16000)
    spreadsheet_id: str = Field(default="", max_length=200)
    range: str = Field(default="Sheet1!A1:Z100", max_length=200)
    values: list[list[Any]] = Field(default_factory=list, max_length=200)
    file_id: str = Field(default="", max_length=200)
    name: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=32000)
    parent_id: str = Field(default="", max_length=200)
    recipient: str = Field(default="", max_length=320)
    subject: str = Field(default="", max_length=200)
    page_token: str = Field(default="", max_length=2000)
    limit: int = Field(default=25, ge=1, le=100)


class IntegrationFailure(Exception):
    def __init__(
        self,
        category,
        message,
        *,
        retryable=False,
        retry_after=0,
        uncertain=False,
        http_status=None
    ):
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.retry_after = min(max(int(retry_after), 0), 86400)
        self.uncertain = uncertain
        self.http_status = http_status
