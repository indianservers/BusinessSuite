import logging

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    # Authentication emails can contain reset links and one-time codes.
    logger.info("email_dispatch_requested provider=unconfigured")
