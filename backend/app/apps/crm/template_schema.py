"""Shared migration entry point for both supported migration histories."""
import sqlalchemy as sa


def upgrade(op):
    op.create_table("crm_visual_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("module", sa.String(24), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("folder", sa.String(100), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("design", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("email_template_id", sa.Integer(), sa.ForeignKey("communication_email_templates.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_crm_visual_templates_organization_id", "crm_visual_templates", ["organization_id"])


def downgrade(op):
    op.drop_table("crm_visual_templates")
