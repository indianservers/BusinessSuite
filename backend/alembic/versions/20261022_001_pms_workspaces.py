"""PMS workspaces, membership, and invitations.

Existing projects remain unassigned and retain their original access rules.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261022_001"
down_revision = ("20260612_001", "20260620_008")
branch_labels = None
depends_on = None


def create_table(name, *columns):
    # The suite also supports current-model bootstrap via create_all.
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns)


def upgrade():
    create_table("pms_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
    create_table("pms_workspace_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_pms_workspace_member"))
    create_table("pms_workspace_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(100), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("pms_projects")}
    foreign_keys = inspector.get_foreign_keys("pms_projects")
    indexes = {i["name"] for i in inspector.get_indexes("pms_projects")}
    with op.batch_alter_table("pms_projects") as batch:
        if "workspace_id" not in columns:
            batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        if not any(f["constrained_columns"] == ["workspace_id"] for f in foreign_keys):
            batch.create_foreign_key("fk_pms_project_workspace", "pms_workspaces", ["workspace_id"], ["id"], ondelete="RESTRICT")
        if "ix_pms_projects_workspace_id" not in indexes:
            batch.create_index("ix_pms_projects_workspace_id", ["workspace_id"])


def downgrade():
    with op.batch_alter_table("pms_projects") as batch:
        batch.drop_index("ix_pms_projects_workspace_id")
        batch.drop_constraint("fk_pms_project_workspace", type_="foreignkey")
        batch.drop_column("workspace_id")
    op.drop_table("pms_workspace_invitations")
    op.drop_table("pms_workspace_members")
    op.drop_table("pms_workspaces")
