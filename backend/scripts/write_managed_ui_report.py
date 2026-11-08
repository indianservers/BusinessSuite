"""Keep workflow evidence separate from control inventories and universal sign-off."""
import csv,json,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"outputs/conditional-121"
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def main():
    pages=read(ROOT/"outputs/project-ux-20261107/pages.json");routes={p["route"] for p in pages};latest={}
    for file in [OUT/"native-results.json",*sorted(OUT.glob("managed-*-results.json"))]:
        for row in read(file):
            previous=latest.get(row["title"])
            if previous is None or row.get("verifiedAt","")>previous.get("verifiedAt",""):
                row={**row,"evidence_file":str(file.relative_to(ROOT))}
                # Older reporters stored the requested profile, including in tests
                # that deliberately switch to readers or portal sessions.
                if "actor" in row:row["requestedProfile"]=row.pop("actor")
                latest[row["title"]]=row
    def targets(row):
        found=set(row.get("pages",[]));title=row["title"]
        found.update(re.findall(r"/[\w/-]+",title))
        for prefix,path in [("Customization ","/admin/customization/"),("Inventory ","/srm/inventory/"),("Sales ","/srm/")]:
            if title.startswith(prefix):found.add(path+title[len(prefix):].split()[0])
        if title.startswith("FAM parties "):found.add("/fam/parties")
        if title.startswith("FAM banking "):found.add("/fam/banking")
        if title.startswith("Customer portal "):found.update(r for r in routes if r.startswith("/portal/customer"))
        if title.startswith("Partner portal "):found.update(r for r in routes if r.startswith("/portal/partner") and not r.endswith("/commissions"))
        matched=set()
        for value in found:
            candidates=[r for r in routes if value==r or value.startswith(r+"/")]
            if candidates:matched.add(max(candidates,key=len))
        return matched
    reference_file=OUT/"managed-reference-complete.json"
    refs={r["route"]:r for r in read(reference_file if reference_file.exists() else OUT/"managed-reference-workflows.json")}
    roles={role:read(OUT/f"role-{role}.json") for role in ("creator","editor","approver","configurer","deleter","assigner")}
    baseline={r["page"]:r for r in read(ROOT/"outputs/crud-permissions-121-final/page-results.json")}
    matrix=[]
    for page in pages:
        route=page["route"];cases=[r for r in latest.values() if route in targets(r)];ref=refs.get(route)
        observations={role:next((r for r in rows if r["page"]==route),{}) for role,rows in roles.items()}
        failures=[r["title"] for r in cases if r["status"]!="passed"]
        if ref and ref["status"]=="failed":failures.append(ref.get("error","Reference UI workflow failed"))
        failures.extend(role+" role control audit: "+(r.get("error") or "; ".join(c["action"] for c in r.get("checks",[]) if not c.get("passed"))) for role,r in observations.items() if r.get("result")=="failed")
        matrix.append({"module":page["module"],"page":route,"baseline_own_ui_workflow":baseline.get(route,{}).get("workflow_verified"),"native_workflows":[{"title":r["title"],"status":r["status"],"verifiedAt":r.get("verifiedAt"),"evidence":r["evidence_file"],"uiWrites":r.get("uiWrites",[])} for r in cases],"managed_reference_workflow":ref,"role_control_observations":{role:{"result":r.get("result"),"checks":len(r.get("checks",[]))} for role,r in observations.items()},"unresolved_recorded_cases":failures,"meta_actions_excluded":route.startswith("/crm/whatsapp")})
    def titles(suite):
        yield from (s["title"] for s in suite.get("specs",[]))
        for child in suite.get("suites",[]):yield from titles(child)
    catalog=read(OUT/"managed-workflow-catalog.json");planned=list(titles(catalog))
    pending=[title for title in planned if title not in latest or latest[title]["status"]!="passed"]
    summary={"generatedAt":datetime.now(timezone.utc).isoformat(),"target":"http://127.0.0.1:1582","pageCount":len(matrix),"latestNativeCaseResults":dict(Counter(r["status"] for r in latest.values())),"plannedManagedWorkflows":len(planned),"plannedManagedCasesNotPassing":pending,"referencePageResults":dict(Counter(r["status"] for r in refs.values())),"unresolvedRecordedCases":[{"page":r["page"],"cases":r["unresolved_recorded_cases"]} for r in matrix if r["unresolved_recorded_cases"]],"allActionsStatesAndRolesCertified":False,"coverageNote":"Recorded native workflows, baseline workflows, and role-control observations are separate evidence; they do not certify every possible action/state/role combination.","exclusions":["Meta-dependent actions","Live email delivery"],"backendRegressions":"90 passed; backend-message-guard.log","frontendTypecheck":"types-message-guard.log","frontendBuild":"build-message-guard.log"}
    (OUT/"managed-verification-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUT/"managed-page-wise-verification.json").write_text(json.dumps(matrix,indent=2),encoding="utf-8")
    (OUT/"managed-native-latest.json").write_text(json.dumps(list(latest.values()),indent=2),encoding="utf-8")
    with (OUT/"managed-page-wise-verification.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["page","module","baseline_own_ui_workflow","native_workflows","managed_reference_result","role_control_observations","unresolved_recorded_cases"]);writer.writeheader()
        for row in matrix:writer.writerow({"page":row["page"],"module":row["module"],"baseline_own_ui_workflow":row["baseline_own_ui_workflow"],"native_workflows":"; ".join(r["title"]+": "+r["status"] for r in row["native_workflows"]),"managed_reference_result":(row["managed_reference_workflow"] or {}).get("status",""),"role_control_observations":"; ".join(role+": "+str(observation["result"]) for role,observation in row["role_control_observations"].items()),"unresolved_recorded_cases":"; ".join(row["unresolved_recorded_cases"])})
    print(json.dumps({k:summary[k] for k in ["pageCount","latestNativeCaseResults","plannedManagedWorkflows","plannedManagedCasesNotPassing","referencePageResults"]},indent=2))
if __name__=="__main__":main()
