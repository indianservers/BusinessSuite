"""Private agent document bindings over existing uploads; every use reauthorizes."""
from fastapi import HTTPException
from pydantic import Field
from app.ai_operator.suite_tools import Strict


class KnowledgeFile(Strict):
    conversation_id:int=Field(gt=0)
    attachment_id:int=Field(gt=0)
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


def sources(db,user,bindings,workspace_id):
    from app.ai_operator import suite_uploads as uploads,suite_conversations as chats
    result=[]
    for binding in bindings:
        ref=binding if isinstance(binding,KnowledgeFile) else KnowledgeFile.model_validate(binding)
        chat=chats.owned(db,user,ref.conversation_id)
        if chat.workspace_id!=workspace_id:raise HTTPException(403,'Agent knowledge must use the same workspace')
        row=uploads.owned(db,user,chat.id,ref.attachment_id)
        if row.arguments['sha256']!=ref.sha256:raise HTTPException(409,'Agent knowledge source changed; select it again')
        result.append((chat,row))
    return result


def context(db,user,profile):
    result=[]
    for chat,row in sources(db,user,profile.get('knowledge_files',[]),profile['workspace_id']):
        result.append({'id':f'upload:{row.id}','tool':'suite.attachment','record_id':row.id,
            'label':row.arguments['name'],'href':f'/api/v1/ai-operator/suite/conversations/{chat.id}/attachments/{row.id}/download',
            'text':row.result['text'],'notes':row.arguments['notes'],'agent_knowledge':True})
    return result


def chunks(db,user,profile):
    files=[];values=[]
    for chat,row in sources(db,user,profile.get('knowledge_files',[]),profile['workspace_id']):
        file={'id':row.id,'name':row.arguments['name']};files.append(file)
        text=row.result['text']
        for start in range(0,len(text),900):
            part=text[start:start+1200]
            if part.strip():values.append({'text':part,'source':{'id':f'upload:{row.id}:{start}',
                'file_id':row.id,'kind':'upload','agent_knowledge':True,'label':file['name'],
                'start':start,'end':start+len(part),
                'href':f'/api/v1/ai-operator/suite/conversations/{chat.id}/attachments/{row.id}/download'}})
    return files,values


def available(db,user,workspace_id):
    from app.ai_operator import suite_conversations as chats,suite_uploads as uploads
    from app.ai_operator.assistant_models import AssistantMessage
    from app.ai_agents.security import verify
    result=[]
    conversations={chat['id']:chat for chat in chats.listing(db,user,workspace_id)}
    if not conversations:return result
    rows=db.query(AssistantMessage.id,AssistantMessage.conversation_id,AssistantMessage.arguments,
        AssistantMessage.security_context).filter(AssistantMessage.conversation_id.in_(list(conversations)),
        AssistantMessage.tool==uploads.TOOL,AssistantMessage.status=='stored').order_by(AssistantMessage.id.desc()).limit(100)
    for row in rows:
        try:verify(db,user,row.security_context,history=True)
        except HTTPException:continue
        file=row.arguments;chat=conversations[row.conversation_id]
        result.append({'conversation_id':chat['id'],'attachment_id':row.id,'sha256':file['sha256'],
            'name':file['name'],'conversation_title':chat['title'],'notes':file['notes'],'size':file['size']})
    return result
