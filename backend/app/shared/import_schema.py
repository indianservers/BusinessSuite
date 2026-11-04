from app.shared.import_models import ImportBatch, ImportConnection


def upgrade(op):
    for model in (ImportBatch, ImportConnection):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade(op):
    for model in (ImportConnection, ImportBatch):
        model.__table__.drop(op.get_bind(), checkfirst=True)
