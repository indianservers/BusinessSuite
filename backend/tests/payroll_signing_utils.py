"""Test-only DSC material. No production private keys are read or generated."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def signing_material(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Payroll test signatory")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True).sign(key, hashes.SHA256()))
    from cryptography.hazmat.primitives.serialization.pkcs12 import serialize_key_and_certificates
    pfx = tmp_path / "test-signatory.p12"
    pfx.write_bytes(serialize_key_and_certificates(b"test", key, cert, None, serialization.NoEncryption()))
    return pfx, cert.public_bytes(serialization.Encoding.PEM)


def sign_pdf(data, pfx):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    signer = signers.SimpleSigner.load_pkcs12(str(pfx))
    out = BytesIO()
    signers.sign_pdf(IncrementalPdfFileWriter(BytesIO(data)), signers.PdfSignatureMetadata(field_name="EmployerDSC"), signer=signer, output=out)
    return out.getvalue()
