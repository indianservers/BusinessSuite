from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class AssetCategorySchema(AssetCategoryCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AssetSerialInput(BaseModel):
    @field_validator("serial_number", mode="before", check_fields=False)
    @classmethod
    def normalize_serial(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class AssetCreate(AssetSerialInput):
    asset_tag: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    category_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    warranty_expiry: Optional[date] = None
    condition: str = "Good"
    status: str = "Available"
    location: Optional[str] = None
    description: Optional[str] = None
    details: dict = Field(default_factory=dict)


class AssetUpdate(AssetSerialInput):
    name: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    warranty_expiry: Optional[date] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    details: Optional[dict] = None


class AssetSchema(AssetCreate):
    assigned_employee: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AssetAssignmentCreate(BaseModel):
    asset_id: int
    employee_id: int
    assigned_date: date
    condition_at_assignment: Optional[str] = None
    remarks: Optional[str] = Field(default=None, max_length=4000)
    expected_return_date: Optional[date] = None
    accessories: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def due_after_assignment(self):
        if self.expected_return_date and self.expected_return_date < self.assigned_date:
            raise ValueError("Expected return cannot precede assignment")
        return self


class AssetAssignmentSchema(AssetAssignmentCreate):
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    id: int
    handover_group: Optional[str] = None
    inspection_status: str = "Not Required"
    inspection_approval_id: Optional[int] = None
    recovery_amount: Decimal = Decimal("0")
    recovery_status: str = "None"
    return_details: dict = Field(default_factory=dict)
    returned_date: Optional[date] = None
    acknowledgement_signed: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    returned_by: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AssetHandover(BaseModel):
    employee_id: int = Field(gt=0)
    asset_ids: list[int] = Field(min_length=1, max_length=50)
    assigned_date: date
    expected_return_date: Optional[date] = None
    condition_at_assignment: str = "Good"
    accessories: list[str] = Field(default_factory=list, max_length=40)
    remarks: str = Field(default="", max_length=4000)
    handover_document_ids: dict[int, list[int]] = Field(default_factory=dict, max_length=50)
    request_key: str = Field(min_length=8, max_length=80)

    @model_validator(mode="after")
    def valid_batch(self):
        if any(key not in self.asset_ids or len(ids)>20 for key,ids in self.handover_document_ids.items()):
            raise ValueError("Handover evidence must belong to selected assets, with at most 20 documents each")
        if len(set(self.asset_ids)) != len(self.asset_ids) or any(i < 1 for i in self.asset_ids):
            raise ValueError("Select distinct positive asset IDs")
        if self.expected_return_date and self.expected_return_date < self.assigned_date:
            raise ValueError("Expected return cannot precede assignment")
        return self


class AssetReturn(BaseModel):
    return_date: date
    condition: str = Field(pattern="^(New|Good|Fair|Poor|Damaged|Missing Accessories|Lost|Under Inspection|Under Repair)$")
    accessories_returned: list[str] = Field(default_factory=list, max_length=40)
    missing_accessories: list[str] = Field(default_factory=list, max_length=40)
    remarks: str = Field(default="", max_length=4000)
    damage_description: str = Field(default="", max_length=4000)
    employee_acknowledged: bool = False
    photo_document_ids: list[int] = Field(default_factory=list, max_length=20)


class AssetInspection(BaseModel):
    comments: str = Field(min_length=3, max_length=4000)
    disposition: str = Field(pattern="^(Available|Under Repair|Lost|Damaged|Retired)$")
    condition: str = Field(pattern="^(New|Good|Fair|Poor|Damaged|Lost)$")
    missing_resolved: bool = False
    photo_document_ids: list[int] = Field(default_factory=list, max_length=20)


class AssetRecovery(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=5, max_length=4000)
    policy_reference: str = Field(min_length=3, max_length=500)


class AssetDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=3, max_length=2000)


class AssetSettlement(BaseModel):
    reference: str = Field(min_length=3, max_length=500)


class AssetExtension(BaseModel):
    expected_return_date: date
    reason: str = Field(min_length=3, max_length=1000)


class AssetTransfer(BaseModel):
    employee_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=2000)
    assigned_date: date
    expected_return_date: Optional[date] = None
    condition: str = Field(default="Good", pattern="^(New|Good|Fair)$")


class AssetException(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    policy_reference: str = Field(min_length=3, max_length=500)


class AssetPolicy(BaseModel):
    inspection_approver_id: Optional[int] = None
    recovery_approver_id: Optional[int] = None
    exception_approver_id: Optional[int] = None
    block_damaged_clearance: bool = False
    block_missing_clearance: bool = True
    recovery_enabled: bool = False
    recovery_limit: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    reminders_enabled: bool = True
    reminder_days: int = Field(default=7, ge=0, le=365)
    repeat_days: int = Field(default=7, ge=1, le=90)
    channels: list[str] = Field(default_factory=lambda: ["in_app"], min_length=1, max_length=3)
    whatsapp_template: Optional[dict] = None
    manager_user_ids: list[int] = Field(default_factory=list, max_length=30)

    @field_validator("channels")
    @classmethod
    def channels_allowed(cls, value):
        if set(value) - {"in_app", "email", "whatsapp"}:
            raise ValueError("Choose in-app, email or WhatsApp")
        return list(dict.fromkeys(value))
