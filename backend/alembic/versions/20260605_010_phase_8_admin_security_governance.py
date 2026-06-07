"""phase 8 admin security governance

Revision ID: 20260605_010
Revises: 20260605_009
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_010"
down_revision = "20260605_009"
branch_labels = None
depends_on = None


def ts():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table("admin_profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text()), sa.Column("active", sa.Boolean(), default=True), ts(), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("name"))
    op.create_table("admin_profile_permissions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("admin_profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("permission_name", sa.String(120), nullable=False), sa.Column("allowed", sa.Boolean(), default=True), ts(), sa.UniqueConstraint("profile_id", "permission_name", name="uq_admin_profile_permission"))
    op.create_table("admin_roles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text()), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("admin_profiles.id", ondelete="SET NULL")), sa.Column("active", sa.Boolean(), default=True), ts(), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("name"))
    op.create_table("admin_role_hierarchy", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("parent_role_id", sa.Integer(), sa.ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False), sa.Column("child_role_id", sa.Integer(), sa.ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False), ts(), sa.UniqueConstraint("parent_role_id", "child_role_id", name="uq_admin_role_hierarchy"))
    op.create_table("admin_field_security", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("field_name", sa.String(120), nullable=False), sa.Column("profile_id", sa.Integer(), sa.ForeignKey("admin_profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("can_view", sa.Boolean(), default=True), sa.Column("can_edit", sa.Boolean(), default=True), sa.Column("mask_value", sa.Boolean(), default=False), ts(), sa.UniqueConstraint("module_name", "field_name", "profile_id", name="uq_admin_field_security"))
    op.create_table("admin_record_sharing_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("rule_name", sa.String(160), nullable=False), sa.Column("condition_json", sa.JSON()), sa.Column("share_with_type", sa.String(40), nullable=False), sa.Column("share_with_id", sa.Integer(), nullable=False), sa.Column("access_level", sa.String(20), default="read"), sa.Column("active", sa.Boolean(), default=True), ts())
    op.create_table("admin_manual_record_shares", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("record_id", sa.Integer(), nullable=False), sa.Column("share_with_type", sa.String(40), nullable=False), sa.Column("share_with_id", sa.Integer(), nullable=False), sa.Column("access_level", sa.String(20), default="read"), sa.Column("active", sa.Boolean(), default=True), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), ts(), sa.UniqueConstraint("module_name", "record_id", "share_with_type", "share_with_id", name="uq_admin_manual_share"))
    op.create_table("admin_data_sharing_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("rule_json", sa.JSON()), sa.Column("access_level", sa.String(20), default="read"), sa.Column("active", sa.Boolean(), default=True), ts())
    op.create_table("admin_ip_restrictions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("cidr", sa.String(80), nullable=False), sa.Column("action", sa.String(20), default="allow"), sa.Column("description", sa.String(255)), sa.Column("active", sa.Boolean(), default=True), sa.Column("environment_safe", sa.Boolean(), default=True), ts())
    op.create_table("admin_audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("module_name", sa.String(100)), sa.Column("resource_type", sa.String(100)), sa.Column("resource_id", sa.Integer()), sa.Column("status", sa.String(30), default="completed"), sa.Column("detail_json", sa.JSON()), ts())
    op.create_table("admin_import_jobs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("filename", sa.String(240), nullable=False), sa.Column("status", sa.String(30), default="uploaded"), sa.Column("total_rows", sa.Integer(), default=0), sa.Column("success_rows", sa.Integer(), default=0), sa.Column("failed_rows", sa.Integer(), default=0), sa.Column("duplicate_rows", sa.Integer(), default=0), sa.Column("mapping_json", sa.JSON()), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), ts(), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_table("admin_import_job_rows", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("import_job_id", sa.Integer(), sa.ForeignKey("admin_import_jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("row_number", sa.Integer(), nullable=False), sa.Column("raw_json", sa.JSON()), sa.Column("mapped_json", sa.JSON()), sa.Column("status", sa.String(30), default="pending"), sa.Column("error_message", sa.Text()))
    op.create_table("admin_duplicate_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("match_fields_json", sa.JSON()), sa.Column("match_logic", sa.String(40), default="any"), sa.Column("active", sa.Boolean(), default=True), ts())
    op.create_table("admin_duplicate_candidates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("rule_id", sa.Integer(), sa.ForeignKey("admin_duplicate_rules.id", ondelete="SET NULL")), sa.Column("record_id", sa.Integer(), nullable=False), sa.Column("duplicate_record_id", sa.Integer(), nullable=False), sa.Column("confidence_score", sa.Integer(), default=0), sa.Column("status", sa.String(30), default="open"), sa.Column("evidence_json", sa.JSON()), ts())
    op.create_table("admin_merge_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("winner_record_id", sa.Integer(), nullable=False), sa.Column("loser_record_ids_json", sa.JSON()), sa.Column("merged_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("detail_json", sa.JSON()), ts())
    op.create_table("admin_export_controls", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("max_rows", sa.Integer(), default=1000), sa.Column("require_approval", sa.Boolean(), default=False), sa.Column("watermark", sa.Boolean(), default=True), sa.Column("active", sa.Boolean(), default=True), ts())
    op.create_table("admin_backup_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scope", sa.String(100), default="crm"), sa.Column("status", sa.String(30), default="requested"), sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("detail_json", sa.JSON()))
    op.create_table("admin_compliance_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("setting_key", sa.String(120), nullable=False), sa.Column("setting_value_json", sa.JSON()), sa.Column("active", sa.Boolean(), default=True), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("setting_key"))
    op.create_table("admin_data_retention_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("module_name", sa.String(100), nullable=False), sa.Column("retention_days", sa.Integer(), nullable=False), sa.Column("action", sa.String(40), default="archive"), sa.Column("active", sa.Boolean(), default=True), ts())


def downgrade() -> None:
    for name in (
        "admin_data_retention_rules",
        "admin_compliance_settings",
        "admin_backup_requests",
        "admin_export_controls",
        "admin_merge_logs",
        "admin_duplicate_candidates",
        "admin_duplicate_rules",
        "admin_import_job_rows",
        "admin_import_jobs",
        "admin_audit_logs",
        "admin_ip_restrictions",
        "admin_data_sharing_rules",
        "admin_manual_record_shares",
        "admin_record_sharing_rules",
        "admin_field_security",
        "admin_role_hierarchy",
        "admin_roles",
        "admin_profile_permissions",
        "admin_profiles",
    ):
        op.drop_table(name)
