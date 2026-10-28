import logging
import json
import os
import smtplib
from email.message import EmailMessage

from app.models import IntegrationSetting


def send_email(to, subject, body_html, attachment_bytes=None, attachment_name=None):
    config = smtp_config()
    host = config.get("host")
    port = int(config.get("port") or 587)
    user = config.get("user")
    password = config.get("password")
    sender = config.get("sender") or user
    ses_enabled = os.environ.get("EMAIL_PROVIDER") == "ses" or os.environ.get("INTERN_HUB_SES_ENABLED", "false").lower() == "true"
    if not ses_enabled and (not host or not sender):
        logging.info("Email not configured")
        return False

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content("This email contains an HTML report. Please use an HTML-capable client.")
    message.add_alternative(body_html, subtype="html")
    if attachment_bytes and attachment_name:
        payload = attachment_bytes.getvalue() if hasattr(attachment_bytes, "getvalue") else attachment_bytes
        maintype, subtype = ("application", "pdf") if attachment_name.lower().endswith(".pdf") else ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=attachment_name)

    # The standalone legacy app loads the same dependency-free suite transport.
    from pathlib import Path
    from importlib.util import spec_from_file_location, module_from_spec
    from types import SimpleNamespace
    module_path = Path(__file__).resolve().parents[6] / "suite_email_transport.py"
    spec = spec_from_file_location("businesssuite_email_transport", module_path)
    transport = module_from_spec(spec)
    spec.loader.exec_module(transport)
    values = dict(MAIL_SERVER=host, MAIL_PORT=port, MAIL_USERNAME=user or "", MAIL_PASSWORD=password or "",
        MAIL_FROM=sender, MAIL_FROM_NAME="Business Suite", MAIL_STARTTLS=True, MAIL_SSL_TLS=False,
        EMAIL_PROVIDER=os.environ.get("EMAIL_PROVIDER", "auto"),
        INTERN_HUB_SES_ENABLED=os.environ.get("INTERN_HUB_SES_ENABLED", "false").lower() == "true")
    for key, default in {"SES_REGION":"", "SES_FROM":"", "SES_FROM_NAME":"Business Suite",
        "SES_CONFIGURATION_SET":"", "SES_SMTP_SERVER":"", "SES_SMTP_USERNAME":"", "SES_SMTP_PASSWORD":"",
        "INTERN_HUB_SES_REGION":"ap-south-1", "INTERN_HUB_SES_FROM":"noreply@indianservers.com",
        "INTERN_HUB_SES_SMTP_SERVER":"", "INTERN_HUB_SES_SMTP_USERNAME":"", "INTERN_HUB_SES_SMTP_PASSWORD":""}.items():
        values[key] = os.environ.get(key, default)
    for key in ("SES_SMTP_PORT", "INTERN_HUB_SES_SMTP_PORT"):
        values[key] = int(os.environ.get(key, "587"))
    transport.send_message(message, settings=SimpleNamespace(**values))

    return True


def smtp_config():
    config = {
        "host": os.environ.get("SMTP_HOST"),
        "port": os.environ.get("SMTP_PORT") or 587,
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "sender": os.environ.get("SMTP_FROM"),
    }
    try:
        setting = IntegrationSetting.query.filter_by(provider_type="email", is_active=True).order_by(IntegrationSetting.id.desc()).first()
        if setting and setting.config_json:
            data = json.loads(setting.config_json)
            config.update({
                "host": data.get("host") or data.get("SMTP_HOST") or config["host"],
                "port": data.get("port") or data.get("SMTP_PORT") or config["port"],
                "user": data.get("user") or data.get("SMTP_USER") or config["user"],
                "password": data.get("password") or data.get("SMTP_PASS") or config["password"],
                "sender": data.get("sender") or data.get("from") or data.get("SMTP_FROM") or config["sender"],
            })
    except Exception:
        logging.exception("Unable to read SMTP integration settings")
    return config
