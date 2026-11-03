"""Business-owned SMTP transport; credentials never leave the server."""
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import ipaddress
import socket
import ssl
import smtplib
from .customer_models import CustomerEmailConnection


def connection(db, company):
    return db.query(CustomerEmailConnection).filter_by(organization_id=company).first()


def configured(db, company):
    from app.core.email import email_configured
    row = connection(db, company)
    return bool(row.active) if row else email_configured()


def public_addresses(host, port):
    addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('SMTP host must resolve only to public addresses')
    return addresses


def send(db, company, recipient, subject, body):
    from app.shared.integrations import reveal
    row = connection(db, company)
    if not row:
        from app.core.email import send_email
        return send_email(recipient, subject, body)
    if not row.active:
        raise ValueError('Business email connection is disabled')
    addresses = public_addresses(row.host, row.port)
    message = EmailMessage()
    message['From'] = formataddr((row.from_name, row.from_email))
    message['To'], message['Subject'] = recipient, subject
    message['Message-ID'] = make_msgid(domain=row.from_email.split('@')[1])
    if row.reply_to:
        message['Reply-To'] = row.reply_to
    message.set_content(body)
    # Pin the socket address, keeping the configured hostname for TLS verification.
    cls = smtplib.SMTP_SSL if row.port == 465 else smtplib.SMTP
    smtp = cls(timeout=20, **({'context': ssl.create_default_context()} if row.port == 465 else {}))
    try:
        smtp._host = row.host
        smtp._get_socket = lambda host, port, timeout: socket.create_connection((addresses[0], row.port), timeout)
        if row.port == 465:
            smtp._get_socket = lambda host, port, timeout: ssl.create_default_context().wrap_socket(
                socket.create_connection((addresses[0], row.port), timeout), server_hostname=row.host)
        code, _ = smtp.connect(row.host, row.port)
        if code != 220:
            raise smtplib.SMTPConnectError(code, 'SMTP connection rejected')
        smtp.ehlo()
        if row.port == 587:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        smtp.login(row.username, reveal(row.password_ciphertext))
        refused = smtp.send_message(message, from_addr=row.from_email, to_addrs=[recipient])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        return str(message['Message-ID'])
    finally:
        smtp.close()
