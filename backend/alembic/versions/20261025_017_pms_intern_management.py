"""PMS-owned work execution and HRMS internship orchestration. Legacy data is retained."""
from alembic import op
import sqlalchemy as sa
revision = "20261025_017_intern_pms"
down_revision = "20261025_016_intern_apps"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management import models as pms
    from app.apps.interns_hub import management_models as hr
    bind=op.get_bind()
    if "organization_id" not in {c["name"] for c in sa.inspect(bind).get_columns("intern_hub_courses")}:
        op.add_column("intern_hub_courses",sa.Column("organization_id",sa.Integer(),nullable=False,server_default="1"))
        # Department-owned historical courses follow their existing company.
        op.execute(sa.text("UPDATE intern_hub_courses SET organization_id=COALESCE((SELECT branches.company_id FROM departments JOIN branches ON branches.id=departments.branch_id WHERE departments.id=intern_hub_courses.department_id),1)"))
    if "ix_intern_hub_courses_organization_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("intern_hub_courses")}:
        op.create_index("ix_intern_hub_courses_organization_id","intern_hub_courses",["organization_id"])
    additions=[sa.Column("execution_status",sa.String(30),nullable=False,server_default="To Do"),sa.Column("due_date",sa.Date()),sa.Column("reviewer_user_id",sa.Integer()),sa.Column("maximum_score",sa.Integer(),nullable=False,server_default="100"),sa.Column("source_key",sa.String(80)),sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now())]
    columns={c["name"] for c in sa.inspect(bind).get_columns("pms_task_assignees")}
    for column in additions:
        if column.name not in columns:
            if column.name=="created_at" and bind.dialect.name=="sqlite":column=sa.Column("created_at",sa.DateTime(timezone=True))
            op.add_column("pms_task_assignees",column)
    op.execute(sa.text("UPDATE pms_task_assignees SET created_at=CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    for field in ["execution_status","due_date","reviewer_user_id","source_key"]:
        name="ix_pms_task_assignees_"+field
        if name not in {i["name"] for i in sa.inspect(bind).get_indexes("pms_task_assignees")}:op.create_index(name,"pms_task_assignees",[field])
    for column in [sa.Column("verification_id",sa.String(80)),sa.Column("document_certificate_id",sa.Integer())]:
        if column.name not in {c["name"] for c in sa.inspect(bind).get_columns("intern_hub_certificates")}:op.add_column("intern_hub_certificates",column)
    if "ux_intern_certificate_verification" not in {i["name"] for i in sa.inspect(bind).get_indexes("intern_hub_certificates")}:
        op.create_index("ux_intern_certificate_verification","intern_hub_certificates",["verification_id"],unique=True)
    if bind.dialect.name=="postgresql":
        for table,column,target in [("pms_task_assignees","reviewer_user_id","users"),("intern_hub_certificates","document_certificate_id","employee_certificates")]:
            name="fk_"+table+"_"+column
            if not any(fk["constrained_columns"]==[column] for fk in sa.inspect(bind).get_foreign_keys(table)):op.create_foreign_key(name,table,target,[column],["id"])
    for cls in [pms.PMSWorkSubmission,pms.PMSWorkReview,hr.InternBatch,hr.InternBatchMembership,hr.InternDistribution,hr.InternTaskSchedule,hr.InternCompletionReview,hr.InternReportReview,hr.InternLegacyTaskMap,hr.InternLegacyFileMap]:cls.__table__.create(bind,checkfirst=True)


def downgrade():
    # Keep submissions, reviewer decisions and program history when rolling back application code.
    pass
