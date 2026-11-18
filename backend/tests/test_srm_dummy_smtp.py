"""Real queued collection email over TLS to a loopback-only dummy SMTP server."""
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
import ipaddress
import socketserver
import ssl
import threading
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from app.core.config import settings
from app.apps.communication import customer_service as service
from app.apps.communication.customer_models import CustomerDelivery
from app.apps.srm.models import SRMCollectionReminder
from app.models.email_outbox import EmailOutbox
from app.services.email_dispatch import drain_outbox
from tests.test_unified_collection_controls import issued_invoice


@pytest.fixture
def dummy_smtp(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
        .not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False).sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path/'cert.pem', tmp_path/'key.pem'
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(str(cert_file), str(key_file))
    client_context = ssl.create_default_context(cafile=str(cert_file))
    state = {'messages': [], 'reject_once': False, 'connections': 0}

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            state['connections'] += 1
            self.wfile.write(b'220 localhost dummy SMTP\r\n')
            for raw in self.rfile:
                command = raw.split(b' ', 1)[0].strip().upper()
                if command in (b'EHLO', b'HELO'):
                    self.wfile.write(b'250-localhost\r\n250 AUTH PLAIN\r\n')
                elif command == b'AUTH':
                    self.wfile.write(b'235 Authentication accepted\r\n')
                elif command == b'DATA':
                    self.wfile.write(b'354 End with dot\r\n')
                    lines = []
                    for line in self.rfile:
                        if line == b'.\r\n':
                            break
                        lines.append(line[1:] if line.startswith(b'..') else line)
                    if state['reject_once']:
                        state['reject_once'] = False
                        self.wfile.write(b'451 Temporary dummy rejection\r\n')
                    else:
                        state['messages'].append(b''.join(lines))
                        self.wfile.write(b'250 Message accepted locally\r\n')
                elif command == b'QUIT':
                    self.wfile.write(b'221 Goodbye\r\n')
                    break
                else:
                    self.wfile.write(b'250 OK\r\n')

    server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for field, value in {'EMAIL_PROVIDER': 'smtp', 'EMAIL_SITE': '', 'MAIL_SERVER': '127.0.0.1',
        'MAIL_PORT': server.server_address[1], 'MAIL_USERNAME': 'dummy', 'MAIL_PASSWORD': 'dummy',
        'MAIL_FROM': 'srm-dummy@example.invalid', 'MAIL_SSL_TLS': True, 'MAIL_STARTTLS': False}.items():
        monkeypatch.setattr(settings, field, value)
    monkeypatch.setattr(ssl, 'create_default_context', lambda *args, **kwargs: client_context)
    monkeypatch.setattr(service, 'now', lambda: datetime(2030, 1, 7, 12, tzinfo=timezone.utc))
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('reject_once', [False, True])
def test_collection_reminder_reaches_dummy_tls_smtp_once(client, db, superuser_headers, dummy_smtp, reject_once):
    invoice = issued_invoice(client, db, superuser_headers)
    # Invoice approval also queues internal fixture notifications. This test
    # measures the customer reminder; keep those separate jobs out of its drain.
    db.query(EmailOutbox).filter_by(status='queued').update({'status': 'cancelled'})
    db.commit()
    recipient = client.post('/api/v1/communication/customers/recipients', headers=superuser_headers, json={
        'name': 'Dummy billing recipient', 'email': 'billing@example.com', 'role': 'billing',
        'timezone': 'UTC', 'consent_source': 'Dummy integration test', 'preferences': {'email.transactional': True}})
    assert recipient.status_code == 201, recipient.text
    response = client.post(f'/api/v1/communication/customers/recipients/{recipient.json()["id"]}/bindings',
        headers=superuser_headers, json={'source_type': 'invoice', 'source_id': invoice['id']})
    assert response.status_code == 201, response.text
    response = client.post('/api/v1/srm/collections/reminders/send', headers=superuser_headers, json={'invoice_id': invoice['id']})
    assert response.status_code == 200, response.text
    dummy_smtp['reject_once'] = reject_once
    service.process_customer_communications(db)
    assert db.query(EmailOutbox).filter_by(module='customer_communication').count() == 1
    drain_outbox(db)
    service.sync_delivery(db, db.query(CustomerDelivery).one())
    db.commit()
    if reject_once:
        row = db.query(CustomerDelivery).one()
        assert row.status == 'retry_wait' and not dummy_smtp['messages']
        response = client.post(f'/api/v1/communication/customers/deliveries/{row.id}/retry', headers=superuser_headers)
        # A temporary rejection already has a worker retry scheduled. A second
        # manual retry must not create another delivery or reset that attempt.
        assert response.status_code == 409, response.text
        service.process_customer_communications(db)
        drain_outbox(db)
        service.process_customer_communications(db)
    assert len(dummy_smtp['messages']) == 1
    message = BytesParser(policy=policy.default).parsebytes(dummy_smtp['messages'][0])
    assert message['To'] == 'billing@example.com'
    assert invoice['invoice_number'] in message.get_content()
    assert db.query(EmailOutbox).filter_by(module='customer_communication').one().status == 'accepted'
    assert db.query(CustomerDelivery).one().status == 'accepted'
    assert db.query(SRMCollectionReminder).one().status == 'accepted'
    service.process_customer_communications(db)
    drain_outbox(db)
    assert len(dummy_smtp['messages']) == 1
