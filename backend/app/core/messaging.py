import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MessagingResult:
    status: str
    message: str

    @property
    def sent(self) -> bool:
        return self.status == "Sent"


def send_sms(to: str, body: str) -> MessagingResult:
    if not to:
        return MessagingResult(status="Skipped", message="SMS destination missing")
    logger.info("SMS queued to=%s body=%s", to, body)
    return MessagingResult(status="Sent", message="SMS queued through stub provider")


def send_whatsapp(to: str, body: str) -> MessagingResult:
    if not to:
        return MessagingResult(status="Skipped", message="WhatsApp destination missing")
    logger.info("WhatsApp queued to=%s body=%s", to, body)
    return MessagingResult(status="Sent", message="WhatsApp queued through stub provider")
