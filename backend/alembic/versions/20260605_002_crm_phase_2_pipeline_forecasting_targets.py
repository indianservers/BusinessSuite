"""crm phase 2 pipeline forecasting targets

Revision ID: 20260605_002
Revises: 20260605_001
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_002"
down_revision = "20260605_001"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    _add_column_if_missing("crm_pipelines", sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()))
    _add_column_if_missing("crm_pipeline_stages", sa.Column("order_index", sa.Integer(), nullable=True, server_default="0"))
    _add_column_if_missing("crm_pipeline_stages", sa.Column("stage_type", sa.String(length=20), nullable=True, server_default="open"))
    _add_column_if_missing("crm_pipeline_stages", sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()))
    _add_column_if_missing("crm_territories", sa.Column("manager_id", sa.Integer(), nullable=True))
    _add_column_if_missing("crm_territories", sa.Column("region", sa.String(length=120), nullable=True))
    _add_column_if_missing("crm_territories", sa.Column("product_line", sa.String(length=120), nullable=True))
    _add_column_if_missing("crm_territories", sa.Column("service_line", sa.String(length=120), nullable=True))
    _add_column_if_missing("crm_territories", sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()))

    _create_index_if_missing("ix_crm_pipelines_active", "crm_pipelines", ["active"])
    _create_index_if_missing("ix_crm_pipeline_stages_order_index", "crm_pipeline_stages", ["order_index"])
    _create_index_if_missing("ix_crm_pipeline_stages_stage_type", "crm_pipeline_stages", ["stage_type"])
    _create_index_if_missing("ix_crm_pipeline_stages_active", "crm_pipeline_stages", ["active"])
    _create_index_if_missing("ix_crm_territories_region", "crm_territories", ["region"])
    _create_index_if_missing("ix_crm_territories_manager_id", "crm_territories", ["manager_id"])
    _create_index_if_missing("ix_crm_territories_product_line", "crm_territories", ["product_line"])
    _create_index_if_missing("ix_crm_territories_service_line", "crm_territories", ["service_line"])
    _create_index_if_missing("ix_crm_territories_active", "crm_territories", ["active"])

    op.execute("UPDATE crm_pipelines SET active = COALESCE(active, CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)")
    op.execute("UPDATE crm_pipeline_stages SET order_index = COALESCE(order_index, position, 0)")
    op.execute("UPDATE crm_pipeline_stages SET stage_type = CASE WHEN COALESCE(is_won, 0) = 1 THEN 'won' WHEN COALESCE(is_lost, 0) = 1 THEN 'lost' ELSE COALESCE(stage_type, 'open') END")
    op.execute("UPDATE crm_pipeline_stages SET active = COALESCE(active, CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)")
    op.execute("UPDATE crm_territories SET active = COALESCE(active, is_active, CASE WHEN status = 'Active' THEN 1 ELSE 0 END)")

    op.create_table(
        "crm_sales_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("period_type", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("target_owner_type", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("target_owner_id", sa.Integer(), nullable=True),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=True, server_default="INR"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_sales_targets_organization_id", "crm_sales_targets", ["organization_id"])
    op.create_index("ix_crm_sales_targets_period_start", "crm_sales_targets", ["period_start"])
    op.create_index("ix_crm_sales_targets_period_end", "crm_sales_targets", ["period_end"])
    op.create_index("ix_crm_sales_targets_target_owner_type", "crm_sales_targets", ["target_owner_type"])
    op.create_index("ix_crm_sales_targets_target_owner_id", "crm_sales_targets", ["target_owner_id"])

    op.create_table(
        "crm_forecast_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_name", sa.String(length=180), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("pipeline_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("territory_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True, server_default="INR"),
        sa.Column("pipeline_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("weighted_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("committed_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("best_case_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("upside_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("closed_won_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("invoiced_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("collected_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("scenarios_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["organization_id", "period_start", "period_end", "pipeline_id", "owner_user_id", "team_id", "territory_id"]:
        op.create_index(f"ix_crm_forecast_snapshots_{column}", "crm_forecast_snapshots", [column])

    op.create_table(
        "crm_territory_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("territory_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("assignment_type", sa.String(length=40), nullable=True, server_default="owner"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("territory_id", "user_id", "team_id", "assignment_type", name="uq_crm_territory_assignment"),
    )
    for column in ["organization_id", "territory_id", "user_id", "team_id", "assignment_type", "active"]:
        op.create_index(f"ix_crm_territory_assignments_{column}", "crm_territory_assignments", [column])

    op.create_table(
        "crm_lost_reasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_crm_lost_reason_org_name"),
    )
    op.create_index("ix_crm_lost_reasons_organization_id", "crm_lost_reasons", ["organization_id"])
    op.create_index("ix_crm_lost_reasons_name", "crm_lost_reasons", ["name"])
    op.create_index("ix_crm_lost_reasons_active", "crm_lost_reasons", ["active"])

    op.create_table(
        "crm_sales_performance_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("territory_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("pipeline_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("weighted_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("won_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("lost_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("invoiced_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("collected_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("activity_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("conversion_rate", sa.Numeric(6, 2), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["organization_id", "owner_user_id", "team_id", "territory_id", "period_start", "period_end"]:
        op.create_index(f"ix_crm_sales_performance_snapshots_{column}", "crm_sales_performance_snapshots", [column])


def downgrade() -> None:
    for table_name in [
        "crm_sales_performance_snapshots",
        "crm_lost_reasons",
        "crm_territory_assignments",
        "crm_forecast_snapshots",
        "crm_sales_targets",
    ]:
        op.drop_table(table_name)

    for index_name, table_name in [
        ("ix_crm_territories_active", "crm_territories"),
        ("ix_crm_territories_service_line", "crm_territories"),
        ("ix_crm_territories_product_line", "crm_territories"),
        ("ix_crm_territories_manager_id", "crm_territories"),
        ("ix_crm_territories_region", "crm_territories"),
        ("ix_crm_pipeline_stages_active", "crm_pipeline_stages"),
        ("ix_crm_pipeline_stages_stage_type", "crm_pipeline_stages"),
        ("ix_crm_pipeline_stages_order_index", "crm_pipeline_stages"),
        ("ix_crm_pipelines_active", "crm_pipelines"),
    ]:
        op.drop_index(index_name, table_name=table_name)

    for column_name in ["active", "service_line", "product_line", "region", "manager_id"]:
        op.drop_column("crm_territories", column_name)
    for column_name in ["active", "stage_type", "order_index"]:
        op.drop_column("crm_pipeline_stages", column_name)
    op.drop_column("crm_pipelines", "active")
