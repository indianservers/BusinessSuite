from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AssetCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class AssetCategorySchema(AssetCategoryCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AssetCreate(BaseModel):
    asset_tag: str
    name: str
    category_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    condition: str = "Good"
    status: str = "Available"
    location: Optional[str] = None
    description: Optional[str] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[Decimal] = None
    warranty_expiry: Optional[date] = None
    condition: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class AssetSchema(AssetCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AssetAssignmentCreate(BaseModel):
    asset_id: int
    employee_id: int
    assigned_date: date
    condition_at_assignment: Optional[str] = None
    remarks: Optional[str] = None


class AssetAssignmentSchema(AssetAssignmentCreate):
    asset_name: Optional[str] = None
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    id: int
    returned_date: Optional[date] = None
    acknowledgement_signed: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    returned_by: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
