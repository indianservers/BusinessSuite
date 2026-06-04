"""deepen talent suite workflows

Revision ID: 20260529_004
Revises: 20260529_003
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_004"
down_revision = "20260529_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calibration_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("facilitator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(length=30), default="Draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("audit_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_calibration_sessions_cycle_id", "calibration_sessions", ["cycle_id"])
    op.create_index("ix_calibration_sessions_status", "calibration_sessions", ["status"])

    op.create_table(
        "calibration_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("calibration_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_rating", sa.Numeric(3, 1)),
        sa.Column("final_rating", sa.Numeric(3, 1)),
        sa.Column("potential_rating", sa.Numeric(3, 1)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(length=30), default="Proposed"),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_calibration_participants_session_id", "calibration_participants", ["session_id"])
    op.create_index("ix_calibration_participants_employee_id", "calibration_participants", ["employee_id"])

    op.create_table(
        "one_on_one_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("talking_points_json", sa.JSON()),
        sa.Column("action_items_json", sa.JSON()),
        sa.Column("private_manager_notes", sa.Text()),
        sa.Column("employee_notes", sa.Text()),
        sa.Column("status", sa.String(length=30), default="Open"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_one_on_one_records_employee_id", "one_on_one_records", ["employee_id"])
    op.create_index("ix_one_on_one_records_manager_id", "one_on_one_records", ["manager_id"])

    op.create_table(
        "critical_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_name", sa.String(length=160), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("designation_id", sa.Integer(), sa.ForeignKey("designations.id", ondelete="SET NULL")),
        sa.Column("incumbent_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("business_impact", sa.String(length=40), default="High"),
        sa.Column("vacancy_risk", sa.String(length=40), default="Medium"),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_critical_roles_is_active", "critical_roles", ["is_active"])

    op.create_table(
        "succession_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("critical_role_id", sa.Integer(), sa.ForeignKey("critical_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("readiness_level", sa.String(length=40), default="Ready in 1-2 years"),
        sa.Column("readiness_score", sa.Numeric(4, 2)),
        sa.Column("development_actions_json", sa.JSON()),
        sa.Column("mentor_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(length=30), default="Active"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_succession_candidates_critical_role_id", "succession_candidates", ["critical_role_id"])
    op.create_index("ix_succession_candidates_employee_id", "succession_candidates", ["employee_id"])

    op.add_column("learning_courses", sa.Column("content_standard", sa.String(length=30), server_default="Internal"))
    op.add_column("learning_courses", sa.Column("scorm_package_url", sa.String(length=500)))
    op.add_column("learning_courses", sa.Column("scorm_version", sa.String(length=40)))
    op.add_column("learning_courses", sa.Column("xapi_activity_id", sa.String(length=300)))
    op.add_column("learning_courses", sa.Column("xapi_launch_url", sa.String(length=500)))
    op.add_column("learning_courses", sa.Column("external_launch_url", sa.String(length=500)))
    op.add_column("learning_courses", sa.Column("completion_callback_url", sa.String(length=500)))
    op.add_column("learning_courses", sa.Column("metadata_json", sa.JSON()))
    op.add_column("learning_certifications", sa.Column("renewal_required", sa.Boolean(), server_default=sa.false()))
    op.add_column("learning_certifications", sa.Column("renewal_due_on", sa.Date()))
    op.add_column("learning_certifications", sa.Column("reminder_days", sa.Integer(), server_default="30"))
    op.add_column("learning_certifications", sa.Column("renewal_status", sa.String(length=30), server_default="Not Required"))
    op.add_column("learning_certifications", sa.Column("last_reminder_at", sa.DateTime(timezone=True)))

    op.create_table(
        "certification_renewals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("certification_id", sa.Integer(), sa.ForeignKey("learning_certifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), default="Due"),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_url", sa.String(length=500)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_certification_renewals_employee_id", "certification_renewals", ["employee_id"])
    op.create_index("ix_certification_renewals_due_on", "certification_renewals", ["due_on"])

    op.create_table(
        "compensation_worksheet_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("compensation_cycle_id", sa.Integer(), sa.ForeignKey("compensation_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manager_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("pay_band_id", sa.Integer(), sa.ForeignKey("pay_bands.id", ondelete="SET NULL")),
        sa.Column("current_ctc", sa.Numeric(14, 2), default=0),
        sa.Column("pay_band_min", sa.Numeric(14, 2), default=0),
        sa.Column("pay_band_midpoint", sa.Numeric(14, 2), default=0),
        sa.Column("pay_band_max", sa.Numeric(14, 2), default=0),
        sa.Column("proposed_merit_amount", sa.Numeric(14, 2), default=0),
        sa.Column("proposed_merit_percent", sa.Numeric(6, 2), default=0),
        sa.Column("proposed_ctc", sa.Numeric(14, 2), default=0),
        sa.Column("budget_impact", sa.Numeric(14, 2), default=0),
        sa.Column("approval_status", sa.String(length=30), default="Draft"),
        sa.Column("performance_rating", sa.Numeric(3, 1)),
        sa.Column("manager_notes", sa.Text()),
        sa.Column("hr_notes", sa.Text()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_compensation_worksheet_rows_cycle", "compensation_worksheet_rows", ["compensation_cycle_id"])
    op.create_index("ix_compensation_worksheet_rows_employee", "compensation_worksheet_rows", ["employee_id"])


def downgrade() -> None:
    op.drop_table("compensation_worksheet_rows")
    op.drop_table("certification_renewals")
    for column in ["last_reminder_at", "renewal_status", "reminder_days", "renewal_due_on", "renewal_required"]:
        op.drop_column("learning_certifications", column)
    for column in ["metadata_json", "completion_callback_url", "external_launch_url", "xapi_launch_url", "xapi_activity_id", "scorm_version", "scorm_package_url", "content_standard"]:
        op.drop_column("learning_courses", column)
    op.drop_table("succession_candidates")
    op.drop_table("critical_roles")
    op.drop_table("one_on_one_records")
    op.drop_table("calibration_participants")
    op.drop_table("calibration_sessions")
