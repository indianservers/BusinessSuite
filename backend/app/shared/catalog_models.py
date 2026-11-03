"""Shared extensions over the existing product/service source records."""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, CheckConstraint, Index, Numeric
from app.db.base_class import Base


class CatalogDetails(Base):
    __tablename__ = "shared_catalog_details"
    __table_args__ = (
        CheckConstraint("(product_id IS NOT NULL AND service_id IS NULL) OR (product_id IS NULL AND service_id IS NOT NULL)", name="ck_catalog_details_item"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), unique=True)
    service_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), unique=True)
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id", ondelete="RESTRICT"), nullable=True, index=True)
    unit = Column(String(40), default="unit", nullable=False)
    images = Column(JSON, default=list, nullable=False)
    custom_fields = Column(JSON, default=dict, nullable=False)
    pricing_options = Column(JSON, default=list, nullable=False)
    version = Column(Integer, default=1, nullable=False)


class CatalogLink(Base):
    __tablename__ = "shared_catalog_links"
    __table_args__ = (
        CheckConstraint("(product_id IS NOT NULL AND service_id IS NULL) OR (product_id IS NULL AND service_id IS NOT NULL)", name="ck_catalog_link_item"),
        Index("ix_catalog_link_target", "organization_id", "target_type", "target_id"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=False)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"))
    service_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"))
    pricing_id = Column(String(80))
    quantity = Column(Numeric(14, 4), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    discount = Column(Numeric(5, 2), nullable=False, default=0)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False)
