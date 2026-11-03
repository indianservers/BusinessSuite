"""Shared service follow-ups and durable reminder receipts."""
revision = 'pg_20261103_064_follow_ups'
down_revision = 'pg_20261103_063_crm_features'
branch_labels = None
depends_on = None

def upgrade():
    from alembic import op
    from app.shared.follow_ups import FollowUp, FollowUpActivity, FollowUpReminder, FollowUpAttachment, FollowUpPreference
    for table in (FollowUp.__table__, FollowUpActivity.__table__, FollowUpReminder.__table__, FollowUpAttachment.__table__, FollowUpPreference.__table__):
        table.create(op.get_bind(), checkfirst=True)

def downgrade():
    raise RuntimeError('Follow-up history must be retained; restore a reviewed backup instead')
