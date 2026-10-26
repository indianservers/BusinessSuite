from unittest.mock import MagicMock
import pytest
from app.core import email


@pytest.fixture
def smtp(monkeypatch):
    for key, value in {"MAIL_SERVER": "smtp.example.test", "MAIL_PORT": 587, "MAIL_USERNAME": "test-user", "MAIL_PASSWORD": "test-secret", "MAIL_FROM": "noreply@example.test", "MAIL_FROM_NAME": "DSB Chartered", "MAIL_STARTTLS": True, "MAIL_SSL_TLS": False}.items():
        monkeypatch.setattr(email.settings, key, value)
    transport = MagicMock()
    transport.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr(email.smtplib, "SMTP", transport)
    return transport.return_value.__enter__.return_value


def test_transactional_email_uses_tls_and_explicit_sender(smtp):
    email.send_email("recipient@example.test", "Password reset", "Secret reset link")
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("test-user", "test-secret")
    args = smtp.send_message.call_args
    assert args.kwargs == {"from_addr": "noreply@example.test", "to_addrs": ["recipient@example.test"]}
    assert str(args.args[0]["From"]) == "DSB Chartered <noreply@example.test>"
    assert "Secret reset link" in args.args[0].get_content()


def test_rejected_recipient_is_not_reported_success(smtp):
    smtp.send_message.return_value = {"recipient@example.test": (550, b"rejected")}
    with pytest.raises(RuntimeError, match="rejected"):
        email.send_email("recipient@example.test", "Test", "Body")


def test_missing_production_credentials_fail(monkeypatch):
    monkeypatch.setattr(email.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(email.settings, "MAIL_PASSWORD", "")
    with pytest.raises(RuntimeError, match="not configured"):
        email.send_email("recipient@example.test", "Test", "Body")


def test_plaintext_smtp_is_rejected(smtp, monkeypatch):
    monkeypatch.setattr(email.settings, "MAIL_STARTTLS", False)
    with pytest.raises(RuntimeError, match="requires TLS"):
        email.send_email("recipient@example.test", "Test", "Body")
    smtp.login.assert_not_called()
