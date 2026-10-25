"""Interns Hub workflows, sharing HRMS employee identities."""
from alembic import op
revision = "pg_20261025_015_interns"
down_revision = "pg_20261024_014_suite"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.interns_hub import models
    for name in ["InternTask", "InternSubmission", "InternReport", "InternCourse", "InternEnrollment", "InternCertificate", "InternFile", "InternTicket"]:
        getattr(models, name).__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    from app.apps.interns_hub import models
    for name in ["InternTicket", "InternFile", "InternCertificate", "InternEnrollment", "InternCourse", "InternReport", "InternSubmission", "InternTask"]:
        getattr(models, name).__table__.drop(op.get_bind(), checkfirst=True)
