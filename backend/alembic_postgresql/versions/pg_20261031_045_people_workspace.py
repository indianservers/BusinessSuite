"""Normalize existing team identities and index scoped directory searches.

The historical bootstrap creates current ORM tables on a fresh database. Introspection
supports both that bootstrap and a deployed legacy schema; backfill always runs.
"""

import json
from alembic import op
import sqlalchemy as sa

revision = "pg_20261031_045_people_workspace"
down_revision = "pg_20261031_044_note_visibility"
branch_labels = None
depends_on = None


def index(name, table, columns):
    if name not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}:
        op.create_index(name, table, columns)


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("pms_workspace_teams")}
    if "description" not in columns:
        op.add_column(
            "pms_workspace_teams",
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
        )
    if "lead_user_id" not in columns:
        with op.batch_alter_table("pms_workspace_teams") as batch:
            batch.add_column(sa.Column("lead_user_id", sa.Integer()))
            batch.create_foreign_key(
                "fk_pms_team_lead_user",
                "users",
                ["lead_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
    if "visibility" not in columns:
        op.add_column(
            "pms_workspace_teams",
            sa.Column(
                "visibility", sa.String(20), nullable=False, server_default="workspace"
            ),
        )
    index(
        "ix_pms_workspace_teams_lead_user_id", "pms_workspace_teams", ["lead_user_id"]
    )
    if "pms_workspace_team_members" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "pms_workspace_team_members",
            sa.Column(
                "team_id",
                sa.Integer(),
                sa.ForeignKey("pms_workspace_teams.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )
    index(
        "ix_pms_workspace_team_members_user_id",
        "pms_workspace_team_members",
        ["user_id"],
    )
    rows = bind.execute(
        sa.text("SELECT id,workspace_id,member_ids_json FROM pms_workspace_teams")
    ).mappings()
    members = sa.table(
        "pms_workspace_team_members",
        sa.column("team_id", sa.Integer),
        sa.column("user_id", sa.Integer),
    )
    for row in rows:
        try:
            ids = set(json.loads(row["member_ids_json"] or "[]"))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid membership JSON for team {row['id']}; repair before migration"
            )
        eligible = {
            r[0]
            for r in bind.execute(
                sa.text(
                    "SELECT user_id FROM pms_workspace_members WHERE workspace_id=:wid AND role <> 'Guest'"
                ),
                {"wid": row["workspace_id"]},
            )
        }
        existing = {
            r[0]
            for r in bind.execute(
                sa.text(
                    "SELECT user_id FROM pms_workspace_team_members WHERE team_id=:tid"
                ),
                {"tid": row["id"]},
            )
        }
        values = [
            {"team_id": row["id"], "user_id": uid}
            for uid in (ids & eligible) - existing
        ]
        if values:
            bind.execute(members.insert(), values)
    index("ix_users_role_active_id", "users", ["role_id", "is_active", "id"])
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for name, table, column in [
            ("ix_people_name_trgm", "common_people", "display_name"),
            ("ix_people_email_trgm", "users", "email"),
            ("ix_people_employee_code_trgm", "employees", "employee_id"),
        ]:
            op.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({column} gin_trgm_ops)"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for name in [
            "ix_people_name_trgm",
            "ix_people_email_trgm",
            "ix_people_employee_code_trgm",
        ]:
            op.drop_index(name)
    op.drop_index("ix_users_role_active_id", table_name="users")
    op.drop_table("pms_workspace_team_members")
    op.drop_index(
        "ix_pms_workspace_teams_lead_user_id", table_name="pms_workspace_teams"
    )
    op.drop_column("pms_workspace_teams", "visibility")
    constraints = [
        f["name"]
        for f in sa.inspect(op.get_bind()).get_foreign_keys("pms_workspace_teams")
        if f["constrained_columns"] == ["lead_user_id"] and f.get("name")
    ]
    with op.batch_alter_table("pms_workspace_teams") as batch:
        for name in constraints:
            batch.drop_constraint(name, type_="foreignkey")
        batch.drop_column("lead_user_id")
    op.drop_column("pms_workspace_teams", "description")
