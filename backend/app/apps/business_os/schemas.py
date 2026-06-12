from pydantic import BaseModel, Field


class BOSModuleState(BaseModel):
    module_key: str
    display_name: str
    enabled: bool
    is_financial_backbone: bool = False
    optional: bool = True
    home_path: str | None = None
    reason: str | None = None


class BOSModulesResponse(BaseModel):
    company_id: int
    modules: list[BOSModuleState]
    enabled_modules: list[str]
    supported_combinations: list[dict[str, object]]


class BOSModulesUpdate(BaseModel):
    enabled_modules: list[str] = Field(default_factory=list)


class BOSDependencyResponse(BaseModel):
    module_key: str
    depends_on_module_key: str
    dependency_type: str
    reason: str | None = None
    active: bool


class BOSIntegrationRuleResponse(BaseModel):
    id: int
    rule_key: str
    source_module: str
    target_module: str
    event_name: str
    action_name: str
    enabled: bool
    source_enabled: bool
    target_enabled: bool
    effective: bool


class BOSEntityLinkResponse(BaseModel):
    id: int
    source_module: str
    source_entity: str
    source_entity_id: str
    target_module: str
    target_entity: str
    target_entity_id: str
    link_type: str
    active: bool
    metadata_json: dict


class BOSLifecycleEventResponse(BaseModel):
    id: int
    module_key: str
    entity_type: str
    entity_id: str
    event_name: str
    status: str
    message: str | None = None
    source_module: str | None = None
    target_module: str | None = None
    evidence_json: dict
    created_at: str | None = None

