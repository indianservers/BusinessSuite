"""Private conversation attachments, parsed on the server; never public storage.

Existing AssistantMessage storage binds the original bytes and extracted context
to the same owner, company, branch and workspace as the conversation.
"""
import base64
import csv
import hashlib
import io
import re
import zipfile
from datetime import datetime,date
from pathlib import PurePosixPath
from uuid import uuid4
from fastapi import HTTPException
from app.ai_operator.assistant_models import AssistantMessage
from app.ai_operator import suite_conversations as chats

MAX_BYTES=5_000_000
TOOL='suite.attachment'
FORMATS={'.xlsx','.csv','.txt','.docx','.pdf'}


def parse(content,name):
    suffix=PurePosixPath(name).suffix.lower()
    if suffix not in FORMATS:raise HTTPException(422,'Use XLSX, CSV, TXT, DOCX or text-based PDF. Macros and legacy Office formats are not supported.')
    if not content or len(content)>MAX_BYTES:raise HTTPException(413,'Use a nonempty file of at most 5 MB')
    rows=[];notes=[];text=''
    try:
        if suffix in {'.xlsx','.docx'}:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries=archive.infolist()
                if len(entries)>2000 or sum(v.file_size for v in entries)>25_000_000:
                    raise HTTPException(413,'The expanded document exceeds the parsing limit')
                if any('vbaproject' in v.filename.casefold() for v in entries):raise HTTPException(422,'Macro-enabled content is not accepted')
        if suffix=='.xlsx':
            from openpyxl import load_workbook
            book=load_workbook(io.BytesIO(content),read_only=True,data_only=False,keep_links=False)
            try:
                sheet=book.worksheets[0]
                if len(book.worksheets)>1:notes.append('Only the first sheet is included; upload other sheets separately.')
                for values in sheet.iter_rows(max_row=202,max_col=31,values_only=True):
                    row=[]
                    for value in values:
                        if isinstance(value,str) and value.startswith('='):
                            notes.append('Formula cells are omitted; formulas are never evaluated.');value=''
                        if isinstance(value,datetime):value=value.date().isoformat()
                        elif isinstance(value,date):value=value.isoformat()
                        if value is not None and len(str(value))>1000:notes.append('Long cell values are limited to 1,000 characters.')
                        row.append(str(value)[:1000] if value is not None else '')
                    while row and row[-1]=='':row.pop()
                    if any(row):rows.append(row)
            finally:book.close()
        elif suffix in {'.csv','.txt'}:
            text=content.decode('utf-8-sig')
            if '\x00' in text:raise ValueError('Binary text')
            if suffix=='.csv':
                for i,row in enumerate(csv.reader(io.StringIO(text))):
                    if i>=202:notes.append('Table preview is limited to 200 data rows.');break
                    if any(len(v)>1000 for v in row):notes.append('Long cell values are limited to 1,000 characters.')
                    rows.append([v[:1000] for v in row[:31]])
        elif suffix=='.docx':
            from docx import Document
            doc=Document(io.BytesIO(content))
            text='\n'.join(p.text for p in doc.paragraphs)[:30000]
            for table in doc.tables[:3]:
                for row in table.rows[:201]:rows.append([c.text[:1000] for c in row.cells[:30]])
        else:
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(content))
            if reader.is_encrypted:raise HTTPException(422,'Use an unencrypted PDF')
            parts=[]
            for page in reader.pages[:20]:
                parts.append((page.extract_text() or '')[:10000])
                if sum(map(len,parts))>=30000:break
            text='\n'.join(parts)
            if len(reader.pages)>20:notes.append('Only the first 20 PDF pages are included.')
        if rows:
            if len(rows)>201 or any(len(r)>30 for r in rows):notes.append('Table context is limited to 200 data rows and 30 columns.')
            rows=[r[:30] for r in rows[:201]]
            if not text:text='\n'.join(' | '.join(r) for r in rows)
        if len(text)>30000:notes.append('Text context is limited to 30,000 characters.')
        text=text[:30000]
        if not text.strip():raise HTTPException(422,'No readable text was found. Scanned images need OCR before upload.')
    except HTTPException:raise
    except Exception:raise HTTPException(422,'The file could not be parsed. Check its format and use UTF-8 for CSV/TXT.') from None
    return {'text':text,'rows':rows,'notes':list(dict.fromkeys(notes))}


def public(row):
    a=row.arguments
    return {'id':row.id,'name':a['name'],'size':a['size'],'format':a['format'],'sha256':a['sha256'],
        'preview':a['preview'],'row_count':a['row_count'],'notes':a['notes'],'excerpt':a['excerpt'],'created_at':row.created_at}


def owned(db,user,conversation_id,ident):
    chats.owned(db,user,conversation_id)
    row=db.query(AssistantMessage).filter_by(id=ident,conversation_id=conversation_id,tool=TOOL,status='stored').first()
    if not row:raise HTTPException(404,'Attachment not found')
    from app.ai_agents.security import verify
    verify(db,user,row.security_context,history=True)
    return row


def listing(db,user,conversation_id):
    chats.owned(db,user,conversation_id)
    values=db.query(AssistantMessage).filter_by(conversation_id=conversation_id,tool=TOOL,status='stored').order_by(AssistantMessage.id).limit(8).all()
    return [public(owned(db,user,conversation_id,r.id)) for r in values]


def store(db,user,conversation_id,filename,content):
    chat=chats.owned(db,user,conversation_id)
    # Lock the conversation briefly to enforce per-conversation storage quotas.
    from app.ai_operator.assistant_models import AssistantConversation
    db.query(AssistantConversation).filter_by(id=chat.id).with_for_update().one()
    existing=listing(db,user,conversation_id)
    if not content or len(content)>MAX_BYTES:raise HTTPException(413,'Use a nonempty file of at most 5 MB')
    name=PurePosixPath((filename or 'upload').replace('\\','/')).name[:160]
    name=re.sub(r'[\x00-\x1f\x7f]','',name) or 'upload'
    sha=hashlib.sha256(content).hexdigest()
    for old in existing:
        if old['sha256']==sha and old['format']==PurePosixPath(name).suffix.lower():return old
    if len(existing)>=8 or sum(r['size'] for r in existing)+len(content)>20_000_000:
        raise HTTPException(413,'Limit eight attachments and 20 MB per conversation; remove an old file first')
    extracted=parse(content,name)
    row=AssistantMessage(conversation_id=chat.id,request_key=str(uuid4()),request_hash=sha,prompt='Private uploaded context',tool=TOOL,
        arguments={'name':name,'format':PurePosixPath(name).suffix.lower(),'sha256':sha,'size':len(content),
            'preview':extracted['rows'][:9],'row_count':max(0,len(extracted['rows'])-1),'notes':extracted['notes'],'excerpt':extracted['text'][:2000]},
        status='stored',result={**extracted,'content_b64':base64.b64encode(content).decode('ascii')})
    db.add(row);db.commit();db.refresh(row)
    return public(row)


def context(db,user,conversation_id,ids):
    if ids and not conversation_id:raise HTTPException(422,'Uploads require their original conversation')
    result=[]
    for ident in dict.fromkeys(ids):
        row=owned(db,user,conversation_id,ident)
        result.append({'id':f'upload:{row.id}','tool':'suite.attachment','record_id':row.id,'label':row.arguments['name'],
            'href':f'#bot-attachment-{row.id}','text':row.result['text'],'notes':row.arguments['notes']})
    return result


def spreadsheet_plan(row,request_key):
    """An explicit user request turns table rows into a reviewed local draft."""
    rows=(row.result or {}).get('rows') or []
    if len(rows)<2:raise HTTPException(422,'Use a table with module and title headers plus at least one data row')
    headers=[re.sub(r'\s+','_',v.strip().casefold()) for v in rows[0]]
    if len(set(headers))!=len(headers):raise HTTPException(422,'Use unique column headers')
    if not {'module','title'}<=set(headers):raise HTTPException(422,'Required columns: module, title. Optional: project_id, priority, due_date, description.')
    if len(rows)-1>8 or row.arguments['notes']:raise HTTPException(422,'For action drafts, upload a complete first sheet with at most eight rows and no omitted formulas or truncated content')
    allowed={'module','title','project_id','priority','due_date','description'}
    if set(headers)-allowed:raise HTTPException(422,'Remove unsupported columns before creating action drafts')
    steps=[]
    for index,values in enumerate(rows[1:],1):
        record=dict(zip(headers,values));module=record.get('module','').strip().upper();title=record.get('title','').strip()
        if module not in {'CRM','PMS','HRMS'} or not title:raise HTTPException(422,f'Row {index}: use CRM/PMS/HRMS and a nonempty title')
        payload={'title':title}
        for key in ('priority','due_date','description'):
            if record.get(key):payload[key]=record[key]
        if module=='HRMS':
            if record.get('due_date'):raise HTTPException(422,'HR tickets do not accept due_date in this template')
            payload={'subject':title,'description':record.get('description') or title,'priority':record.get('priority') or 'Medium'}
        step={'tool':{'CRM':'crm.create_task','PMS':'pms.create_task','HRMS':'hrms.create_ticket'}[module],'payload':payload,'depends_on':[index-1] if index>1 else []}
        if module=='PMS':
            value=record.get('project_id','')
            if not re.fullmatch(r'[1-9]\d*',value):raise HTTPException(422,f'Row {index}: PMS needs a positive project_id')
            step['record_id']=int(value);payload['task_key']=f'AI-{request_key.replace("-","")[:12]}-{index}'
        steps.append(step)
    return {'summary':'Review the actions extracted from your uploaded table. Uploading alone created no business records.','steps':steps}
