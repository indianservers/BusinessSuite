from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AIProviderSettingPayload(BaseModel):
    provider_name: str
    model_name: str
    enabled: bool = False
    masked_api_key_reference: str | None = None
    data_sharing_allowed: bool = False
    max_tokens: int = Field(default=1200, ge=1, le=32000)
    temperature: float = Field(default=0.2, ge=0, le=2)


class AIPromptTemplatePayload(BaseModel):
    name: str
    use_case: str
    module_name: str
    system_prompt: str
    user_prompt_template: str
    output_schema_json: dict[str, Any] | None = None
    active: bool = True


class AIUseCaseRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_type: str | None = None
    record_id: int | None = None
    module_name: str | None = None
    prompt: str | None = None
    tone: str | None = None
    data: dict[str, Any] | None = None


class AIAgentActionPreviewRequest(BaseModel):
    action_type: str
    module_name: str
    record_type: str | None = None
    record_id: int | None = None
    input_json: dict[str, Any] | None = None


class AIAgentActionConfirmRequest(BaseModel):
    action_id: int
    confirmation_note: str | None = None


class AIUserFeedbackPayload(BaseModel):
    prompt_run_id: int | None = None
    recommendation_id: int | None = None
    rating: str
    comments: str | None = None

