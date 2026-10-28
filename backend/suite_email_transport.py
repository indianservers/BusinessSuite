"""Shared suite email transport. Acceptance is not confirmed inbox delivery."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, getaddresses


logger = logging.getLogger(__name__)


def email_provider(settings):
    provider = settings.EMAIL_PROVIDER.strip().lower()
    if provider == "auto":
        return "ses" if settings.INTERN_HUB_SES_ENABLED else "smtp"
    if provider not in {"ses", "smtp"}:
        raise RuntimeError("Unsupported email provider")
    return provider


def email_configured(settings):
    if email_provider(settings) == "ses":
        return bool(settings.SES_FROM or settings.INTERN_HUB_SES_FROM)
    return bool(settings.MAIL_SERVER and settings.MAIL_USERNAME and settings.MAIL_PASSWORD and settings.MAIL_FROM)


def _smtp(message, recipients, *, host, port, username, password, sender, implicit_tls=False, starttls=True):
    if not (host and username and password and sender):
        raise RuntimeError("Email delivery is not configured")
    if not implicit_tls and not starttls:
        raise RuntimeError("SMTP requires TLS")
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if implicit_tls else smtplib.SMTP
    kwargs = {"timeout": 20}
    if implicit_tls:
        kwargs["context"] = context
    with smtp_class(host, port, **kwargs) as connection:
        if not implicit_tls:
            connection.ehlo()
            connection.starttls(context=context)
            connection.ehlo()
        connection.login(username, password)
        refused = connection.send_message(message, from_addr=sender, to_addrs=recipients)
    if refused:
        raise RuntimeError("Email provider rejected one or more recipients; reconcile before retry")
    return str(message["Message-ID"])


def send_message(message: EmailMessage, recipients=None, *, source=None, settings):
    """Send MIME mail including attachments through SES API, SES SMTP or SMTP."""
    recipients = list(dict.fromkeys(recipients or [address for _, address in getaddresses(
        message.get_all("To", []) + message.get_all("Cc", []) + message.get_all("Bcc", []))]))
    if not recipients or any(not address or "@" not in address or "\n" in address or "\r" in address for address in recipients):
        raise ValueError("Valid email recipients are required")
    if len(recipients) > 50:
        raise ValueError("Send at most 50 recipients per message")
    if "Bcc" in message:
        del message["Bcc"]
    provider = email_provider(settings)
    sender = (settings.SES_FROM or settings.INTERN_HUB_SES_FROM) if provider == "ses" else settings.MAIL_FROM
    source = source or formataddr((settings.SES_FROM_NAME if provider == "ses" else settings.MAIL_FROM_NAME, sender))
    if "From" in message:
        message.replace_header("From", source)
    else:
        message["From"] = source
    if "Message-ID" not in message:
        message["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    if provider == "ses":
        host = settings.SES_SMTP_SERVER or settings.INTERN_HUB_SES_SMTP_SERVER
        if host:
            if settings.SES_CONFIGURATION_SET:
                message["X-SES-CONFIGURATION-SET"] = settings.SES_CONFIGURATION_SET
            port = settings.SES_SMTP_PORT if settings.SES_SMTP_SERVER else settings.INTERN_HUB_SES_SMTP_PORT
            return _smtp(message, recipients, host=host, port=port,
                username=settings.SES_SMTP_USERNAME or settings.INTERN_HUB_SES_SMTP_USERNAME,
                password=settings.SES_SMTP_PASSWORD or settings.INTERN_HUB_SES_SMTP_PASSWORD,
                sender=getaddresses([source])[0][1], implicit_tls=port in (465, 2465))
        import boto3
        from botocore.config import Config
        client = boto3.client("ses", region_name=settings.SES_REGION or settings.INTERN_HUB_SES_REGION,
            config=Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1}))
        payload = dict(Source=source, Destinations=recipients, RawMessage={"Data": message.as_bytes()})
        if settings.SES_CONFIGURATION_SET:
            payload["ConfigurationSetName"] = settings.SES_CONFIGURATION_SET
        return client.send_raw_email(**payload)["MessageId"]
    return _smtp(message, recipients, host=settings.MAIL_SERVER, port=settings.MAIL_PORT,
        username=settings.MAIL_USERNAME, password=settings.MAIL_PASSWORD, sender=settings.MAIL_FROM,
        implicit_tls=settings.MAIL_SSL_TLS, starttls=settings.MAIL_STARTTLS)
