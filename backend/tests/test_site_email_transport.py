"""Provider-free tests; run python -m unittest discover -s tests -p test_site_email_transport.py."""
import unittest
from types import SimpleNamespace
from email.message import EmailMessage
from unittest.mock import patch, Mock
import smtplib
import suite_email_transport as mail


def configuration(site='besterp'):
    return SimpleNamespace(EMAIL_PROVIDER='ses', EMAIL_SITE=site,
        FRONTEND_PUBLIC_URL='https://' + (site or 'indianservers') + '.app',
        SES_FROM='noreply@indianservers.com', SES_FROM_NAME='Indian Servers',
        INTERN_HUB_SES_FROM='noreply@indianservers.com', INTERN_HUB_SES_ENABLED=True,
        SES_SMTP_SERVER='legacy.smtp.example', SES_SMTP_PORT=587,
        SES_SMTP_USERNAME='legacy-user', SES_SMTP_PASSWORD='legacy-test-password',
        INTERN_HUB_SES_SMTP_SERVER='', INTERN_HUB_SES_SMTP_PORT=587,
        INTERN_HUB_SES_SMTP_USERNAME='', INTERN_HUB_SES_SMTP_PASSWORD='',
        SES_CONFIGURATION_SET='', SITE_SES_SMTP_SERVER='email-smtp.us-east-1.amazonaws.com',
        SITE_SES_SMTP_PORT=587, SITE_SES_SMTP_USERNAME='site-user', SITE_SES_SMTP_PASSWORD='site-test-password')


def message():
    m=EmailMessage();m['To']='owner@example.com';m['Subject']='Test'
    m['From']='Untrusted <info@another-site.example>'
    m.set_content('Sign in at https://besterp.app/login')
    m.add_alternative('<p>Sign in at <a href="https://besterp.app/login">BestERP</a></p>',subtype='html')
    return m


class SiteEmailTests(unittest.TestCase):
    @patch.object(mail, '_smtp', return_value='accepted')
    def test_both_sites_and_www_use_fixed_identity(self, send):
        for site,name in [('besterp','BestERP'),('bestschool','BestSchool')]:
            for prefix in ['', 'www.']:
                cfg=configuration(site);cfg.FRONTEND_PUBLIC_URL=f'https://{prefix}{site}.app'
                m=message()
                self.assertEqual(mail.send_message(m,settings=cfg),'accepted')
                self.assertEqual(m['From'],f'{name} <info@{site}.app>')
                self.assertEqual(send.call_args.kwargs['sender'],f'info@{site}.app')
                self.assertEqual(send.call_args.kwargs['username'],'site-user')
                self.assertEqual(m.get_body(preferencelist=('html',)).get_content_type(),'text/html')
                self.assertEqual(m.get_body(preferencelist=('plain',)).get_content_type(),'text/plain')

    @patch.object(mail, '_smtp', return_value='accepted')
    def test_intern_sender_keeps_original_credentials(self, send):
        m=message();mail.send_message(m,source='Interns Hub <noreply@indianservers.com>',settings=configuration())
        self.assertEqual(m['From'],'Interns Hub <noreply@indianservers.com>')
        self.assertEqual(send.call_args.kwargs['host'],'legacy.smtp.example')
        self.assertEqual(send.call_args.kwargs['username'],'legacy-user')

    @patch.object(mail, '_smtp', return_value='accepted')
    def test_unrelated_deployment_preserved(self, send):
        m=message();mail.send_message(m,settings=configuration(''))
        self.assertEqual(m['From'],'Indian Servers <noreply@indianservers.com>')
        self.assertEqual(send.call_args.kwargs['host'],'legacy.smtp.example')

    @patch.object(mail, '_smtp')
    def test_cannot_override_sender_or_impersonate_other_site(self, send):
        for source in ['BestSchool <info@bestschool.app>','Evil <evil@example.com>', 'a@example.com, b@example.com']:
            with self.assertRaises(ValueError):mail.send_message(message(),source=source,settings=configuration())
        send.assert_not_called()

    @patch.object(mail, '_smtp')
    def test_rejects_invalid_server_identity_and_noncanonical_links(self, send):
        for site,url in [('unknown','https://besterp.app'),('besterp','http://localhost:5173'),('besterp','https://evil.example'),('besterp','https://besterp.app/evil')]:
            cfg=configuration();cfg.EMAIL_SITE=site;cfg.FRONTEND_PUBLIC_URL=url
            with self.assertRaises(RuntimeError):mail.send_message(message(),settings=cfg)
        send.assert_not_called()

    @patch.object(mail, '_smtp', side_effect=smtplib.SMTPAuthenticationError(535,b'rejected'))
    def test_provider_rejection_is_surfaced_without_retry(self, send):
        with self.assertRaises(smtplib.SMTPAuthenticationError):mail.send_message(message(),settings=configuration())
        send.assert_called_once()

    @patch.object(mail.smtplib,'SMTP')
    def test_starttls_is_required_and_certificates_validated(self, factory):
        connection=factory.return_value.__enter__.return_value
        connection.send_message.return_value={}
        m=message();m['Message-ID']='<test@example.com>'
        mail._smtp(m,['owner@example.com'],host='email-smtp.us-east-1.amazonaws.com',port=587,
            username='test-user',password='test-password',sender='info@besterp.app')
        context=connection.starttls.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,mail.ssl.CERT_REQUIRED)
        self.assertEqual([c[0] for c in connection.method_calls],['ehlo','starttls','ehlo','login','send_message'])
        factory.assert_called_once_with('email-smtp.us-east-1.amazonaws.com',587,timeout=20)

    @patch.object(mail.smtplib,'SMTP')
    def test_failed_tls_never_authenticates_or_sends(self, factory):
        connection=factory.return_value.__enter__.return_value
        connection.starttls.side_effect=smtplib.SMTPNotSupportedError('STARTTLS unavailable')
        with self.assertRaises(smtplib.SMTPNotSupportedError):
            mail._smtp(message(),['owner@example.com'],host='host',port=587,username='test',password='test',sender='info@besterp.app')
        connection.login.assert_not_called();connection.send_message.assert_not_called()

if __name__=='__main__':unittest.main()
