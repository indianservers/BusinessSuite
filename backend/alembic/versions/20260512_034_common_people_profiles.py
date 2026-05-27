"""add common people and profiles

Revision ID: 20260512_034
Revises: 20260512_033
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_034"
down_revision = "20260512_033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "common_people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("primary_email", sa.String(length=150), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("first_name", sa.String(length=80), nullable=True),
        sa.Column("middle_name", sa.String(length=80), nullable=True),
        sa.Column("last_name", sa.String(length=80), nullable=True),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("source_module", sa.String(length=50), nullable=True),
        sa.Column("source_record_type", sa.String(length=80), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("external_refs_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("primary_email"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_common_people_id"), "common_people", ["id"], unique=False)
    op.create_index(op.f("ix_common_people_organization_id"), "common_people", ["organization_id"], unique=False)
    op.create_index(op.f("ix_common_people_primary_email"), "common_people", ["primary_email"], unique=False)
    op.create_index(op.f("ix_common_people_source_module"), "common_people", ["source_module"], unique=False)
    op.create_index(op.f("ix_common_people_source_record_id"), "common_people", ["source_record_id"], unique=False)
    op.create_index(op.f("ix_common_people_status"), "common_people", ["status"], unique=False)
    op.create_index("idx_common_people_org_status", "common_people", ["organization_id", "status"], unique=False)
    op.create_index("idx_common_people_source", "common_people", ["source_module", "source_record_type", "source_record_id"], unique=False)

    op.create_table(
        "common_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("preferred_display_name", sa.String(length=180), nullable=True),
        sa.Column("profile_photo_url", sa.String(length=500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=True),
        sa.Column("locale", sa.String(length=20), nullable=True),
        sa.Column("directory_visibility", sa.String(length=20), nullable=True),
        sa.Column("skills_json", sa.JSON(), nullable=True),
        sa.Column("profile_data_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["common_people.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id"),
    )
    op.create_index(op.f("ix_common_profiles_directory_visibility"), "common_profiles", ["directory_visibility"], unique=False)
    op.create_index(op.f("ix_common_profiles_id"), "common_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_common_profiles_person_id"), "common_profiles", ["person_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_common_profiles_person_id"), table_name="common_profiles")
    op.drop_index(op.f("ix_common_profiles_id"), table_name="common_profiles")
    op.drop_index(op.f("ix_common_profiles_directory_visibility"), table_name="common_profiles")
    op.drop_table("common_profiles")
    op.drop_index("idx_common_people_source", table_name="common_people")
    op.drop_index("idx_common_people_org_status", table_name="common_people")
    op.drop_index(op.f("ix_common_people_status"), table_name="common_people")
    op.drop_index(op.f("ix_common_people_source_record_id"), table_name="common_people")
    op.drop_index(op.f("ix_common_people_source_module"), table_name="common_people")
    op.drop_index(op.f("ix_common_people_primary_email"), table_name="common_people")
    op.drop_index(op.f("ix_common_people_organization_id"), table_name="common_people")
    op.drop_index(op.f("ix_common_people_id"), table_name="common_people")
    op.drop_table("common_people")
