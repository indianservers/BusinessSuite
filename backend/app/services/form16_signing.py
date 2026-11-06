"""Validate uploaded DSC-signed PDFs without fetching signer-controlled URLs."""
from io import BytesIO
import hashlib
from fastapi import HTTPException


def certificates(pem_bytes):
    from asn1crypto import pem, x509
    try:
        result = [x509.Certificate.load(data) for kind, _, data in pem.unarmor(pem_bytes, multiple=True) if kind == "CERTIFICATE"]
    except Exception:
        result = []
    if not result:
        raise HTTPException(422, "Upload PEM-encoded public signing certificates; never upload private keys")
    return result


def verify_signed_pdf(data, original, trust_pem):
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    if not data.startswith(original):
        raise HTTPException(422, "Sign the downloaded combined PDF without rewriting or replacing its original pages")
    roots = certificates(trust_pem.encode())
    try:
        reader = PdfFileReader(BytesIO(data))
        if not reader.embedded_signatures:
            raise ValueError("No signature")
        valid = []
        for signature in reader.embedded_signatures:
            result = validate_pdf_signature(signature, signer_validation_context=ValidationContext(trust_roots=roots, allow_fetching=False))
            if result.bottom_line:
                valid.append({"signer": result.signing_cert.subject.human_friendly,
                    "certificate_sha256": hashlib.sha256(result.signing_cert.dump()).hexdigest(),
                    "intact": result.intact, "valid": result.valid, "trusted": result.trusted})
        if not valid:
            raise ValueError("Invalid or untrusted signature")
    except Exception:
        raise HTTPException(422, "PDF signature is missing, invalid, altered, expired or not trusted by the configured company signing certificates") from None
    return {"signatures": valid, "sha256": hashlib.sha256(data).hexdigest(),
            "validation": "Cryptographic integrity and configured certificate trust verified; no online revocation lookup performed"}
