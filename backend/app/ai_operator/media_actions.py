"""Reviewed, single-attempt transcription with private durable checkpoints."""
import base64
import hashlib
import re
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_current_user,get_db
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/media',tags=['Reviewed media'])
JOURNAL='suite.media.transcription'


class Transcribe(Strict):
    title:str=Field(min_length=1,max_length=160)
    conversation_id:int=Field(gt=0)
    attachment_id:int=Field(gt=0)
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    model:str=Field(min_length=1,max_length=120)
    media_policy_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Reviewed(Transcribe):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


def source(db,user,data,workspace_id):
    from app.ai_operator import suite_uploads as uploads,suite_conversations as chats
    chat=chats.owned(db,user,data.conversation_id)
    if chat.workspace_id!=workspace_id:raise HTTPException(403,'Media source is outside this workspace')
    row=uploads.owned(db,user,chat.id,data.attachment_id)
    if row.arguments.get('format')!='.wav' or (row.arguments.get('media') or {}).get('kind')!='audio':
        raise HTTPException(422,'Select a validated PCM WAV audio attachment')
    if row.arguments['sha256']!=data.sha256:raise HTTPException(409,'Media source changed since review')
    try:content=base64.b64decode(row.result['content_b64'],validate=True)
    except (ValueError,KeyError,TypeError):raise HTTPException(409,'Media source is unavailable') from None
    if hashlib.sha256(content).hexdigest()!=data.sha256:raise HTTPException(409,'Media source integrity check failed')
    from app.ai_operator.gemini_media import wav_duration
    wav_duration(content)
    return row,content


def preflight(db,user,run,step):
    from app.ai_operator.media_policy import resolve_media
    from app.ai_operator.artifacts import access,Body
    data=Transcribe.model_validate(step.payload)
    if not run or (run.result or {}).get('request',{}).get('conversation_id')!=data.conversation_id:
        raise HTTPException(403,'Transcription must retain its original conversation')
    module=step.tool.split('.')[0].upper()
    access(db,user,run.workspace_id,module,(run.result or {}).get('request',{}).get('project_id') if module=='PMS' else None)
    row,content=source(db,user,data,run.workspace_id)
    config=resolve_media(db,user,'transcription',run.workspace_id)
    if config.model!=data.model or config.media_policy_sha256!=data.media_policy_sha256:
        raise HTTPException(409,'Media provider configuration changed; prepare a fresh review')
    try:Body(title=data.title,kind='document',content='Transcript pending')
    except ValueError:raise HTTPException(422,'Transcript needs a valid document title') from None
    return row,content,config


def local_plan(db,user,data,parent=None):
    """An explicit audio request selects owned file IDs, never text extraction."""
    from app.ai_operator.suite import Plan,Step
    from app.ai_operator import suite_uploads as uploads
    text=data.text.strip()
    if parent and parent.status=='needs_clarification' and parent.plan and parent.plan.get('summary')=='Choose one private audio source.':
        selected=re.fullmatch(r'(?:audio\s+)?(?:file\s*)?#?\s*([1-9]\d{0,9})[.!? ]*',text,re.I)
        if selected:text='transcribe audio file #'+selected[1]
    match=re.fullmatch(r'(?:(CRM|PMS|HRMS)\s*:\s*)?(?:please\s+)?(?:transcribe|transcription of|create (?:a )?transcript (?:of|from))\s+(?:(?:this|the|my)\s+)?(?:audio|recording|wav)(?:\s+file)?(?:\s*#?\s*([1-9]\d{0,9}))?[.!? ]*',text,re.I)
    if not match:return None
    module=match[1].upper() if match[1] else data.module
    if module not in {'CRM','PMS','HRMS'}:
        return Plan(summary='Choose where to save the private transcript.',question='Select CRM, PMS or HRMS and ask to transcribe the audio again.',steps=[])
    data.module=module
    if not data.conversation_id:return Plan(summary='An audio file is required.',question='Upload a PCM WAV file in this conversation, then ask me to transcribe the audio.',steps=[])
    files=[f for f in uploads.listing(db,user,data.conversation_id) if f.get('format')=='.wav']
    if match[2]:files=[f for f in files if f['id']==int(match[2])]
    if len(files)!=1:
        return Plan(summary='Choose one private audio source.',question='Which audio file should I transcribe? Use “transcribe audio file #ID” after uploading a PCM WAV file.',steps=[])
    from app.ai_operator.media_policy import resolve_media
    config=resolve_media(db,user,'transcription',data.workspace_id);file=files[0]
    payload=Transcribe(title=('Transcript – '+file['name'])[:160],conversation_id=data.conversation_id,
        attachment_id=file['id'],sha256=file['sha256'],model=config.model,media_policy_sha256=config.media_policy_sha256)
    return Plan(summary=f'Review transcription of {file["name"]} using Gemini / {config.model}. The selected audio will be sent to Gemini and its output saved as a private document. Cost is unknown. No tasks or messages will be created.',
        steps=[Step(tool=f'{module.lower()}.transcribe_audio',payload=payload.model_dump())])


@router.post('/transcribe-approved')
def execute(data:Reviewed,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.agent_connectors import reviewed_run
    from app.ai_operator.assistant_models import AssistantMessage
    from app.ai_agents.security import verify
    from app.ai_operator import gemini_media,artifacts
    from app.ai_operator.prompt_registry import render
    _,prompt_manifest=render('media_transcription',gemini_media.Transcript.model_json_schema())
    run,step=reviewed_run(db,user,request,data,Transcribe,'transcribe_audio')
    row,content,config=preflight(db,user,run,step)
    module=step.tool.split('.')[0].upper()
    from app.ai_operator.media_journal import output
    def invoke():
        transcript,usage=gemini_media.transcribe_wav(config,content)
        return {'transcript':transcript.model_dump()},usage
    journal=output(db,user,run,data,step,config,JOURNAL,'media_transcription',prompt_manifest,invoke)
    if journal.status=='completed':return journal.result['receipt']
    transcript=gemini_media.Transcript.model_validate(journal.result['transcript'])
    # Reauthorize source, capability, approval and module after the external call.
    run,step=reviewed_run(db,user,request,data,Transcribe,'transcribe_audio')
    preflight(db,user,run,step)
    body=artifacts.Body(title=data.title,kind='document',content=transcript.text.strip() or 'No intelligible speech was detected.').model_dump()
    citation={'id':f'upload:{row.id}','label':row.arguments['name'],'href':f'/api/v1/ai-operator/suite/conversations/{data.conversation_id}/attachments/{row.id}/download'}
    receipt=artifacts.store_revision(db,user,run,module,body,data.suite_step,provenance_extra={
        'citations':[citation],'note':'AI-generated transcript of the selected audio; verify names, dates and commitments against the recording. No business actions were inferred or executed.',
        'media':{'kind':'transcription','provider':'gemini','model':config.model,'source_sha256':data.sha256,
            'media_policy_sha256':data.media_policy_sha256,'core_prompt':journal.arguments['core_prompt'],
            'language':transcript.language,'notes':transcript.notes}})
    journal.status='completed';journal.result={**journal.result,'receipt':receipt}
    run.result={**(run.result or {}),'media_checkpoint':{'step':data.suite_step,'state':'completed'}}
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=module,action='suite.media.transcribed',
        input_json={'suite_run_id':run.id,'step':data.suite_step},output_json={'artifact_id':receipt['artifact_id'],'policy':'media-policy:'+data.media_policy_sha256},status='success')
    db.commit();return receipt


def resume_stored(db,user,run,plan_hash):
    """Resume only a durable output; an unknown provider outcome never replays."""
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    from app.ai_operator.assistant_models import AssistantMessage
    from app.ai_operator.saved_agents import enforce
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    plan=Plan.model_validate(run.plan);step=plan.steps[run.active_step-1]
    image=step.tool.endswith(('.generate_image','.edit_image'))
    imported=step.tool.endswith('.import_image')
    if not image and not imported and not step.tool.endswith('.transcribe_audio'):return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:
        raise HTTPException(409,'Review the unchanged approved media plan before resuming')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    if imported:
        from app.ai_operator.image_actions import preflight as image_preflight,confirmed
        image_preflight(db,user,run,step)
        receipt=confirmed(db,user,run,step)
        if not receipt:raise HTTPException(409,'MEDIA_OUTCOME_REQUIRES_RECONCILIATION')
        finish_step(db,run,run.active_step,step.tool,receipt)
        run.error_code=None;approval.execution_status=run.status;approval.execution_error=None
        db.commit();return True
    if image:
        from app.ai_operator.image_actions import preflight as image_preflight,JOURNAL as image_journal
        image_preflight(db,user,run,step)
    else:preflight(db,user,run,step)
    key=digest({'media_run':run.id,'step':run.active_step})
    journal=db.query(AssistantMessage).filter_by(conversation_id=step.payload['conversation_id'],request_key=key,tool=image_journal if image else JOURNAL).first()
    if not journal or journal.request_hash!=digest(step.payload) or journal.status not in {'output_stored','completed'}:
        raise HTTPException(409,'MEDIA_OUTCOME_REQUIRES_RECONCILIATION')
    verify(db,user,journal.security_context,history=True)
    if journal.status=='completed':
        from app.ai_operator import artifacts
        receipt=journal.result['receipt'];row=artifacts.owned(db,user,receipt['artifact_id'])
        artifacts.version(db,user,row,receipt['artifact_revision'])
        finish_step(db,run,run.active_step,step.tool,receipt)
    else:
        if image:
            from app.ai_operator.image_actions import validated_output
            validated_output(journal)
        else:
            from app.ai_operator.gemini_media import Transcript
            Transcript.model_validate(journal.result['transcript'])
        run.status='queued';run.active_step=None;run.lease_until=None
    run.error_code=None;approval.execution_status=run.status;approval.execution_error=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=step.tool.split('.')[0].upper(),action='suite.media.resumed',
        input_json={'suite_run_id':run.id,'plan_hash':run.plan_hash},output_json={'status':run.status,'policy':'stored-output-only'},status='success')
    db.commit();return True
