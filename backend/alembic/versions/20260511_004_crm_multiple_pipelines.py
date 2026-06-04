"""Backfill CRM default pipelines and stages

Revision ID: 20260511_004_crm_multiple_pipelines
Revises: 20260511_003_crm_email_compose
Create Date: 2026-05-11 04:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_004_crm_multiple_pipelines"
down_revision = "20260511_003_crm_email_compose"
branch_labels = None
depends_on = None


DEFAULT_STAGES = [
    ("Prospecting", 10, 1, "#2563eb", False, False),
    ("Qualification", 25, 2, "#0891b2", False, False),
    ("Needs Analysis", 40, 3, "#7c3aed", False, False),
    ("Proposal Sent", 55, 4, "#f59e0b", False, False),
    ("Negotiation", 70, 5, "#ea580c", False, False),
    ("Contract Sent", 85, 6, "#db2777", False, False),
    ("Won", 100, 7, "#16a34a", True, False),
    ("Lost", 0, 8, "#dc2626", False, True),
]


def upgrade() -> None:
    conn = op.get_bind()
    org_rows = conn.execute(
        sa.text(
            """
            SELECT organization_id FROM crm_deals WHERE organization_id IS NOT NULL
            UNION
            SELECT organization_id FROM crm_pipelines WHERE organization_id IS NOT NULL
            """
        )
    ).fetchall()
    organization_ids = [row[0] for row in org_rows] or [1]
    for organization_id in organization_ids:
        pipeline_id = conn.execute(
            sa.text("SELECT id FROM crm_pipelines WHERE organization_id = :org ORDER BY is_default DESC, id LIMIT 1"),
            {"org": organization_id},
        ).scalar()
        if not pipeline_id:
            result = conn.execute(
                sa.text(
                    """
                    INSERT INTO crm_pipelines (organization_id, name, description, is_default, created_at)
                    VALUES (:org, 'Default Sales Pipeline', 'Default CRM sales process', true, CURRENT_TIMESTAMP)
                    """
                ),
                {"org": organization_id},
            )
            pipeline_id = result.lastrowid
            if not pipeline_id:
                pipeline_id = conn.execute(
                    sa.text(
                        """
                        SELECT id FROM crm_pipelines
                        WHERE organization_id = :org AND name = 'Default Sales Pipeline'
                        ORDER BY id DESC LIMIT 1
                        """
                    ),
                    {"org": organization_id},
                ).scalar()
        for name, probability, position, color, is_won, is_lost in DEFAULT_STAGES:
            exists = conn.execute(
                sa.text("SELECT id FROM crm_pipeline_stages WHERE organization_id = :org AND pipeline_id = :pipeline AND name = :name"),
                {"org": organization_id, "pipeline": pipeline_id, "name": name},
            ).scalar()
            if not exists:
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO crm_pipeline_stages (organization_id, pipeline_id, name, probability, position, color, is_won, is_lost, created_at)
                        VALUES (:org, :pipeline, :name, :probability, :position, :color, :is_won, :is_lost, CURRENT_TIMESTAMP)
                        """
                    ),
                    {"org": organization_id, "pipeline": pipeline_id, "name": name, "probability": probability, "position": position, "color": color, "is_won": is_won, "is_lost": is_lost},
                )
        first_stage_id = conn.execute(
            sa.text("SELECT id FROM crm_pipeline_stages WHERE organization_id = :org AND pipeline_id = :pipeline ORDER BY position, id LIMIT 1"),
            {"org": organization_id, "pipeline": pipeline_id},
        ).scalar()
        if first_stage_id:
            conn.execute(
                sa.text(
                    """
                    UPDATE crm_deals
                    SET pipeline_id = COALESCE(pipeline_id, :pipeline),
                        stage_id = COALESCE(stage_id, :stage)
                    WHERE organization_id = :org
                    """
                ),
                {"org": organization_id, "pipeline": pipeline_id, "stage": first_stage_id},
            )


def downgrade() -> None:
    pass
