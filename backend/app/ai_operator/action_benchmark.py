"""Versioned, authored workplace acceptance cases, never training examples.

These are synthetic real-world-style conversations, not private customer chats
or an independent language sample. Native API receipts determine completion.
"""
import hashlib
import json

VERSION='action-workplace-v4.0'
REFERENCES=[
 {'concept':'Conversation creation and follow-ups','url':'https://help.clickup.com/hc/en-us/articles/19953994898711-Create-items-with-ClickUp-AI','checked_on':'2026-11-11','evidence':'Vendor documentation lists tasks, subtasks, Docs, reminders, Lists and artifacts; follow-ups depend on context.'},
 {'concept':'Compound actions, permissions, dependencies and documents','url':'https://developer.clickup.com/docs/mcp-tools','checked_on':'2026-11-11','evidence':'Vendor documentation describes task/document mutations, bulk operations and dependencies within the caller permissions. MCP tools do not themselves prove Brain reasoning success.'}]


def cases():
    result=[]
    for n,topic in enumerate(('Hospital onboarding','Retail renewal','Manufacturing dispatch','Agency launch','Campus rollout')):
        titles=[topic+' contract review',topic+' delivery check',topic+' owner handoff']
        quoted=', '.join('"'+t+'"' for t in titles)
        families=[
            ('crm-batch','CRM',[f'Create 3 CRM tasks {quoted}','Make all the tasks high priority',f'Rename item 2 to "{topic} delivery recovery"'],['crm.create_task']*3),
            ('pms-followups','PMS',[f'Create 3 PMS tasks {quoted}','project #{project_id}','Make all the tasks high priority',f'Rename item 1 to "{topic} kickoff review"'],['pms.create_task']*3),
            ('hrms-intake','HRMS',[f'Create 3 HR tickets {quoted}','Make all the tickets high priority',f'Rename item 2 to "{topic} staffing review"'],['hrms.create_ticket']*3),
            ('cross-module','CRM',[f'CRM: create task "{titles[0]}" '+('after that','afterwards','once that is done','finally','next')[n]+f' PMS: create task "{titles[1]}" then HRMS: create HR ticket "{titles[2]}"','project #{project_id}','Make the second one high priority',f'Rename item 1 to "{topic} customer call"','Show receipts'],['crm.create_task','pms.create_task','hrms.create_ticket']),
            ('ten-actions','CRM',['Create 10 CRM tasks '+', '.join(f'"{topic} checkpoint {i}"' for i in range(1,11)),f'Rename item 10 to "{topic} final review"','Make the ninth one high priority'],['crm.create_task']*10),
            ('cancel-chain','CRM',[f'CRM: create task "{titles[0]}" then PMS: create task "{titles[1]}" then HRMS: create HR ticket "{titles[2]}"','project #{project_id}',f'Rename item 1 to "{topic} cancelled draft"','Cancel this workflow'],[]),
            ('new-project','PMS',[f'Create project called "{topic}" with tasks {quoted}',f'Rename item 3 to "{topic} implementation check"','Make all the tasks high priority'],['pms.create_project']+['pms.create_task']*3),
            ('quoted-intent','CRM',[f'Create CRM tasks "{topic} call then review", "{topic} after that wait"',f'Rename item 2 to "{topic} final confirmation"','Make both high priority'],['crm.create_task']*2),
        ]
        for family,module,messages,tools in families:
            result.append({'id':f'{family}-{n+1}','family':family,'module':module,'messages':messages,
                'expected_tools':tools,'cancelled':family=='cancel-chain','receipt_question':None if family=='cancel-chain' else 'What did you do?',
                'fixture':'A private test user, an existing PMS project, an employee profile and no initial CRM tasks or HR tickets. Ten-action cases explicitly configure a twelve-call test budget; other cases retain defaults.',
                'checks':['no writes before review','exact ordered tools','earlier dependencies only','canonical execution receipts','no duplicate dispatch','server conversation follow-up']})
    return result


def manifest():
    rows=cases();encoded=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
    return {'version':VERSION,'dataset_sha256':hashlib.sha256(encoded).hexdigest(),'conversations':len(rows),
        'user_messages':sum(len(c['messages'])+bool(c['receipt_question']) for c in rows),'cases':rows,
        'limits':'Authored synthetic acceptance conversations; not independent human evaluation, production success estimates, training data, or a ClickUp leaderboard.',
        'clickup':{'status':'not_tested','references':REFERENCES}}
