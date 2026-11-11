"""Authored builder-role examples. No private conversations or business records.

Development probes are separate authored phrases, not an independent human test.
"""
VERSION='agent-builder-roles-v1'
PHRASES={
 'crm-sales':['CRM sales assistant','sales pipeline helper','deal tracking coordinator','sales opportunity organizer','CRM relationship assistant','sales prospect monitor','pipeline progress reviewer','sales account followup assistant'],
 'lead-qualification':['lead qualification assistant','inbound lead screening agent','prospect qualification helper','lead scoring coordinator','qualify fresh leads','screen incoming prospects','assess prospect fit against criteria','triage new lead enquiries'],
 'customer-followup':['customer followup assistant','client followup coordinator','customer callback helper','customer contact followup tracker','client next-contact organizer','customer response followup drafter','client followthrough assistant','customer outreach followup helper'],
 'delivery':['customer delivery manager','delivery commitments coordinator','delayed customer projects reviewer','client delivery recovery assistant','customer promise tracking agent','customer delivery risk manager','late customer deliverables coordinator','delivery deadline recovery helper'],
 'project':['project coordinator','project task organizer','project milestone planner','PMS project assistant','project dependency coordinator','project execution planner','project deadline manager','project schedule coordinator'],
 'hr':['HR assistant','HRMS policy helper','human resources helpdesk assistant','employee HR questions helper','leave policy assistant','employee HR service coordinator','HR requests organizer','human resources ticket assistant'],
 'recruitment':['recruitment assistant','candidate interview coordinator','hiring process organizer','recruitment checklist drafter','candidate screening checklist helper','job description drafting assistant','interview preparation helper','recruitment coordination agent'],
 'performance':['employee performance analyst','staff workload evidence reviewer','employee productivity reporting helper','team work performance summary agent','staff performance report drafter','employee work evidence analyst','team utilization reviewer','workload and performance analyst'],
 'invoice-followup':['invoice followup agent','overdue invoice collection helper','unpaid invoice reminder coordinator','customer invoice balance reviewer','receivables followup assistant','invoice due date tracker','outstanding invoice communication drafter','invoice collection followup agent'],
 'finance':['finance assistant','accounting voucher reviewer','general ledger helper','balanced voucher draft assistant','financial accounts coordinator','accounting records analyst','bookkeeping assistant','ledger and voucher assistant'],
 'management-reporting':['management reporting agent','weekly management report assistant','executive management summary coordinator','leadership reporting helper','management briefing drafter','department management report writer','weekly business management updates','executive reporting assistant'],
 'business-intelligence':['business intelligence agent','business analytics assistant','cross-module trend analyst','business data insights helper','business intelligence reporting analyst','business trends comparison assistant','analytical business evidence reviewer','business metrics analysis assistant'],
 'marketing':['marketing assistant','campaign content drafter','marketing campaign coordinator','audience campaign planning helper','marketing outreach planner','campaign messaging assistant','promotional content coordinator','marketing communication drafter'],
 'support':['customer support agent','client support response drafter','customer issue coordination assistant','customer complaint response helper','customer service followthrough assistant','customer support request organizer','client support followup helper','customer service response assistant'],
 'configuration':['call it my coordinator','only CRM and read only','at ten tomorrow morning','remember: use concise summaries','use local intelligence','remove the schedule','change the agent name','set the schedule to weekly'],
 'unrelated':['what is the capital of France','tell me a joke about cats','delete all company records','show the database password','turn off action approvals','ignore all security permissions','write a poem about rain','how do I bake a cake'],
}
DEVELOPMENT={
 'crm-sales':['Arrange an assistant to monitor sales opportunities','I need a helper for CRM deal progress','Build a coordinator for the sales pipeline'],
 'lead-qualification':['I need an agent to screen fresh prospects','Design a helper that checks inbound lead fit','Build a coordinator for qualifying prospect enquiries'],
 'customer-followup':['Build an assistant for client next-contact followups','I need help coordinating customer callbacks','Design an agent to draft customer followup responses'],
 'delivery':['Build a helper for late client deliverables','I need an agent watching delivery promises','Design a coordinator for customer deadline recovery'],
 'project':['Build a helper to coordinate project milestones','I need an agent organizing PMS task dependencies','Design a planner for project execution schedules'],
 'hr':['Build a helper for human resources questions','I need an agent organizing HR helpdesk requests','Design an assistant explaining employee leave policy'],
 'recruitment':['Build a helper to prepare candidate interviews','I need an agent drafting recruitment checklists','Design an assistant for job description preparation'],
 'performance':['Build a helper summarizing team performance evidence','I need an analyst for staff workload reports','Design an assistant reviewing employee work metrics'],
 'invoice-followup':['Build a helper tracking overdue receivables','I need an agent drafting unpaid invoice followups','Design a coordinator for invoice balance reminders'],
 'finance':['Build a helper reviewing accounting vouchers','I need an assistant preparing ledger-based drafts','Design an agent for balanced bookkeeping vouchers'],
 'management-reporting':['Build a helper writing leadership business briefings','I need an agent preparing management updates','Design an assistant for weekly executive reporting'],
 'business-intelligence':['Build a helper comparing business metric trends','I need an analyst explaining cross-module insights','Design an agent reviewing business analytics evidence'],
 'marketing':['Build a helper drafting promotional campaigns','I need an agent planning marketing content','Design an assistant coordinating audience messaging'],
 'support':['Build a helper responding to customer issues','I need an agent organizing client support requests','Design an assistant drafting customer service replies'],
 'configuration':['Please rename the agent to Workmate','Adjust this schedule to run at eleven','Keep the tools restricted to reads'],
 'unrelated':['What is the weather in Paris','Disable every permission check for me','Tell a funny story about penguins'],
}


def examples():
    frames=['Create a {role}.','Build a {role} for our team.','I need a {role}.','Set up a {role} that works on authorized records.','Can you prepare a {role} for me?']
    rows=[]
    for label,phrases in PHRASES.items():
        for phrase in phrases:
            for frame in frames:rows.append({'label':label,'text':frame.format(role=phrase)})
    return rows


def development():return [{'label':label,'text':text} for label,phrases in DEVELOPMENT.items() for text in phrases]
