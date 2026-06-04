"""advanced analytics and manufacturing domain pack

Revision ID: 20260529_005
Revises: 20260529_004
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_005"
down_revision = "20260529_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_definition_id", sa.Integer(), sa.ForeignKey("report_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("cron_expression", sa.String(length=80), nullable=False),
        sa.Column("recipients_json", sa.JSON()),
        sa.Column("export_format", sa.String(length=20), default="csv"),
        sa.Column("status", sa.String(length=30), default="Active"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_schedules_report_definition_id", "report_schedules", ["report_definition_id"])
    op.create_index("ix_report_schedules_status", "report_schedules", ["status"])

    op.create_table(
        "domain_pack_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE")),
        sa.Column("pack_key", sa.String(length=80), nullable=False),
        sa.Column("pack_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=30), default="Enabled"),
        sa.Column("config_json", sa.JSON()),
        sa.Column("enabled_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("enabled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_domain_pack_company_key", "domain_pack_registry", ["company_id", "pack_key"], unique=True)

    op.create_table(
        "manufacturing_safety_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(length=150)),
        sa.Column("incident_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=30), default="Low"),
        sa.Column("description", sa.Text()),
        sa.Column("lost_time_hours", sa.Numeric(8, 2), default=0),
        sa.Column("corrective_action", sa.Text()),
        sa.Column("status", sa.String(length=30), default="Open"),
        sa.Column("reported_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_manufacturing_safety_incidents_employee_id", "manufacturing_safety_incidents", ["employee_id"])

    op.create_table(
        "manufacturing_ppe_issuances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ppe_item", sa.String(length=120), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("condition", sa.String(length=40), default="New"),
        sa.Column("acknowledgement_status", sa.String(length=30), default="Pending"),
        sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_manufacturing_ppe_issuances_employee_id", "manufacturing_ppe_issuances", ["employee_id"])

    op.create_table(
        "manufacturing_medical_fitness_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("fitness_status", sa.String(length=40), nullable=False),
        sa.Column("valid_until", sa.Date()),
        sa.Column("restrictions", sa.Text()),
        sa.Column("provider_name", sa.String(length=150)),
        sa.Column("document_url", sa.String(length=500)),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_manufacturing_medical_fitness_records_employee_id", "manufacturing_medical_fitness_records", ["employee_id"])

    op.create_table(
        "manufacturing_contract_labor_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("vendor_name", sa.String(length=180), nullable=False),
        sa.Column("batch_code", sa.String(length=80), nullable=False),
        sa.Column("work_order_number", sa.String(length=100)),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("headcount", sa.Integer(), default=0),
        sa.Column("compliance_status", sa.String(length=40), default="Pending"),
        sa.Column("document_url", sa.String(length=500)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_manufacturing_contract_labor_batches_batch_code", "manufacturing_contract_labor_batches", ["batch_code"])


def downgrade() -> None:
    op.drop_table("manufacturing_contract_labor_batches")
    op.drop_table("manufacturing_medical_fitness_records")
    op.drop_table("manufacturing_ppe_issuances")
    op.drop_table("manufacturing_safety_incidents")
    op.drop_table("domain_pack_registry")
    op.drop_table("report_schedules")
