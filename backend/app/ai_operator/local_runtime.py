"""Local NLP proposals and read answers; all source access remains canonical."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from app.ai_operator.evidence import records
from app.ai_operator.local_nlp import VERSION, SCOPES


def ask(question):
    return {'summary':'I need these details before preparing this request.','question':question,'steps':[]}


def task_plan(intent, data, context, sources):
    from app.ai_operator.local_dialogue import need
    name,slots=intent.intent,intent.slots
    if name=='conversation.reset':return {'summary':'Started an independent conversation. Previous drafts are unchanged and still require review.','steps':[]}
    if name=='cancelled':return {'summary':'The pending request was cancelled. No new action was executed.','steps':[]}
    if intent.question:return ask(intent.question)
    verbs={
        'tasks.create':{'create','add','make','prepare','draft'},'milestone.create':{'create','add','make','prepare','draft'},
        'ticket.create':{'create','raise','open','prepare','submit','log'},'note.create':{'add','record','write','save','prepare','attach','put'},
        'tasks.priority':{'set','make','change','raise','update','mark'},'tasks.status':{'set','make','change','update','mark','complete','finish'},
        'tasks.schedule':{'schedule','plan','suggest','prepare','draft','start','set'},
    }
    if name in verbs and slots.get('action_verb') not in verbs[name]:
        return ask('Do you want a read or a new action draft? Use an explicit action such as “create task”, “set task priority” or “add note”.')
    module=SCOPES[intent.module]
    if slots.get('invalid_date'):return ask('Please supply a valid ISO date or a supported relative date such as tomorrow.')
    if module=='PMS' and name not in {'projects.list','reminders.today','jobs.today'} and not data.project_id:
        return need(intent,'project_id','Which project ID should I use? Reply with project #12, for example. I will check your project access.')
    if name in {'tasks.create','milestone.create','ticket.create'}:
        if name=='tasks.create' and slots.get('record_id'):return ask('You included an existing task ID. Do you want to update that task, or create a new task with a title?')
        title=slots.get('title')
        if not title:return need(intent,'title','What title should I use? You can reply with the title directly.')
        payload={'title':title}
        if slots.get('priority'):payload['priority']=slots['priority']
        if len(title)>220:return ask('Please use a title of at most 220 characters.')
        if slots.get('due_date'):payload['due_date']=slots['due_date']
        if name=='tasks.create':
            if module=='PMS':payload['task_key']='AI-'+re.sub(r'[^a-zA-Z0-9]','',data.request_key)[:16]
            tool=module.lower()+'.create_task'
        elif name=='milestone.create':
            tool='pms.create_milestone';payload['name']=payload.pop('title')
        else:
            tool='hrms.create_ticket';payload={'subject':title,'description':slots.get('body') or title,'priority':slots.get('priority') or 'Medium'}
        step={'tool':tool,'payload':payload}
        if module=='PMS':step['record_id']=data.project_id
        return {'summary':'Review this local draft. No record has been created.','steps':[step]}
    if name in {'tasks.priority','tasks.status','tasks.schedule'}:
        ident=slots.get('record_id')
        if not ident:return need(intent,'record_id','Which task ID should I use? Reply with task #12 or its number.')
        visible=[row for packet in context if packet['tool'] in {'crm.tasks','crm.task','pms.tasks'} for row in records(packet['records'])]
        if not any(row.get('id')==ident for row in visible):return ask('That task was not found in the authorized sample. Select the task as a source or refine the project before changing it.')
        if name=='tasks.schedule':
            if not slots.get('due_date'):return need(intent,'date','When should scheduling start? Reply tomorrow or an ISO date.')
            step={'tool':'pms.schedule','record_id':data.project_id,'payload':{'task_ids':[ident],'start_date':slots['due_date']}}
        else:
            field='priority' if name=='tasks.priority' else 'status'
            if not slots.get(field):return need(intent,field,f'What {field} should the task have?')
            changes={field:slots[field]}
            if module=='PMS':step={'tool':'pms.task_plan','record_id':data.project_id,'payload':{'plan':{'summary':'Review local task update','steps':[{'tool':'update_task','task_id':ident,'changes':changes}]}}}
            else:step={'tool':'crm.update_task','record_id':ident,'payload':changes}
        return {'summary':'Review this exact task change. It has not been applied.','steps':[step]}
    if name=='note.create':
        if not slots.get('record_id'):return need(intent,'record_id','Which lead ID should receive the internal note?')
        if not slots.get('body'):return need(intent,'body','What exact internal note should I save?')
        return {'summary':'Review this internal note; it sends no external message.','steps':[{'tool':'crm.add_note','payload':{'lead_id':slots['record_id'],'body':slots['body'],'is_internal':True}}]}
    if name=='leave.create':
        types=[row for packet in context if packet['tool']=='hrms.leave_types' for row in records(packet['records'])]
        if slots.get('leave_type_name'):
            matched=[r for r in types if str(r.get('name','')).casefold()==slots['leave_type_name'].strip().casefold()]
            if len(matched)==1:slots['leave_type_id']=matched[0]['id']
        if not slots.get('leave_type_id'):
            return need(intent,'leave_type_id','Which leave type ID? '+', '.join(f'{r["id"]}: {r.get("name", "Leave type")}' for r in types[:15]))
        if not any(r.get('id')==slots['leave_type_id'] for r in types):return need(intent,'leave_type_id','Choose a leave type ID from the authorized list.')
        for field,question in [('from_date','What date should leave start?'),('to_date','What date should leave end?'),('is_half_day','Full day or half day?'),('reason','What reason should I include?')]:
            if field not in slots:return need(intent,field,question)
        if slots['is_half_day'] and not slots.get('half_day_period'):return need(intent,'half_day_period','Morning or afternoon half day?')
        if slots['to_date']<slots['from_date']:return need(intent,'to_date','The end date precedes the start date. What end date should I use?')
        payload={k:slots[k] for k in ('leave_type_id','from_date','to_date','is_half_day','reason')}
        if slots.get('half_day_period'):payload['half_day_period']=slots['half_day_period']
        return {'summary':'Review your leave request. Submission does not approve it.','steps':[{'tool':'hrms.request_leave','payload':payload}]}
    if name=='reminders.create':
        allowed={'CRM':{'task','lead','deal'},'PMS':{'task','project'},'HRMS':{'leave'},'SRM':{'invoice'}}
        for field,question in [('entity','What record type is the reminder for? '+', '.join(sorted(allowed[module]))),
                               ('record_id','What is the existing record ID?'),('title','What should the reminder say?'),
                               ('date','What date should I remind you?'),('time','At what time? For example 09:30 or 3 pm.'),
                               ('channel','In app or email? This reminder will be sent only to you, once.')]:
            if not slots.get(field):return need(intent,field,question)
        if slots['entity'] not in allowed[module]:return need(intent,'entity','Choose one of: '+', '.join(sorted(allowed[module])))
        try:scheduled=datetime.fromisoformat(slots['date']+'T'+slots['time']).replace(tzinfo=ZoneInfo(data.timezone))
        except ValueError:return need(intent,'date','Supply a valid reminder date.')
        if scheduled<=datetime.now(ZoneInfo(data.timezone)):return need(intent,'date','That time has passed. What future date should I use?')
        if slots['channel'] not in {'email','in_app'}:return need(intent,'channel','Choose in app or email for scheduled reminders.')
        from uuid import uuid5,NAMESPACE_URL
        payload={'request_key':str(uuid5(NAMESPACE_URL,'local-reminder:'+data.request_key)),'module':module,'entity':slots['entity'],
                 'record_id':slots['record_id'],'title':slots['title'],'scheduled_at':scheduled.isoformat(),
                 'expires_at':(scheduled+timedelta(days=1)).isoformat(),'timezone':data.timezone,'frequency':'once','channels':[slots['channel']]}
        return {'summary':'Review this one-time reminder to yourself. It expires 24 hours after its scheduled time. No reminder is active yet.',
                'steps':[{'tool':module.lower()+'.create_reminder','payload':payload}]}
    missing={
      'reminders.create':'Select a record, date/time, timezone, recipients and channel in Follow-through → Reminders. The exact schedule needs review.',
      'leave.create':'Choose the leave type, start/end dates, half-day setting and reason in the leave request form. I will not guess your leave type.',
      'leave.approve':'Open the authorized leave approval queue and review the request and decision. This local command does not grant manager approval.',
      'invoice.create':'Choose a real customer, seller, currency and priced line items in the invoice draft form. Issuing and sending remain separate.',
      'invoice.send':'Open the invoice and review the recipient and document in Sales before confirming delivery. No invoice was sent.',
      'invoice.issue':'Open and review the canonical invoice issuance workflow. This local command cannot finalize a financial document.',
      'payment.record':'Use the Sales payment/receipt workflow with the real amount, account and allocation. No payment or ledger entry was recorded.',
      'orders.create':'Choose the customer, seller, currency and order lines in the canonical Sales order form before review.',
      'payroll':'Payroll and bank details are outside this local assistant catalog. Use the separately authorized payroll workspace.',
      'attendance':'Attendance queries are not connected to this local catalog yet. Open the authorized Attendance workspace.',
    }
    if name in missing:return ask(missing[name])
    return None


def read_reply(intent, context, sources, data, user_id, *, instant=None):
    from app.ai_operator.briefing import local_date,DONE
    today=(instant.astimezone(ZoneInfo(data.timezone)) if instant else datetime.now(ZoneInfo(data.timezone))).date()
    rows=[];seen=set()
    for index,packet in enumerate(context):
        for offset,row in enumerate(records(packet['records'])):
            key=(packet['tool'],row['id']) if row.get('id') else (index,offset)
            if key not in seen: rows.append((packet,row));seen.add(key)
    name=intent.intent
    selected=[]
    for packet,row in rows:
        status=str(row.get('status','')).lower()
        due=local_date(row.get('due_date'),data.timezone)
        owners=[row.get('owner_user_id'),row.get('assignee_user_id'),*(row.get('assignee_user_ids') or [])]
        if name in {'tasks.today','invoices.today','jobs.today'} and due!=today:continue
        if name in {'tasks.overdue','invoices.overdue','risk'} and not (due and due<today or status=='blocked'):continue
        if name=='tasks.blocked' and status!='blocked':continue
        if name=='tasks.mine' and user_id not in owners:continue
        if name=='tasks.unassigned' and any(owners):continue
        if name=='tasks.high' and str(row.get('priority','')).lower() not in {'high','urgent','critical'}:continue
        if name=='invoices.draft' and status!='draft':continue
        if name in {'invoices.unpaid','invoices.overdue'}:
            from decimal import Decimal,InvalidOperation
            try:
                balance=Decimal(str(row.get('balance_amount')))
                if status in {'draft','cancelled','canceled','void','paid'} or not balance.is_finite() or balance<=0:continue
            except (InvalidOperation,TypeError):continue
        if name in {'tasks.today','tasks.overdue','tasks.mine','tasks.high','tasks.unassigned','tasks.blocked','invoices.overdue','invoices.today','risk','jobs.today'} and status in DONE:continue
        selected.append((packet,row))
    keys={(packet['tool'],row.get('id')) for packet,row in selected}
    refs=[source['id'] for source in sources if (source['tool'],source['record_id']) in keys][:50]
    labels=[]
    for _,row in selected[:15]:
        label=row.get('title') or row.get('name') or row.get('full_name') or row.get('subject') or row.get('invoice_number') or f'Record {row.get("id", "(summary)")}'
        labels.append(str(label)[:180]+(f' [{row["status"]}]' if row.get('status') else '')+(f' due {row["due_date"]}' if row.get('due_date') else ''))
    summary=f'{intent.module} · {name}: {len(selected)} matching records in the authorized source sample.'
    if name=='leave.balance':
        safe=[{k:v for k,v in row.items() if k in {'name','leave_type','leave_type_id','year','allocated','used','pending','available'}} for _,row in selected]
        summary+=' '+str(safe)[:1400]
    elif name in {'sales.dashboard','invoices.report'}:
        summary+=' '+str([row for _,row in selected][:5])[:1800]
    elif labels:summary+='\n'+'\n'.join('• '+label for label in labels)
    else:summary+=' No matching records were found in this sample.'
    return {'summary':summary[:2000],'steps':[],'source_ids':refs}


async def respond(intent,context,sources,data,request,db,user):
    from app.ai_operator.suite import api_call,authorize,now
    from app.ai_agents.security import company,bounded_result
    from app.access.service import check_background_access
    from app.ai_operator.local_tensorflow import status as model_status,runtime_scope
    module=SCOPES[intent.module]
    runtime=model_status(runtime_scope(db,user,getattr(data,'workspace_id',None)))
    details={'version':VERSION,'module':intent.module,'intent':intent.intent,'confidence':intent.confidence,'release':runtime.get('release'),
             'slots':intent.slots,
             'model':runtime['description'],'neural_prediction':intent.neural,'cloud_calls':0,'coverage':'bounded authorized sources'}
    if any(isinstance(packet['records'],dict) and packet['records'].get('truncated') for packet in context):
        return ask('A selected source exceeds the disclosure budget. Narrow its filters before requesting a local answer or action.'),details,[]
    proposal=task_plan(intent,data,context,sources)
    if proposal is not None:
        if data.mode=='summary' and proposal.get('steps'):proposal=ask('Summary-only mode cannot prepare actions. Choose Answer or prepare actions first.')
        return proposal,details,[]
    name=intent.intent
    if name=='sales.dashboard':
        details.update(kind='dashboard',data=bounded_result(db,user,[p['records'] for p in context if p['tool']=='srm.dashboard']))
        return {'summary':'Authorized native Sales dashboard snapshot. Inspect the displayed totals and scope; no cloud call or write was made.','steps':[]},details,[]
    if name=='leads.message':
        from app.ai_operator.local_dialogue import need
        slots=intent.slots
        if slots.get('action_verb') not in {'send','email','message','prepare','draft','mail','whatsapp','sms'}:
            return ask('Do you want to prepare lead outreach? State the channel and exact subject/body; nothing will send automatically.'),details,[]
        if data.mode=='summary':return ask('Choose Answer or prepare actions to preview an outbound message.'),details,[]
        if not slots.get('channel'):return need(intent,'channel','Which channel: email, WhatsApp or SMS?'),details,[]
        if not slots.get('subject'):return need(intent,'subject','What exact subject should I use?'),details,[]
        if not slots.get('body'):return need(intent,'body','What exact message body should I use?'),details,[]
        lead_packets=[p for p in context if p['tool']=='crm.leads']
        leads=[r for p in lead_packets for r in records(p['records'])]
        if not leads:return {'summary':'No leads were returned by the authorized source. No message was sent.','steps':[]},details,[]
        # Do not silently substitute the first page for "all".
        if any(not p.get('complete',False) for p in lead_packets):
            return ask('The lead source is a partial sample. Use the CRM audience filters and reviewed batches of at most 50 recipients; I cannot call this sample all leads.'),details,[]
        draft={'channel':slots['channel'],'subject':slots['subject'],'body':slots['body'],
               'recipients':[{'entity':'leads','id':r['id']} for r in leads[:50]]}
        preview=await api_call(request.app,request.headers.get('authorization',''),'POST','/crm/growth/greetings/preview',draft)
        safe={k:v for k,v in preview.items() if k!='preview_token'}
        safe=bounded_result(db,user,safe)
        if safe.get('truncated'):return ask('The outreach preview exceeds the disclosure limit. Narrow the audience in CRM.'),details,[]
        details.update(kind='message_preview',preview=safe,draft=draft,sent=False)
        if not preview.get('eligible'):
            return {'summary':'No eligible recipients remain. No send action was prepared. Review the blocked-recipient reasons.','steps':[]},details,[]
        if not preview.get('can_send'):
            return {'summary':'I cannot send this channel through the connected provider. '+str(preview.get('channel_note','')),'steps':[]},details,[]
        from uuid import uuid5,NAMESPACE_URL
        payload={**draft,'preview_token':preview['preview_token'],'request_id':str(uuid5(NAMESPACE_URL,'local-outreach:'+data.request_key))}
        return {'summary':f'Review this send action: {preview["eligible"]} eligible leads, {preview["blocked"]} blocked. Nothing sent yet. Consent and the exact message will be checked again on approval.','steps':[{'tool':'crm.send_lead_message','payload':payload}], 'source_ids':[s['id'] for s in sources if s['tool']=='crm.leads'][:50]},details,[]
    if name=='reminders.today':
        from app.ai_operator.reminders import Job,source,utc
        from app.ai_operator.suite import MODULES
        from app.ai_agents.security import scoped
        authorize(db,user,data.workspace_id,module);check_background_access(db,user,MODULES[module],'view')
        branch=db.info.get('branch_context')
        if not branch or not branch.branch_id:return ask('Select a concrete branch to check today’s reminders.'),details,[]
        instant=now();today=instant.astimezone(ZoneInfo(data.timezone)).date()
        rows=db.query(Job).filter_by(job_type='ai_reminder',created_by=user.id,organization_id=company(user),status='ai_active').filter(
            Job.payload_json['branch_id'].as_integer()==branch.branch_id).order_by(Job.run_at).limit(101).all()
        visible=[];unavailable=0
        for row in rows[:100]:
            spec=row.payload_json['spec']
            if spec['module']!=module or not row.run_at or utc(row.run_at).astimezone(ZoneInfo(data.timezone)).date()!=today:continue
            if datetime.fromisoformat(spec['expires_at'])<=instant:continue
            try:
                with scoped(db,user,MODULES[module]):
                    current=source(db,user,spec)
                from app.ai_operator.briefing import DONE
                if str(current.get('status','')).lower() in DONE:continue
                visible.append({'id':row.id,'title':spec['title'],'due_at':utc(row.run_at).isoformat(),'href':row.payload_json['href']})
            except HTTPException:unavailable+=1
        details.update(kind='reminders',items=visible,limited=len(rows)>100,unavailable=unavailable,today=today.isoformat(),timezone=data.timezone)
        return {'summary':f'{module}: {len(visible)} active reminders due today ({data.timezone}). '+(' '.join(f'{r["title"]} at {r["due_at"]}.' for r in visible[:10]) or 'No matching active reminders in the authorized sample.')+' Unavailable sources are excluded.','steps':[]},details,[]
    if name=='jobs.today' and module in {'CRM','PMS','HRMS'}:
        value=await api_call(request.app,request.headers.get('authorization',''),'GET','/ai-operator/suite/briefing',
            {**({'workspace_id':data.workspace_id} if data.workspace_id else {}),**({'project_id':data.project_id} if data.project_id and module=='PMS' else {}),
             'module':module,'mine':True,'timezone':data.timezone})
        found=[row for row in value['priorities'] if row.get('due_date')==value['today'] or 'Overdue' in row.get('reasons',[]) or module=='HRMS']
        details.update(kind='jobs',items=found,source_coverage=value['coverage'],limited=value['limited'],today=value['today'])
        extras=[row['source'] for row in found[:50]]
        for index,ref in enumerate(extras):ref['id']=f'local-job:{index}:{ref["record_id"]}'
        label='pending personal HR requests (not all dated today)' if module=='HRMS' else 'due-today or overdue jobs'
        return {'summary':f'{len(found)} {label} in the authorized sample. '+(' '.join(f'{r["title"]}: {", ".join(r["reasons"])}.' for r in found[:10]) or 'No matching work in available sources.'),'steps':[],
                'source_ids':[ref['id'] for ref in extras]},details,extras
    if name in {'capacity','playbooks','dependencies','invoices.report'}:
        if name=='capacity':
            path='/ai-operator/suite/operations/capacity-scenario';method='POST'
            payload={'project_id':data.project_id,'workspace_id':data.workspace_id,'week_start':now().astimezone(ZoneInfo(data.timezone)).date().isoformat()}
        elif name in {'playbooks','dependencies'}:
            path='/ai-operator/workbench/items' if name=='playbooks' else '/ai-operator/local-context';method='GET';payload={'project_id':data.project_id}
        else:
            path='/ai-operator/suite/reports/SRM';method='GET';payload={'entity':'invoices','group_by':'currency','measures':'count,amount','timezone':data.timezone}
        value=await api_call(request.app,request.headers.get('authorization',''),method,path,payload)
        if name=='dependencies':value={'items':[{'task_id':t['id'],'dependencies':t.get('dependencies',[])} for t in value['tasks'] if t.get('dependencies')], 'complete':value.get('tasks_complete',False)}
        if name=='playbooks':value={'items':[r for r in value.get('items',[]) if r.get('kind') in {'playbook','rule','memory'}]}
        details.update(kind=name,data=bounded_result(db,user,value))
        return {'summary':f'Local {intent.module} {name} preview. Inspect the structured result and coverage. No changes were made.','steps':[]},details,[]
    return read_reply(intent,context,sources,data,user.id),details,[]
