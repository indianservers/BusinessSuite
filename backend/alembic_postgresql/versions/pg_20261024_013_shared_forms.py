"""Shared forms, anonymous submissions and private response files."""

from alembic import op

revision = "pg_20261024_013"
down_revision = "pg_20261024_012"
branch_labels = None
depends_on = None


def upgrade():
    from app.forms.models import (
        SuiteForm,
        FormReply,
        FormFile,
        FormChallenge,
        FormRateBucket,
    )

    for model in (SuiteForm, FormReply, FormFile, FormChallenge, FormRateBucket):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for table in (
        "suite_form_rate_buckets",
        "suite_form_challenges",
        "suite_form_files",
        "suite_form_replies",
        "suite_forms",
    ):
        op.drop_table(table)
