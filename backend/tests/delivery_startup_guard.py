"""Loaded before conftest: ordinary application import cannot be test-masked."""
from sqlalchemy import event
from sqlalchemy.engine import Engine
statements=[]
def observed(connection,cursor,statement,parameters,context,executemany):
    if statement.lstrip().split(None,1)[0].upper() in {'CREATE','ALTER','DROP','INSERT','UPDATE','DELETE','TRUNCATE'}:statements.append(1)
event.listen(Engine,'before_cursor_execute',observed)
try:
    from app.main import app
    from app.business_packs import delivery_sources
    from app.services import email_events
    from sqlalchemy.orm import Session
    probe=Session()
    try:
        callbacks=list(probe.dispatch.after_flush_postexec)
        assert callbacks.index(delivery_sources.finalize_births)<callbacks.index(email_events.enqueue_email_events)
    finally:probe.close()
    assert not statements,'Ordinary import must not perform DDL/DML'
finally:event.remove(Engine,'before_cursor_execute',observed)
from app.core import email
def no_network(*args,**kwargs):raise AssertionError('No real provider call permitted in native producer proof')
email.send_email=no_network
