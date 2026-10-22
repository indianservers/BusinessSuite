"""Shared collaboration events and resumable scheduled jobs."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261022_002"
down_revision = "pg_20261022_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pms_collaboration_events", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("project_id", sa.Integer(), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_pms_collaboration_events_project_id", "pms_collaboration_events", ["project_id"])
    op.create_index("ix_pms_collaboration_events_created_at", "pms_collaboration_events", ["created_at"])
    op.create_table("scheduled_job_runs", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("job_name", sa.String(100), nullable=False),
                    sa.Column("period", sa.String(20), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("cursor", sa.Integer(), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("lease_until", sa.DateTime(timezone=True)),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("error", sa.Text()), sa.Column("result", sa.JSON()),
                    sa.UniqueConstraint("job_name", "period", name="uq_scheduled_job_period"))


def downgrade():
    op.drop_table("scheduled_job_runs")
    op.drop_table("pms_collaboration_events")
