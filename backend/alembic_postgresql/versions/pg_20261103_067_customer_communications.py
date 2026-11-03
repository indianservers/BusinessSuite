"""Customer identities, journeys, shipments and durable delivery intent."""
revision = 'pg_20261103_067_customer_comms'
down_revision = 'pg_20261103_066_wa_branch'
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    from app.apps.communication import customer_models as models
    from sqlalchemy import inspect
    names = set(inspect(op.get_bind()).get_table_names())
    for model in (models.CustomerRecipient, models.CustomerCommunicationSettings, models.CustomerEmailConnection, models.CustomerAutomation,
                  models.CustomerBinding, models.CustomerEvent, models.CustomerDelivery, models.CustomerShipment,
                  models.CustomerPreferenceToken, models.CustomerConversationNote, models.CustomerEmailReply):
        if model.__tablename__ not in names:
            model.__table__.create(op.get_bind())


def downgrade():
    raise RuntimeError('Customer communication history must be retained; use a reviewed restore')
