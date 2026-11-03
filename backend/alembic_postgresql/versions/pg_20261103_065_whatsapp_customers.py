"""Customer WhatsApp connections, consent, inbox, and durable delivery receipts."""
revision = "pg_20261103_065_whatsapp"
down_revision = "pg_20261103_064_follow_ups"
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    from app.shared.whatsapp_models import WhatsAppConnection, WhatsAppOnboarding, WhatsAppContact, WhatsAppMessage, WhatsAppReceipt
    for model in (WhatsAppConnection, WhatsAppOnboarding, WhatsAppContact, WhatsAppMessage, WhatsAppReceipt):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Customer messaging history must be retained; use a reviewed restore procedure")
