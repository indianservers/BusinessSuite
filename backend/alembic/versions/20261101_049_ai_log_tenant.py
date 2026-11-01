"""Give new AI action logs explicit company ownership; never guess historical tenants."""
from alembic import op
import sqlalchemy as sa
revision = "20261101_049_ai_log_tenant"
down_revision = "20261031_048_drag_arrangement"
branch_labels = None
depends_on = None


TABLES = ("ai_prompt_runs", "ai_action_logs", "ai_agent_actions", "ai_user_feedback")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_organization", "companies", ["organization_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        inspector = sa.inspect(op.get_bind())
        source_column = "id" if table == "ai_prompt_runs" else "prompt_run_id"
        if inspector.has_table("security_resource_ownership") and source_column in {c["name"] for c in inspector.get_columns(table)}:
            # Only uniquely recorded parent ownership is authoritative.
            op.execute(sa.text(f"""
                UPDATE {table} SET organization_id = (
                    SELECT MIN(o.company_id) FROM security_resource_ownership o
                    WHERE o.resource_table = 'ai_prompt_runs'
                      AND o.resource_id = {table}.{source_column}
                    HAVING COUNT(DISTINCT o.company_id) = 1
                ) WHERE organization_id IS NULL AND {source_column} IS NOT NULL
            """))


def downgrade():
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_organization", type_="foreignkey")
            batch.drop_column("organization_id")
