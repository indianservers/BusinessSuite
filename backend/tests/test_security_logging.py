import logging
from app.core.log_filters import SecurityLogFilter


def test_server_access_log_does_not_expose_bearer_download_links():
    record=logging.LogRecord('uvicorn.access',logging.INFO,'server.py',1,'%s - "%s %s HTTP/%s" %d',('synthetic-client','GET','/api/v1/files/blob?token=SYNTHETIC-PRIVATE-CAPABILITY','1.1',200),None)
    SecurityLogFilter().filter(record)
    result=record.getMessage()
    assert 'SYNTHETIC-PRIVATE-CAPABILITY' not in result
    assert '/api/v1/files/blob' in result and '200' in result


def test_server_exception_log_excludes_parameter_values():
    try:
        raise ValueError('SYNTHETIC-RESTRICTED-PARAMETER')
    except ValueError:
        import sys
        record=logging.LogRecord('uvicorn.error',logging.ERROR,'server.py',1,'ASGI failed',(),sys.exc_info())
    SecurityLogFilter(redact_exceptions=True).filter(record)
    output=logging.Formatter().format(record)
    assert 'SYNTHETIC-RESTRICTED-PARAMETER' not in output
    assert 'ValueError' in output


def test_websocket_access_log_omits_query_tokens():
    record=logging.LogRecord('uvicorn.error',logging.INFO,'server.py',1,'%s - "WebSocket %s" [accepted]',('synthetic-client','/api/v1/project-management/realtime?token=SYNTHETIC-SECRET'),None)
    SecurityLogFilter().filter(record)
    assert 'SYNTHETIC-SECRET' not in record.getMessage()
