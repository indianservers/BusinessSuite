"""Shared by both supported migration chains."""
def upgrade(op):
    from .calendar_sync_models import CalendarSyncState, CalendarEventLink
    for model in (CalendarSyncState, CalendarEventLink):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade(op):
    from .calendar_sync_models import CalendarSyncState, CalendarEventLink
    for model in (CalendarEventLink, CalendarSyncState):
        model.__table__.drop(op.get_bind(), checkfirst=True)
