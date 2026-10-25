"""Private, bounded applicant uploads. Claim tokens cannot be guessed from file IDs."""
import hashlib
import io
import zipfile
import hmac
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, text
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from app.core.config import settings
from app.core.storage import persist_file
from .management_models import ApplicationDocument

LIMIT=10*1024*1024

def upload_document(db,file,category,source='unknown'):
    if category not in {'Identity','Academic','Resume','Portfolio'}:raise HTTPException(422,'Choose a document category')
    name=Path((file.filename or '').replace('\\','/')).name
    suffix=Path(name).suffix.lower()
    if suffix not in {'.pdf','.png','.jpg','.jpeg','.docx'}:raise HTTPException(422,'Use PDF, PNG, JPG or DOCX')
    body=file.file.read(LIMIT+1)
    if not body or len(body)>LIMIT:raise HTTPException(413,'Document must be between 1 byte and 10 MB')
    valid=(suffix=='.pdf' and body.startswith(b'%PDF-')) or (suffix=='.png' and body.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix in {'.jpg','.jpeg'} and body.startswith(b'\xff\xd8\xff'))
    if suffix=='.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                names=archive.namelist()
                safe_names = all(not n.startswith(('/', '\\')) and ':' not in n and '..' not in n.replace('\\','/').split('/') for n in names)
                valid=safe_names and 'word/document.xml' in names and '[Content_Types].xml' in names and len(names)<=2000 and sum(i.file_size for i in archive.infolist())<=50*1024*1024 and not any('vbaproject' in n.lower() for n in names)
        except zipfile.BadZipFile:valid=False
    if not valid:raise HTTPException(422,'Document content does not match its file type')
    source_hash=hmac.new(settings.SECRET_KEY.encode(),source.encode(),hashlib.sha256).hexdigest()
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':int(source_hash[:15],16)})
    count,size=db.query(func.count(ApplicationDocument.id),func.coalesce(func.sum(ApplicationDocument.size),0)).filter(ApplicationDocument.uploader_hash==source_hash,ApplicationDocument.created_at>=datetime.now(timezone.utc)-timedelta(days=1)).one()
    if count>=30 or size+len(body)>100*1024*1024:
        raise HTTPException(429,'Daily document upload allowance reached')
    token=uuid4().hex+uuid4().hex
    path=Path(settings.UPLOAD_DIR).resolve()/'_private'/'applications'/(uuid4().hex+suffix)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    try:
        persist_file(str(path))
        item=ApplicationDocument(uploader_hash=source_hash,claim_hash=hashlib.sha256(token.encode()).hexdigest(),name=name[:255],category=category,storage_path=str(path),mime_type={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}[suffix],size=len(body))
        db.add(item);db.commit()
    except Exception:
        db.rollback();path.unlink(missing_ok=True);raise
    finally:file.file.close()
    return {'token':token,'name':item.name,'category':category,'size':len(body),'scan_status':'Type validated; malware scanning is not configured'}

def claim(db,application,tokens):
    for token in set(tokens):
        item=db.query(ApplicationDocument).filter_by(claim_hash=hashlib.sha256(token.encode()).hexdigest()).with_for_update().first()
        if not item or item.application_id not in {None,application.id}:raise HTTPException(422,'Document token is invalid or already claimed')
        item.application_id=application.id
