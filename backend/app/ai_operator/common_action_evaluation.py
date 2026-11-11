"""Planner-boundary audit, with synthetic context and no business execution."""
import re
from types import SimpleNamespace
from app.ai_operator.common_actions import VERSION,catalog


def benchmark():
    from app.ai_operator.local_features import head
    from app.ai_operator.local_nlp import parse
    from app.ai_operator.local_writing import chat_plan
    from app.ai_operator.local_runtime import task_plan
    from app.ai_operator.workflows import local_plan
    failures=[];passed={m:0 for m in ('PMS','CRM','HRMS')}
    for row in catalog():
        try:
            text=head(row['text'])
            assignment=text.endswith(' and assign it to any eligible user')
            # Canonical people lookup/execution are separately covered by the
            # native assignment tests. This audit checks the underlying draft.
            if assignment:text=text.removesuffix(' and assign it to any eligible user')
            data=SimpleNamespace(text=text,module=row['module'],project_id=12 if row['module']=='PMS' else None,
                request_key='catalog-'+row['id'],timezone='Asia/Kolkata')
            if chat_plan(text) is not None:raise ValueError('Action intercepted by writing router')
            proposal,_=local_plan(data,None,None)
            if proposal is None:
                intent=parse(row['module']+': '+text,row['module'])
                if intent.module!=row['module'] or intent.intent!=row['intent']:
                    raise ValueError(f'Expected {row["intent"]}, got {intent.module}/{intent.intent}')
                snapshots=[{'id':n,'title':f'Synthetic task {n}'} for n in range(101,211)]
                context=[{'tool':'pms.tasks' if row['module']=='PMS' else 'crm.tasks','records':snapshots}]
                proposal=task_plan(intent,data,context,[])
                if row['behavior']=='authorized_read' and intent.question:raise ValueError('Read unexpectedly asks for details')
            if row['behavior']=='reviewed_draft':
                if not proposal or proposal.get('question') or len(proposal.get('steps',[]))!=1:
                    raise ValueError('Expected exactly one reviewable draft')
                step=proposal['steps'][0]
                expected={'tasks.create':'create_task','ticket.create':'create_ticket','milestone.create':'create_milestone'}
                if row['intent'] in expected and step['tool']!=row['module'].lower()+'.'+expected[row['intent']]:
                    raise ValueError('Wrong mutation tool')
                quoted=re.search(r'"([^"]+)"',text)
                if quoted and quoted[1]!=next((step['payload'][k] for k in ('title','name','subject') if k in step['payload']),None):
                    raise ValueError('Draft title changed')
            elif row['behavior']=='native_handoff':
                if not proposal or not proposal.get('question') or proposal.get('steps'):
                    raise ValueError('Native-only request must not create a local action')
            elif row['behavior']=='needs_details' and proposal and proposal.get('steps'):
                raise ValueError('Missing details must not create an executable action')
            passed[row['module']]+=1
        except Exception as exc:
            failures.append({'id':row['id'],'text':row['text'],'intent':row['intent'],'error':str(exc)})
    return {'version':VERSION,'total':600,'passed':sum(passed.values()),'by_module':passed,'failures':failures,
        'limits':'Authored training-fit and planner-routing audit with synthetic task context. Not unseen language accuracy or live execution. Reads still require canonical permissions; assignment lookup is covered by separate native tests.'}
