from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class AssetCategory(Base):
    __tablename__ = "asset_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    assets = relationship("Asset", back_populates="category")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, default=1, server_default="1", index=True)
    asset_tag = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True)
    brand = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100), unique=True)
    purchase_date = Column(Date)
    purchase_cost = Column(Numeric(12, 2))
    warranty_expiry = Column(Date)
    condition = Column(String(30), default="Good")  # New, Good, Fair, Poor
    status = Column(String(30), default="Available")  # Available, Assigned, Under Repair, Retired
    location = Column(String(200))
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("AssetCategory", back_populates="assets")
    assignments = relationship("AssetAssignment", back_populates="asset")


class AssetAssignment(Base):
    __tablename__ = "asset_assignments"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    assigned_date = Column(Date, nullable=False)
    returned_date = Column(Date)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    condition_at_assignment = Column(String(30))
    condition_at_return = Column(String(30))
    remarks = Column(Text)
    acknowledgement_signed = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    returned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    asset = relationship("Asset", back_populates="assignments")
    employee = relationship("Employee", back_populates="assets")
