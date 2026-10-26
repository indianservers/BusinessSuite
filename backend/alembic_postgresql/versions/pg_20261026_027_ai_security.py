"""Bind AI history, approvals and jobs to server-owned authorization context."""

from alembic import op
import sqlalchemy as sa

revision = "pg_20261026_027_ai_security"
down_revision = "pg_20261026_026_enterprise"
branch_labels = None
depends_on = None
TABLES = (
    "ai_handoff_notes",
    "ai_conversations",
    "ai_action_approvals",
    "ai_operator_runs",
    "ai_operator_proposals",
    "ai_suite_runs",
    "pms_assistant_conversations",
    "pms_assistant_messages",
    "pms_assistant_artifacts",
)


def add_column(table, column):
    if column.name not in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)
    }:
        op.add_column(table, column)


def create_index(name, table, columns, **kwargs):
    if name not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}:
        op.create_index(name, table, columns, **kwargs)


def upgrade():
    for table in TABLES:
        add_column(table, sa.Column("security_context", sa.JSON()))
    for table in (
        "ai_conversations",
        "ai_action_approvals",
        "ai_audit_logs",
        "ai_handoff_notes",
    ):
        add_column(table, sa.Column("organization_id", sa.Integer()))
        create_index("ix_" + table + "_organization_id", table, ["organization_id"])
    add_column("ai_audit_logs", sa.Column("session_id", sa.Integer()))
    add_column("ai_audit_logs", sa.Column("correlation_id", sa.String(64)))
    create_index("ix_ai_audit_logs_correlation_id", "ai_audit_logs", ["correlation_id"])
    add_column("ai_audit_logs", sa.Column("event_key", sa.String(64)))
    create_index(
        "ix_ai_audit_logs_event_key", "ai_audit_logs", ["event_key"], unique=True
    )
    # Historical context has no trustworthy session/tenant seal; never invent one.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION ai_security_audit_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'AI audit is append-only'; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER ai_security_audit_immutable BEFORE UPDATE OR DELETE ON ai_audit_logs FOR EACH ROW EXECUTE FUNCTION ai_security_audit_immutable()"
        )
    else:
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER ai_security_audit_no_{operation.lower()} BEFORE {operation} ON ai_audit_logs BEGIN SELECT RAISE(ABORT,'AI audit is append-only'); END"
            )


def downgrade():
    op.drop_index("ix_ai_audit_logs_event_key", table_name="ai_audit_logs")
    op.drop_column("ai_audit_logs", "event_key")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS ai_security_audit_immutable ON ai_audit_logs"
        )
        op.execute("DROP FUNCTION IF EXISTS ai_security_audit_immutable()")
    else:
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS ai_security_audit_no_{operation}")
    op.drop_index("ix_ai_audit_logs_correlation_id", table_name="ai_audit_logs")
    for name in ("session_id", "correlation_id"):
        op.drop_column("ai_audit_logs", name)
    for table in (
        "ai_conversations",
        "ai_action_approvals",
        "ai_audit_logs",
        "ai_handoff_notes",
    ):
        op.drop_index("ix_" + table + "_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
    for table in TABLES:
        op.drop_column(table, "security_context")
