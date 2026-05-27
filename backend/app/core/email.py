import logging

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    logger.info("Email queued to=%s subject=%s body=%s", to, subject, body)
