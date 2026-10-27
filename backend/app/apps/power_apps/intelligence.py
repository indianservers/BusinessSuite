"""Portable authoring, quality and documentation using the existing graph contract."""
import json
import re
from copy import deepcopy
from uuid import uuid4
from app.apps.power_apps.graph import VisualWorkflowDefinition
from app.apps.power_apps.node_registry import NODES
from app.apps.power_apps.studio import validate_graph, topology
from app.apps.power_apps.authoring import bounded, redact_debug


def portable(definition):
    graph=VisualWorkflowDefinition.model_validate(definition).model_dump()
    ids={node["id"]:"node_"+uuid4().hex[:16] for node in graph["nodes"]}
    def remap(value):
        if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
        if isinstance(value,list):return [remap(v) for v in value]
        if isinstance(value,str):
            from app.ai_agents.services.advanced_security import AiDataRedactionService
            value=AiDataRedactionService().redact_text(value)
            return re.sub(r"(\{\{\s*steps\.)([A-Za-z_][A-Za-z0-9_-]*)(\.output)",lambda m:m[1]+ids.get(m[2],m[2])+m[3],value)
        return value
    graph=remap(graph)
    for node in graph["nodes"]:
        node["id"]=ids[node["id"]];node["credential_reference"]=None
        if node["type"]=="sub_workflow":node["config"]["workflow_id"]=""
    for edge in graph["edges"]:
        edge.update(id="edge_"+uuid4().hex[:16],source=ids[edge["source"]],target=ids[edge["target"]])
    for group in graph["groups"]:group.update(id="group_"+uuid4().hex[:16],node_ids=[ids[i] for i in group["node_ids"]])
    for note in graph["annotations"]:note["id"]="note_"+uuid4().hex[:16]
    if graph["block_contract"]:
        for p in graph["block_contract"]["inputs"]+graph["block_contract"]["outputs"]:p["node_id"]=ids[p["node_id"]]
    graph["block_references"]=[]
    return VisualWorkflowDefinition.model_validate(graph).model_dump()


def analyze(graph, name="Workflow", description="", version=0, history=None):
    validation=validate_graph(graph); _,incoming,outgoing,order,_=topology(graph)
    findings=list(validation["issues"])
    def finding(code,message,node=None):findings.append({"code":code,"message":message,"node_id":node,"severity":"warning"})
    if not description:finding("documentation","Add a purpose and expected inputs")
    if len(graph.nodes)>100:finding("complexity","Consider grouping or extracting reusable blocks")
    for node in graph.nodes:
        if not NODES[node.type]["trigger"] and node.type!="stop_workflow" and not any(e.source_port=="error" for e in outgoing[node.id]):finding("error_coverage","Design an error path or document the stop strategy",node.id)
        if not node.description:finding("node_documentation","Describe why this step is needed",node.id)
    penalties=sum(8 if f["severity"]=="error" else 1 if f["code"]=="runtime_unavailable" else 2 for f in findings)
    lines=[f"# {name}","",description or "Purpose not documented.","",f"Draft version: {version}. Design-time definition only; no live integrations are active.","","## Steps"]
    for key in order:
        node=next(n for n in graph.nodes if n.id==key);definition=NODES[node.type]
        lines += [f"- {node.label} ({definition['name']}): {node.description or definition['description']}","  Required inputs: "+", ".join(f["key"] for f in definition["fields"] if f["required"]),"  Declared outputs: "+json.dumps(definition["output_schema"]),"  Error strategy: "+node.advanced.error_strategy]
        if definition["requires_credential"]:lines.append("  Requires a separately authorized credential reference.")
        if not definition["preview_supported"]:lines.append("  Requires production executor / connector configuration.")
        if node.config.get("condition"):lines.append("  Condition: "+json.dumps(node.config["condition"]))
        elif node.type in {"if_else","compare_values","filter"}:lines.append("  Condition: "+json.dumps({key:node.config.get(key) for key in ["left","operator","right"]}))
        if node.type=="switch":lines.append("  Router cases: "+json.dumps(node.config.get("routes") or node.config.get("cases",{})))
        if node.type in {"loop","for_each","merge"}:lines.append("  Flow configuration: "+json.dumps(node.config))
        if node.mappings:lines.append("  Field mappings: "+json.dumps({key:value.model_dump() for key,value in node.mappings.items()}))
        for edge in outgoing[key]:lines.append(f"  Branch {edge.source_port}: {edge.target}")
    lines += ["","## Change history"]+[f"- Version {h['version']}: {h.get('name',name)}" for h in (history or [])]
    return {"validation":validation,"quality":{"score":max(0,100-penalties),"label":"Design quality, not a security certification or reliability guarantee","findings":findings},"documentation":redact_debug("\n".join(lines))}
