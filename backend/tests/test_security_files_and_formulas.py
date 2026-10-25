from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zipfile import ZipFile
import hashlib
import hmac

import pytest
from fastapi import HTTPException, UploadFile
from app.core.config import settings
from app.core.formula_limits import bounded_formula_tree
from app.core.storage import signed_file_url, blob_token_path, normalize_upload_references
from app.apps.interns_hub.application_documents import upload_document
from app.apps.interns_hub.management_models import ApplicationDocument


@pytest.mark.parametrize('expression', ['10**1000000000', "'x'*1000000000", '1+'*1001, '9'*100, '['*1001])
def test_resource_exhaustion_formulas_are_rejected_without_evaluation(expression):
    with pytest.raises(HTTPException) as exc:
        bounded_formula_tree(expression)
    assert exc.value.status_code == 400


def test_financial_formula_still_computes():
    from decimal import Decimal
    from app.api.v1.payroll import _safe_formula_value
    assert _safe_formula_value('round(BASIC * 40 / 100, 2)', {'BASIC':Decimal('1000')}, 'HRA') == Decimal('400.00')


@pytest.mark.parametrize('value',['synthetic',[1],{'key':'synthetic'}])
def test_formula_variables_cannot_bypass_resource_limits(value):
    from app.apps.customization.services.validation import evaluate_formula
    with pytest.raises(HTTPException) as exc:
        evaluate_formula('value * 1000000000000000',{'value':value})
    assert exc.value.status_code==400


def test_api_errors_receive_private_security_headers(client):
    response=client.get('/api/v1/auth/me')
    assert response.status_code == 403
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['cache-control']=='private, no-store'
    assert response.headers['referrer-policy']=='no-referrer'


def test_local_download_requires_valid_expiring_capability(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings,'UPLOAD_DIR',str(tmp_path))
    monkeypatch.setattr(settings,'STORAGE_BACKEND','local')
    target=tmp_path/'employee_docs'/'canary.txt'; target.parent.mkdir(); target.write_text('SYNTHETIC')
    url=signed_file_url(str(target)); token=parse_qs(urlsplit(url).query)['token'][0]
    assert Path(blob_token_path(token))==target
    assert normalize_upload_references(url)=='/uploads/employee_docs/canary.txt'
    result=client.get('/api/v1/files/blob',params={'token':token})
    assert result.status_code==200 and result.text=='SYNTHETIC'
    assert result.headers['content-disposition'].startswith('attachment')
    assert client.get('/api/v1/files/blob',params={'token':token+'tampered'}).status_code==403


def test_docx_traversal_archive_is_rejected(db):
    body=BytesIO()
    with ZipFile(body,'w') as archive:
        for name in ('word/document.xml','[Content_Types].xml','../outside.txt'):
            archive.writestr(name,'synthetic')
    file=UploadFile(filename='synthetic.docx',file=BytesIO(body.getvalue()))
    with pytest.raises(HTTPException) as exc:
        upload_document(db,file,'Academic','synthetic-source')
    assert exc.value.status_code==422


def test_public_upload_quota_is_persisted_not_process_local(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings,'UPLOAD_DIR',str(tmp_path))
    source='synthetic-quota-source'
    digest=hmac.new(settings.SECRET_KEY.encode(),source.encode(),hashlib.sha256).hexdigest()
    for index in range(30):
        db.add(ApplicationDocument(uploader_hash=digest,claim_hash=f'{index:064x}',name='Synthetic.pdf',category='Identity',storage_path='unused',mime_type='application/pdf',size=1))
    db.commit()
    file=UploadFile(filename='synthetic.pdf',file=BytesIO(b'%PDF-1.4 synthetic'))
    with pytest.raises(HTTPException) as exc:
        upload_document(db,file,'Identity',source)
    assert exc.value.status_code==429
    assert not list(tmp_path.rglob('*.pdf'))


def test_client_cannot_turn_arbitrary_storage_path_into_download_link(client, superuser_headers):
    response=client.post('/api/v1/documents/certificates/exports',headers=superuser_headers,
                         params={'output_file_url':'/uploads/employee_docs/other-company-canary.pdf'})
    assert response.status_code==422
    assert 'upload service' in response.json()['detail']
    response=client.post('/api/v1/documents/generated',headers=superuser_headers,
                         json={'file_url':'/uploads/employee_docs/other-company-canary.pdf'})
    assert response.status_code==422
    assert 'upload service' in response.json()['detail']


@pytest.mark.parametrize('path',['/uploads/avatars/../employee_docs/canary.pdf','/uploads/avatars/..\\employee_docs/canary.pdf'])
def test_public_asset_prefix_cannot_bypass_private_path_guard(client,superuser_headers,path):
    response=client.post('/api/v1/documents/certificates/exports',headers=superuser_headers,params={'output_file_url':path})
    assert response.status_code==422


def test_forged_s3_signature_is_never_promoted_to_trusted_storage_path(monkeypatch):
    monkeypatch.setattr(settings,'STORAGE_BACKEND','s3')
    forged='https://synthetic-storage.invalid/bucket/employee_docs/canary.pdf?X-Amz-Signature=not-a-signature'
    assert normalize_upload_references(forged)==forged


def test_expired_file_capability_cannot_be_resaved(client,superuser_headers):
    import jwt
    token=jwt.encode({'path':'employee_docs/canary.pdf','purpose':'blob-download','aud':'private-file','exp':1},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
    response=client.post('/api/v1/documents/generated',headers=superuser_headers,
                        json={'file_url':settings.BACKEND_PUBLIC_URL+'/api/v1/files/blob?token='+token})
    assert response.status_code==403
    assert response.json()['detail']=='Invalid or expired file reference'
