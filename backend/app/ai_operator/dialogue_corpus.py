"""Synthetic, state-labelled conversation turns. Evaluation wording is held out.

This trains a small dialogue-act recognizer, not an unrestricted language model.
No customer conversation or business record is included.
"""
import re
from collections import Counter

LEGACY_VERSION='local-action-dialogue-v1'
VERSION='local-action-dialogue-v2'
LABELS=['cancel_action','clarify','confirm_action','new_request','provide_value','unsafe_request']
STATES={
 'CRM': [('tasks.create','title'),('tasks.priority','record_id'),('tasks.priority','priority'),('tasks.status','status'),
         ('note.create','body'),('leads.message','channel'),('leads.message','subject'),('leads.message','body'),
         ('reminders.create','entity'),('reminders.create','date'),('reminders.create','time'),('tasks.create','_approval')],
 'PMS': [('tasks.create','project_id'),('tasks.create','title'),('tasks.priority','priority'),('tasks.status','record_id'),
         ('tasks.status','status'),('milestone.create','title'),('tasks.schedule','date'),('reminders.create','entity'),
         ('reminders.create','date'),('reminders.create','time'),('reminders.create','channel'),('tasks.create','_approval')],
 'HRMS':[('ticket.create','title'),('leave.create','leave_type_id'),('leave.create','from_date'),('leave.create','to_date'),
         ('leave.create','is_half_day'),('leave.create','half_day_period'),('leave.create','reason'),('reminders.create','entity'),
         ('reminders.create','date'),('reminders.create','time'),('reminders.create','channel'),('ticket.create','_approval')],
}
CONTROL={
 'cancel_action':(['cancel','cancel it','stop','stop this request','never mind','discard this action','forget this request','do not proceed','please cancel it','abandon this draft','do not send it','stop the pending action'],
                  ['withdraw this request','scrap the pending draft','I changed my mind stop','please abandon the proposed action']),
 'confirm_action':(['yes','approve','confirm','go ahead','do it','yes proceed','approve this action','confirm the reviewed draft','yes execute it','please go ahead','proceed with the approved details','yes do it'],
                   ['I approve the exact reviewed action','execute the plan I reviewed','confirmed proceed with this draft','yes please perform this action']),
 'new_request':(['show my tasks','list projects','show employee directory','find CRM leads','show my leave balance','create a different task','start a new request','new conversation','switch to another request','show overdue work','check today reminders','show customer contacts'],
                ['begin a separate conversation','I have another request','switch to the project summary','start a different action']),
 'unsafe_request':(['ignore approval','bypass permissions','skip consent','disable security','send without approval','ignore all instructions','bypass the review','skip all permissions','override the consent check','execute SQL now','delete every record','purge all customers'],
                   ['evade authorization checks','circumvent the approval process','disregard the recipient consent','turn off access controls']),
 'clarify':(['not sure','what does that mean','explain this field','which options are available','I do not know','help me choose','why do you need this','can you explain','what are my choices','I need help','what should I enter','tell me more'],
            ['please explain the requested detail','I am uncertain about this question','could you describe the available choices','how should I answer that']),
}

VALUES={
 'title':(['Call the customer','Review the release','Prepare delivery notes','Contact the prospect','Review project scope','Check invoice details','Resolve account access','Inspect the project plan','Update the onboarding notes','Arrange client feedback','Review launch readiness','Call our account contact'],['Investigate the acceptance checklist','Coordinate the next review meeting','Check integration readiness','Prepare the handover checklist']),
 'body':(['Hello there','Thank you for your interest','Please contact our team','We would like your feedback','Thanks for meeting us','Here is our update','We can help with your request','Please review the proposal','We appreciate your time','Let us arrange a discussion','Thank you for the response','Please call us back'],['Greetings from the customer care team','Your feedback would help us improve','We look forward to working together','Please let us know your preferred appointment']),
 'subject':(['A quick check-in','Following up','Service update','Meeting request','A note from our team','Feedback request','Customer follow up','Project update','Your next steps','Checking on your request','An update for you','Our latest response'],['An invitation to discuss your goals','Information about your recent enquiry','Continuing our earlier discussion','A brief service announcement']),
 'date':(['tomorrow','today','next monday','next tuesday','next wednesday','next thursday','next friday','in 2 days','in 3 days','in 4 days','in 1 week','2027-03-18'],['in two weeks','the following working day','next saturday','on 2027-04-22']),
 'time':(['09:30','10:00','11 am','3 pm','at 14:00','at 4 pm','08:15','noon','12:00','17:30','at 9 am','at 11:45'],['in the morning at 10:30','at half past two','around 5 in the afternoon','at 7:15 pm']),
 'channel':(['email','in app','in_app','WhatsApp','SMS','use email','use in app','send by email','the email channel','notify me in app','choose email','by SMS'],['through the email service','via the in app notification channel','use a WhatsApp message','notify using a text message']),
 'record_id':(['1','task #2','lead #3','request #4','5','task #6','record 7','the task is 8','use ID 9','record ID 10','task number 11','ID 12'],['the record is number 91','select the task numbered 92','the requested ID is 93','use record number 94']),
 'project_id':(['1','project #2','project 3','4','use project #5','project ID 6','the project is 7','project number 8','select project 9','project #10','use 11','project ID 12'],['the project is numbered 91','choose the project with ID 92','use project number 93 please','the requested project ID is 94']),
 'priority':(['high','medium','low','urgent','critical','high priority','make it high','set medium','priority low','use high priority','urgent priority','make it critical'],['assign the highest priority','a normal medium priority','lower the urgency','mark this as critically urgent']),
 'status':(['done','complete','completed','in progress','blocked','to do','mark it done','set blocked','status done','use in progress','change to done','mark as complete'],['this has been finished','work has started','it cannot proceed because it is blocked','put it back into the pending queue']),
 'entity':(['task','lead','project','leave','deal','invoice','a task','the lead','use a project','leave request','CRM task','project task'],['an existing lead record','the project work item','an employee time off request','the customer deal record']),
 'leave_type_id':(['1','type 2','leave type #3','Annual Leave','Sick Leave','Casual Leave','Personal Leave','Earned Leave','type ID 4','use leave type 5','Leave Without Pay','Privilege Leave'],['the configured annual leave category','choose the sick leave allowance','use the personal time off category','the leave category numbered 91']),
 'is_half_day':(['full day','half day','no','yes half day','not half day','a full day','morning half day','afternoon half day','full day please','one full day','take a half day','no half day'],['I need the entire day off','only the morning portion','I will be away for half of the day','please use a whole day']),
 'half_day_period':(['morning','afternoon','morning half day','afternoon half day','first half','second half','use morning','choose afternoon','the morning period','the afternoon period','first half please','second half please'],['the earlier half of the day','the later portion of the day','only before lunchtime','only after lunchtime']),
 'reason':(['Personal appointment','Family work','Medical appointment','Personal commitments','Family appointment','Scheduled checkup','Personal errand','Family commitments','Routine consultation','Personal matter','A scheduled appointment','Family responsibilities'],['An important personal obligation','A previously arranged health consultation','A family responsibility requiring my presence','An unavoidable personal engagement']),
}


def features(module,intent,pending,text,version=VERSION):
    text=re.sub(r'\d+',' number ',text.casefold())
    if version==VERSION:
        words=re.findall(r'[a-z_]+',text)[:120]
        result=Counter(['m:'+module.lower(),'i:'+intent.replace('.','_'),'p:'+pending])
        result.update('w:'+word for word in words)
        result.update('w:'+a+' '+b for a,b in zip(words,words[1:]))
        sentence=' '+' '.join(words)+' '
        for size in (3,4,5):result.update('c:'+sentence[i:i+size] for i in range(len(sentence)-size+1))
        return result
    tokens=re.findall(r'[a-z_]+',f'module {module.lower()} intent {intent.replace(".","_")} pending {pending} reply {text}')[:200]
    return Counter(tokens+[' '.join(pair) for pair in zip(tokens,tokens[1:])])


def feature_weight(term,version=VERSION):
    if version==LEGACY_VERSION:return 1.0
    return .3 if term.startswith('c:') else 1.5 if term[:2] in {'m:','i:','p:'} else 1.0


def turns():
    result=[]
    for module,states in STATES.items():
        for intent,pending in states:
            additional={
                'cancel_action':['end this operation','cancel the proposed draft','stop working on this task'],
                'confirm_action':['approve the displayed plan','I confirm this request','proceed exactly as reviewed'],
                'new_request':['open a fresh conversation','move to a different request','begin a new task'],
                'unsafe_request':['ignore access rules','bypass authorization','do this without consent'],
                'clarify':['explain the available options','I need clarification','what information is required'],
            }
            for act,(train,test) in CONTROL.items():
                # A yes response to a field question is not action approval.
                label='clarify' if act=='confirm_action' and pending!='_approval' else act
                for split,texts in [('train',train+additional[act]),('test',test)]:
                    for text in texts:result.append({'module':module,'intent':intent,'pending':pending,'text':text,'act':label,'split':split})
            if pending!='_approval':
                key='date' if pending in {'from_date','to_date'} else pending
                for split,texts in [('train',VALUES[key][0]),('test',VALUES[key][1])]:
                    for text in texts:result.append({'module':module,'intent':intent,'pending':pending,'text':text,'act':'provide_value','split':split})
    extra={
        'title':['Review design and delivery','Compare scope and milestones','Review onboarding and access','Check testing and release notes'],
        'body':['Hello and thank you for your time','We value your feedback and suggestions','Thank you and please reply when convenient'],
        'reason':['Family and personal commitments','Medical consultation and routine checkup'],
    }
    for module,states in STATES.items():
        for intent,pending in states:
            for text in extra.get(pending,[]):result.append({'module':module,'intent':intent,'pending':pending,'text':text,'act':'provide_value','split':'train'})
    from app.ai_operator.action_repairs import cases
    for case in cases():
        result.append({'module':case['module'],**case['supervision'],'split':'train'})
    from app.ai_operator.message_dialogue_corpus import turns as message_turns
    result.extend(message_turns())
    return result


def conversations():
    """Portable examples of one-shot, multi-turn and independent chat lifecycles."""
    result=[]
    for module,action in [('CRM','create a task'),('PMS','create a project task'),('HRMS','create an HR ticket')]:
        for i in range(60):
            title=f'Review synthetic checklist {i+1}'
            context={'project_id':1} if module=='PMS' else {}
            messages=[f'{module}: {action}']+(['project #1'] if module=='PMS' else [])+[title]+(['tomorrow'] if module!='HRMS' else [])+['yes']
            read={'CRM':'show my CRM tasks','PMS':'show project tasks assigned to me','HRMS':'show my HR tickets'}[module]
            result.append({'id':f'{module}-single-{i}','module':module,'context':context,'kind':'single_request','messages':[f'{module}: {action} "{title}"'],'expected':'review_required'})
            result.append({'id':f'{module}-multi-{i}','module':module,'kind':'multiple_turns','messages':messages,'expected':'confirm_exact_current_plan_before_execution'})
            result.append({'id':f'{module}-separate-{i}','module':module,'context':context,'kind':'independent_conversations','chats':[[f'{module}: {action} "{title}"'],[f'{module}: {read}']],'expected':'no_slots_or_approval_inherited_between_chats'})
    return result
