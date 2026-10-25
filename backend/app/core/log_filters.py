"""Keep bearer file links and exception parameter values out of server logs."""
import logging


class SecurityLogFilter(logging.Filter):
    def __init__(self, redact_exceptions=True):
        super().__init__()
        self.redact_exceptions=redact_exceptions

    def filter(self, record):
        # Uvicorn access args: client, method, path-with-query, version, status.
        if record.name.startswith('uvicorn.') and isinstance(record.args,tuple):
            record.args=tuple(value.partition('?')[0] if isinstance(value,str) and value.startswith('/') else value for value in record.args)
        if self.redact_exceptions and record.exc_info:
            record.msg='Server exception error_type=%s'
            record.args=(record.exc_info[0].__name__,)
            record.exc_info=None
            record.exc_text=None
        return True


def install_security_log_filters(redact_exceptions=True):
    for name in ('uvicorn.access','uvicorn.error'):
        logger=logging.getLogger(name)
        if not any(isinstance(value,SecurityLogFilter) for value in logger.filters):
            logger.addFilter(SecurityLogFilter(redact_exceptions))
