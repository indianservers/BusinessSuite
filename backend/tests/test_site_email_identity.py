from types import SimpleNamespace
from email.message import EmailMessage
from unittest.mock import patch
import pytest
import suite_email_transport as transport


def config(site='', url='https://app.indianservers.com'):
    return SimpleNamespace(EMAIL_SITE=site, FRONTEND_PUBLIC_URL=url, EMAIL_PROVIDER='smtp',
        MAIL_FROM='noreply@indianservers.com', MAIL_FROM_NAME='Indian Servers', MAIL_SERVER='smtp.test',
        MAIL_PORT=587, MAIL_USERNAME='mock', MAIL_PASSWORD='mock', MAIL_SSL_TLS=False, MAIL_STARTTLS=True)


@pytest.mark.parametrize('site,name', [('bestschool','BestSchool'), ('besterp','BestERP')])
def test_platform_identity_and_html(site, name):
    message = EmailMessage(); message['To'] = 'owner@example.com'; message.set_content('<unsafe>')
    message['Reply-To'] = 'support@example.com'
    with patch.object(transport, '_smtp', return_value='accepted') as smtp:
        assert transport.send_message(message, settings=config(site, 'https://www.'+site+'.app')) == 'accepted'
    assert str(message['From']) == f'{name} <info@{site}.app>'
    assert smtp.call_args.kwargs['sender'] == f'info@{site}.app'
    assert message['Reply-To'] == 'support@example.com'
    assert '&lt;unsafe&gt;' in message.get_body(preferencelist=('html',)).get_content()
    assert 'https://'+site+'.app' in message.get_body(preferencelist=('html',)).get_content()


def test_unrelated_sender_preserved():
    message = EmailMessage(); message['To'] = 'owner@example.com'; message.set_content('Body')
    with patch.object(transport, '_smtp', return_value='accepted'):
        transport.send_message(message, settings=config())
    assert str(message['From']) == 'Indian Servers <noreply@indianservers.com>'


def test_override_and_cross_site_configuration_rejected():
    message = EmailMessage(); message['To'] = 'owner@example.com'; message.set_content('Body')
    with patch.object(transport, '_smtp') as smtp:
        with pytest.raises(ValueError):
            transport.send_message(message, source='info@bestschool.app', settings=config('besterp','https://besterp.app'))
        with pytest.raises(RuntimeError):
            transport.send_message(message, settings=config('besterp','https://bestschool.app'))
        smtp.assert_not_called()


def test_provider_error_surfaces():
    message = EmailMessage(); message['To'] = 'owner@example.com'; message.set_content('Body')
    with patch.object(transport, '_smtp', side_effect=RuntimeError('rejected')):
        with pytest.raises(RuntimeError, match='rejected'):
            transport.send_message(message, settings=config('besterp','https://besterp.app'))
