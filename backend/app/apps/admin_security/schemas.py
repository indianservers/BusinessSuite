from typing import Any

from pydantic import BaseModel


class ProfilePayload(BaseModel):
    name: str
    description: str | None = None
    active: bool = True


class ProfilePermissionsPayload(BaseModel):
    permissions: list[str]


class AdminRolePayload(BaseModel):
    name: str
    description: str | None = None
    profile_id: int | None = None
    active: bool = True


class RoleHierarchyPayload(BaseModel):
    parent_role_id: int
    child_role_id: int


class FieldSecurityPayload(BaseModel):
    module_name: str
    field_name: str
    profile_id: int
    can_view: bool = True
    can_edit: bool = True
    mask_value: bool = False


class SharingRulePayload(BaseModel):
    module_name: str
    rule_name: str
    condition_json: dict[str, Any] = {}
    share_with_type: str
    share_with_id: int
    access_level: str = "read"
    active: bool = True


class ManualSharePayload(BaseModel):
    module_name: str
    record_id: int
    share_with_type: str
    share_with_id: int
    access_level: str = "read"


class DataSharingRulePayload(BaseModel):
    module_name: str
    name: str
    rule_json: dict[str, Any] = {}
    access_level: str = "read"
    active: bool = True


class IPRestrictionPayload(BaseModel):
    cidr: str
    action: str = "allow"
    description: str | None = None
    active: bool = True
    environment_safe: bool = True


class ImportUploadPayload(BaseModel):
    module_name: str
    filename: str
    rows: list[dict[str, Any]]


class ImportMapPayload(BaseModel):
    mapping: dict[str, str]


class DuplicateRulePayload(BaseModel):
    module_name: str
    name: str
    match_fields_json: list[str]
    match_logic: str = "any"
    active: bool = True


class DuplicateScanPayload(BaseModel):
    module_name: str


class DuplicateMergePayload(BaseModel):
    module_name: str
    winner_record_id: int
    loser_record_ids: list[int]


class ExportControlPayload(BaseModel):
    module_name: str
    max_rows: int = 1000
    require_approval: bool = False
    watermark: bool = True
    active: bool = True


class BackupRequestPayload(BaseModel):
    scope: str = "crm"


class CompliancePayload(BaseModel):
    setting_key: str
    setting_value_json: dict[str, Any]
    active: bool = True


class RetentionPayload(BaseModel):
    module_name: str
    retention_days: int
    action: str = "archive"
    active: bool = True
