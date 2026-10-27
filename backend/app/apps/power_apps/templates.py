"""Versioned, deployment-owned template definitions; no module adapters are installed."""
import json
from copy import deepcopy
from pathlib import Path
from app.apps.power_apps.graph import VisualWorkflowDefinition

TEMPLATES = json.loads(Path(__file__).with_name("automation_templates.json").read_text(encoding="utf-8"))["templates"]
def connector_starter(key,name,actions):
    def node(id,kind,label,config,index):
        return dict(id=id,type=kind,label=label,position={"x":80+index*320,"y":160},config=config,credential_reference=None,advanced={"retry_attempts":1,"error_strategy":"stop","timeout_seconds":30})
    nodes=[node("webhook","webhook_trigger","Incoming webhook",{"event_name":key},0)]
    for i,(provider,action,input) in enumerate(actions,1):
        nodes.append(node("action_"+str(i),"connector_"+provider,provider.replace("_"," ").title(),{"action":action,"input":input,"confirm_write":False},i))
    edges=[dict(id="link_"+str(i),source=nodes[i-1]["id"],target=n["id"],source_port="out",target_port="in") for i,n in enumerate(nodes[1:],1)]
    return dict(id=key,name=name,description="Configure your connections and required fields, then explicitly authorize intended writes before publication. Starts with the existing signed webhook trigger.",version=1,category="Connected workflows",requires_configuration=True,executable=False,required_adapters=sorted({a[0] for a in actions}),definition=dict(schema_version=2,nodes=nodes,edges=edges))

TEMPLATES.extend([
    connector_starter("webhook-receiver","Signed webhook receiver",[]),
    connector_starter("webhook-sheets-email","Webhook to Google Sheets and email",[("google_sheets","append_rows",{"spreadsheet_id":"","range":"Sheet1!A:B","values":[["{{trigger.input.name}}","{{trigger.input.email}}"]]}),("smtp","send",{"recipient":"{{trigger.input.email}}","subject":"Submission received","text":"{{trigger.input.message}}"})]),
    connector_starter("webhook-groq-slack","Webhook to Groq and Slack",[("groq","generate_text",{"model":"","prompt":"{{trigger.input.message}}"}),("slack","send_message",{"channel":"","text":"{{steps.action_1.output.text}}"})]),
    connector_starter("forms-responses-email","Webhook to Google Forms responses and Gmail",[("google_forms","list_responses",{"form_id":"{{trigger.input.form_id}}"}),("gmail","send_mail",{"to":"{{trigger.input.email}}","subject":"Form response received","text":"Review the form response in your authorized workflow history."})]),
])

for item in TEMPLATES:
    VisualWorkflowDefinition.model_validate(item["definition"])

def template_by_id(key):
    return next((deepcopy(row) for row in TEMPLATES if row["id"] == key), None)
