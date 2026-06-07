"""fam phase 9 inventory integrations

Revision ID: 20260607_019
Revises: 20260606_018
Create Date: 2026-06-07 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260607_019"
down_revision = "20260606_018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "fam_inventory_reservations" not in inspector.get_table_names():
        op.create_table(
            "fam_inventory_reservations",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("company_id", sa.Integer(), nullable=False, index=True),
            sa.Column("reservation_number", sa.String(length=120), nullable=False, index=True),
            sa.Column("stock_item_id", sa.Integer(), sa.ForeignKey("fam_stock_items.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("fam_warehouses.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
            sa.Column("reserved_quantity", sa.Numeric(14, 3), nullable=False),
            sa.Column("source_module", sa.String(length=40), nullable=False, index=True),
            sa.Column("source_record_type", sa.String(length=80), nullable=False, index=True),
            sa.Column("source_record_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("status", sa.String(length=30), nullable=True, server_default="active", index=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True, index=True),
            sa.UniqueConstraint("company_id", "source_module", "source_record_type", "source_record_id", "stock_item_id", name="uq_fam_inventory_reservation_source_item"),
        )

    if "fam_inventory_integration_links" not in inspector.get_table_names():
        op.create_table(
            "fam_inventory_integration_links",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("company_id", sa.Integer(), nullable=False, index=True),
            sa.Column("stock_item_id", sa.Integer(), sa.ForeignKey("fam_stock_items.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("target_module", sa.String(length=40), nullable=False, index=True),
            sa.Column("target_record_type", sa.String(length=80), nullable=False, index=True),
            sa.Column("target_record_id", sa.String(length=120), nullable=False, index=True),
            sa.Column("link_type", sa.String(length=60), nullable=True, server_default="catalog", index=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True, index=True),
            sa.UniqueConstraint("company_id", "stock_item_id", "target_module", "target_record_type", "target_record_id", name="uq_fam_inventory_link_target"),
        )

    if "fam_inventory_control_settings" not in inspector.get_table_names():
        op.create_table(
            "fam_inventory_control_settings",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("company_id", sa.Integer(), nullable=False, index=True),
            sa.Column("setting_key", sa.String(length=120), nullable=False, index=True),
            sa.Column("setting_value_json", sa.JSON(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True, index=True),
            sa.UniqueConstraint("company_id", "setting_key", name="uq_fam_inventory_control_setting"),
        )


def downgrade() -> None:
    for table_name in (
        "fam_inventory_control_settings",
        "fam_inventory_integration_links",
        "fam_inventory_reservations",
    ):
        op.drop_table(table_name)
