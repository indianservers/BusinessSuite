"""Lead proposals use existing review, canonical CRM rules and execution receipts."""
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,approve,tick
from tests.test_suite_conversations import create,say,ROOT
from app.ai_operator.local_nlp import parse,contexts
from app.ai_operator.local_dialogue import continue_action
from app.ai_operator.crm_lead_actions import LeadCreate,LeadFields,LeadConvert,proposal
from app.ai_operator.suite_tools import TOOLS,validate_payload,catalog
from app.ai_operator.suite_models import SuiteRun
from app.ai_agents.security import company
from app.apps.crm.models import CRMLead,CRMCompany,CRMContact
from ai_test_utils import auth_headers


@pytest.mark.parametrize('text,name',[
    ('CRM: create a lead','leads.create'),('Please add a CRM lead name: "Asha Rao", email: asha@example.com','leads.create'),
    ('Update lead #12 email: asha@example.com','leads.update'),('Edit the lead #12 job title: Sales Manager','leads.update'),
    ('Qualify lead #12','leads.qualify'),('Convert lead #12 to a customer','leads.convert'),
])
def test_explicit_local_lead_grammar(text,name):
    value=parse(text,'CRM')
    assert value.intent==name and value.question is None
    if name!='leads.create':assert contexts(value)==[{'tool':'crm.lead_qualification' if name=='leads.qualify' else 'crm.lead','record_id':12}]


@pytest.mark.parametrize('payload',[
    {},{'full_name':'Asha Rao'},{'first_name':' ','full_name':' '},
    {'first_name':'Asha','full_name':'Asha Rao','organization_id':2},
    {'first_name':'Asha','full_name':'Asha Rao','lead_score':100},
    {'first_name':'Asha','full_name':'Asha Rao','email':'invalid'},
    {'first_name':'Asha','full_name':'Asha Rao','status':'Converted'},
])
def test_lead_creation_rejects_invalid_or_protected_fields(payload):
    with pytest.raises(ValueError):LeadCreate.model_validate(payload)


@pytest.mark.parametrize('payload',[{}, {'status':None},{'full_name':' '},{'is_converted':True},{'lead_score':100},{'status':'Converted'}])
def test_lead_update_is_typed_and_cannot_bypass_conversion(payload):
    with pytest.raises(ValueError):LeadFields.model_validate(payload)


def test_conversion_choices_are_explicit_and_dates_typed():
    with pytest.raises(ValueError):LeadConvert.model_validate({})
    with pytest.raises(ValueError):LeadConvert.model_validate({'createContact':False,'createCompany':False,'createDeal':False})
    with pytest.raises(ValueError):LeadConvert.model_validate({'createContact':True,'createCompany':True,'createDeal':False,'expectedCloseDate':'not a date'})
    assert LeadConvert(createContact=True,createCompany=True,createDeal=False).createDeal is False
    names={row['name'] for row in catalog()}
    assert {'crm.create_lead','crm.update_lead','crm.qualify_lead','crm.convert_lead'}<=names


def test_local_followups_do_not_treat_acknowledgement_as_name_or_approval():
    intent=parse('Create a lead','CRM')
    assert proposal(intent,[])['question']
    prior={'intent':intent.intent,'slots':intent.slots,'module':'CRM'}
    reply=continue_action(parse('yes','CRM'),prior,'yes','Asia/Kolkata')
    assert reply.question and not reply.slots.get('values')
    reply=continue_action(parse('name: "Asha Rao"','CRM'),prior,'name: "Asha Rao"','Asia/Kolkata')
    draft=proposal(reply,[])
    assert draft['steps']==[{'tool':'crm.create_lead','payload':{'first_name':'Asha','full_name':'Asha Rao'}}]
    cancelled=continue_action(parse('cancel','CRM'),prior,'cancel','Asia/Kolkata')
    assert cancelled.intent=='cancelled'


def test_giant_or_wrong_record_id_cannot_become_a_lead_selection():
    value=parse('Qualify lead #'+('9'*5000),'CRM')
    assert value.question and not value.slots.get('record_id')
    value=parse('Update lead','CRM');proposal(value,[])
    prior={'intent':value.intent,'slots':value.slots,'module':'CRM'}
    follow=continue_action(parse('task #12','CRM'),prior,'task #12','Asia/Kolkata')
    assert follow.question and not follow.slots.get('record_id')


def native_lead(client,h):
    r=client.post('/api/v1/crm/leads',headers=h,json={'first_name':'Asha','full_name':'Asha Rao','email':f'{uuid4()}@example.com','company_name':'Synthetic QA Company'})
    assert r.status_code==201,r.text
    return r.json()['id']


def final(client,h,ident):
    r=client.get(ROOT+f'/runs/{ident}',headers=h)
    assert r.status_code==200,r.text
    return r.json()


def test_local_lead_conversation_restores_details_and_creates_only_after_review(client,db):
    h,user,_,_=setup_suite(client,db);chat=create(client,h)
    first=say(client,h,chat,'CRM: create a lead')
    assert first['status']=='needs_clarification'
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).json()['runs'][0]['result']['local_nlp']['intent']=='leads.create'
    ambiguous=say(client,h,chat,'yes')
    assert ambiguous['status']=='needs_clarification' and not ambiguous['plan']['steps']
    draft=say(client,h,chat,'name: "Asha Rao", email: asha@example.com, company: Synthetic QA Company')
    assert draft['status']=='awaiting_approval' and not draft['receipts']
    assert db.query(CRMLead).count()==0
    approve(client,h,draft);tick(client,db)
    completed=final(client,h,draft['id'])
    assert completed['status']=='succeeded',completed
    assert db.query(CRMLead).one().full_name=='Asha Rao'
    approve(client,h,completed);assert tick(client,db)==0
    assert db.query(CRMLead).count()==1


def test_typed_workflow_creates_qualifies_and_converts_with_receipt_dependencies(client,db):
    h,user,_,_=setup_suite(client,db)
    draft=prepare(client,h,[
        {'tool':'crm.create_lead','payload':{'first_name':'Asha','full_name':'Asha Rao','email':f'{uuid4()}@example.com','company_name':'Synthetic Conversion Company'}},
        {'tool':'crm.qualify_lead','record_id':{'$step':1,'field':'id'},'payload':{'values':{'status':'Qualified'}}},
        {'tool':'crm.convert_lead','record_id':{'$step':1,'field':'id'},'payload':{'createContact':True,'createCompany':True,'createDeal':False}},
    ])
    assert draft['status']=='awaiting_approval',draft
    assert db.query(CRMLead).count()==0
    approve(client,h,draft);tick(client,db)
    completed=final(client,h,draft['id'])
    assert completed['status']=='succeeded',completed
    assert len(completed['receipts'])==3
    assert db.query(CRMLead).one().is_converted
    assert db.query(CRMCompany).count()==1
    assert db.query(CRMContact).count()==1
    approve(client,h,completed);assert tick(client,db)==0
    assert db.query(CRMCompany).count()==1


def test_local_update_and_conversion_collect_fixed_target_and_creation_choices(client,db):
    h,user,_,_=setup_suite(client,db);ident=native_lead(client,h);chat=create(client,h)
    draft=say(client,h,chat,f'Update lead #{ident} job title: Sales Manager')
    assert draft['status']=='awaiting_approval',draft
    assert db.get(CRMLead,ident).job_title!='Sales Manager'
    approve(client,h,draft);tick(client,db)
    assert final(client,h,draft['id'])['status']=='succeeded'
    db.expire_all();assert db.get(CRMLead,ident).job_title=='Sales Manager'
    question=say(client,h,chat,f'Convert lead #{ident} to customer')
    assert question['status']=='needs_clarification'
    draft=say(client,h,chat,'contact and customer')
    assert draft['status']=='awaiting_approval',draft
    assert draft['plan']['steps'][0]['payload']=={'createContact':True,'createCompany':True,'createDeal':False}
    assert not db.get(CRMLead,ident).is_converted


def test_stale_lead_update_pauses_without_overwriting_other_changes(client,db):
    h,user,_,_=setup_suite(client,db);ident=native_lead(client,h)
    draft=prepare(client,h,[{'tool':'crm.update_lead','record_id':ident,'payload':{'job_title':'Sales Manager'}}])
    approve(client,h,draft)
    assert client.patch(f'/api/v1/crm/leads/{ident}',headers=h,json={'notes':'Changed after preview'}).status_code==200
    tick(client,db);completed=final(client,h,draft['id'])
    assert completed['status']=='paused',completed
    db.expire_all();assert db.get(CRMLead,ident).job_title!='Sales Manager'


def test_read_only_user_cannot_prepare_lead_mutation(client,db):
    setup_suite(client,db)
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    draft=prepare(client,headers,[{'tool':'crm.create_lead','payload':{'first_name':'Asha','full_name':'Asha Rao'}}])
    assert draft['status']=='failed' and not draft['approval_id']
    assert db.query(CRMLead).count()==0


def test_local_qualification_collects_facts_and_respects_configured_requirements(client,db):
    from copy import deepcopy
    from app.apps.crm.lead_management import DEFAULTS
    from app.apps.crm.lead_models import CRMLeadManagementConfig,CRMLeadOperatingState
    h,user,_,_=setup_suite(client,db);ident=native_lead(client,h)
    settings=deepcopy(DEFAULTS)
    settings['stages'][2]['required']=['need','budget','decisionMaker','timeline']
    db.add(CRMLeadManagementConfig(organization_id=company(user),settings_json=settings));db.commit()
    blocked=prepare(client,h,[{'tool':'crm.qualify_lead','record_id':ident,'payload':{'values':{'status':'Qualified'}}}])
    assert blocked['status']=='awaiting_approval',blocked
    approve(client,h,blocked);tick(client,db)
    rejected=final(client,h,blocked['id'])
    # Existing Suite policy conservatively reconciles every dispatched write.
    assert rejected['status']=='needs_reconciliation' and rejected['error_code']=='CANONICAL_STEP_422',rejected
    assert not rejected['receipts']
    db.expire_all();assert db.get(CRMLead,ident).status!='Qualified'
    chat=create(client,h)
    question=say(client,h,chat,f'Qualify lead #{ident}')
    assert question['status']=='needs_clarification'
    draft=say(client,h,chat,'need: CRM deployment, budget: 10000 INR, decision maker: Owner, timeline: Next month')
    assert draft['status']=='awaiting_approval',draft
    step=draft['plan']['steps'][0]
    assert step['tool']=='crm.qualify_lead'
    assert step['payload']['details']['qualification']['decisionMaker']=='Owner'
    assert db.get(CRMLead,ident).status!='Qualified'
    approve(client,h,draft);tick(client,db)
    completed=final(client,h,draft['id'])
    assert completed['status']=='succeeded',completed
    db.expire_all();assert db.get(CRMLead,ident).status=='Qualified'
    state=db.query(CRMLeadOperatingState).filter_by(lead_id=ident).one()
    assert state.data_json['qualification']['budget']=='10000 INR'


def test_qualification_source_minimizes_operating_details_and_links_to_crm():
    from app.ai_operator.suite_tools import minimize_source
    from app.ai_operator.evidence import source_link
    value=minimize_source('crm.lead_qualification',{'id':12,'version':3,'details':{
        'qualification':{'need':'CRM','budget':'10000','secret':'hidden'},'assignmentReason':'private unrelated note'}})
    assert value['qualification']=={'need':'CRM','budget':'10000'}
    assert 'details' not in value
    assert source_link('crm.lead_qualification',value)=='/crm/leads'


def test_lead_specialists_advertise_current_reviewed_actions():
    from app.ai_operator.agent_templates import templates
    items={row['id']:row for row in templates()}
    assert {'crm.create_lead','crm.update_lead','crm.qualify_lead','crm.convert_lead','crm.lead_qualification'}<=set(items['crm-sales']['tools'])
    assert {'crm.qualify_lead','crm.lead_qualification'}<=set(items['lead-qualification']['tools'])
    assert items['crm-sales']['version']==3


def test_qualification_collects_multiple_followups_and_preserves_existing_facts():
    from app.ai_operator.local_nlp import Interpretation
    context=[{'tool':'crm.lead_qualification','records':{'id':12,'version':3,'qualification':{'need':'Existing CRM requirement'}}}]
    intent=parse('Qualify lead #12','CRM')
    assert proposal(intent,context)['question']
    for text in ('budget: 10000 INR','decision maker: Owner'):
        prior={'module':'CRM','intent':intent.intent,'slots':intent.slots}
        intent=continue_action(Interpretation('CRM','unsupported'),prior,text,'Asia/Kolkata')
        assert proposal(intent,context)['question']
    prior={'module':'CRM','intent':intent.intent,'slots':intent.slots}
    intent=continue_action(Interpretation('CRM','unsupported'),prior,'timeline: Next month','Asia/Kolkata')
    draft=proposal(intent,context)
    payload=draft['steps'][0]['payload']
    assert payload['version']==3
    assert payload['details']['qualification']=={'need':'Existing CRM requirement','budget':'10000 INR','decisionMaker':'Owner','timeline':'Next month'}


def test_qualification_existing_facts_choice_does_not_replace_them_with_empty_values():
    from app.ai_operator.local_nlp import Interpretation
    intent=parse('Qualify lead #12','CRM')
    context=[{'tool':'crm.lead_qualification','records':{'id':12,'version':3}}]
    proposal(intent,context)
    prior={'module':'CRM','intent':intent.intent,'slots':intent.slots}
    intent=continue_action(Interpretation('CRM','unsupported'),prior,'use only existing facts','Asia/Kolkata')
    assert proposal(intent,context)['steps'][0]['payload']=={'values':{'status':'Qualified'},'version':3}



def test_partial_lead_update_retains_selection_and_other_proposed_fields():
    from app.ai_operator.crm_lead_actions import continue_lead
    prior={'intent':'leads.update','slots':{'record_id':12,'values':{'job_title':'Manager','email':'old@example.com'}}}
    text='Update lead email: corrected@example.com'
    result=continue_lead(parse(text,'CRM'),prior,text)
    assert result.slots['record_id']==12
    assert result.slots['values']=={'job_title':'Manager','email':'corrected@example.com'}
    text='Update lead #13 email: other@example.com'
    result=continue_lead(parse(text,'CRM'),prior,text)
    assert result.slots['record_id']==13 and result.slots['values']=={'email':'other@example.com'}


def test_lead_fields_before_record_selection_are_retained_without_guessing():
    from app.ai_operator.crm_lead_actions import continue_lead
    prior={'intent':'leads.update','slots':{'_awaiting':'record_id','values':{'job_title':'Manager'}}}
    result=continue_lead(parse('email: corrected@example.com','CRM'),prior,'email: corrected@example.com')
    assert not result.slots.get('record_id')
    assert result.slots['values']=={'job_title':'Manager','email':'corrected@example.com'}
    result=continue_lead(parse('lead #12','CRM'),{'intent':'leads.update','slots':result.slots},'lead #12')
    assert result.slots['record_id']==12 and result.slots['values']['job_title']=='Manager'


def test_lead_early_fields_and_partial_restatement_use_native_reviewed_execution(client,db):
    h,user,_,_=setup_suite(client,db)
    draft=prepare(client,h,[{'tool':'crm.create_lead','payload':{'first_name':'Synthetic','full_name':'Synthetic Lead','email':f'{uuid4()}@example.com'}}])
    approve(client,h,draft);tick(client,db)
    lead=db.query(CRMLead).one();ident=lead.id
    chat=create(client,h)
    value=say(client,h,chat,'CRM: update lead job title: Manager')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,'notes: Synthetic follow-up')
    assert value['status']=='needs_clarification' and not value['plan']['steps']
    value=say(client,h,chat,f'Update lead #{ident}')
    assert value['status']=='awaiting_approval'
    value=say(client,h,chat,'Update lead job title: Director')
    assert value['status']=='awaiting_approval'
    assert value['plan']['steps'][0]['record_id']==ident
    assert value['plan']['steps'][0]['payload']=={'job_title':'Director','notes':'Synthetic follow-up'}
    db.expire_all();assert db.get(CRMLead,ident).job_title is None
    approve(client,h,value);tick(client,db)
    assert final(client,h,value['id'])['status']=='succeeded'
    db.expire_all();assert db.get(CRMLead,ident).job_title=='Director'
