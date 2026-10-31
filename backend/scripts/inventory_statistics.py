"""Reproducible source discovery, never a claim of runtime verification."""
import ast
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"backend/app/services/metrics/inventory.json"


def module(path):
    parts=path.parts
    if "apps" in parts:return {"project_management":"PMS","project-management":"PMS","hrms":"HRMS","interns_hub":"InternHub","crm":"CRM","srm":"Sales","fam":"Finance"}.get(parts[parts.index("apps")+1],parts[parts.index("apps")+1])
    return "HRMS" if "api/v1" in path.as_posix() else "Master Suite / shared"


def discover():
    rows=[];warnings=[]
    manifest=OUTPUT.with_name("reviewed_sources.json")
    annotations=json.loads(manifest.read_text(encoding="utf-8")).get("annotations",{}) if manifest.exists() else {}
    for path in sorted((ROOT/"backend/app").rglob("*.py")):
        if "/inventory/vyapara_erp/" in path.as_posix():
            # Included as a separate integrated module, not omitted.
            pass
        source=path.read_text(encoding="utf-8-sig",errors="replace")
        try:tree=ast.parse(source)
        except SyntaxError as error:
            warnings.append({"source":path.relative_to(ROOT).as_posix(),"error":str(error)});continue
        if "\ufffd" in source:warnings.append({"source":path.relative_to(ROOT).as_posix(),"error":"Invalid UTF-8 bytes replaced during discovery; manual source review required"})
        for node in ast.walk(tree):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            routes=[]
            for decorator in node.decorator_list:
                if isinstance(decorator,ast.Call) and isinstance(decorator.func,ast.Attribute) and decorator.func.attr in {"get","post","route"} and decorator.args and isinstance(decorator.args[0],ast.Constant):routes.append(str(decorator.args[0].value))
            if not routes:
                if path.relative_to(ROOT).as_posix()+":"+node.name in annotations:routes=["Internal statistics source"]
                else:continue
            body=ast.get_source_segment(source,node) or ""
            evidence=[line.strip()[:240] for line in body.splitlines() if re.search(r"func\.(count|sum|avg)|\.count\(|\blen\(|\bsum\(",line)]
            if not evidence and not re.search(r"dashboard|statistics|metrics|summary|analytics|count|stats|[\"\']total[\"\']|count_rows_before_page|canonical_inbox|run_report",node.name+" ".join(routes)+body,re.I):continue
            keys=sorted({key.value for item in ast.walk(node) if isinstance(item,ast.Dict) for key in item.keys if isinstance(key,ast.Constant) and isinstance(key.value,str) and re.search(r"total|count|active|pending|overdue|amount|value|completed|summary|headcount",key.value,re.I)})
            filters=sorted({n.id for n in ast.walk(node) if isinstance(n,ast.Name) and re.search(r"organization|company|workspace|project|department|date|scope|user",n.id)})
            rows.append({"id":path.relative_to(ROOT).as_posix()+":"+node.name,"module":module(path),"page":"API "+", ".join(routes),"metric":", ".join(keys) or node.name,"current_source":path.relative_to(ROOT).as_posix(),"line":node.lineno,"function":node.name,"filters":filters,"definition":"Existing endpoint business aggregate; inspect source and registry mapping before comparing","problem":"Discovered; runtime reconciliation not yet certified","fix":"Verify declared unit, deletion/status rules, permission scope, time period and pagination","verification":"discovered","evidence":evidence[:8]})
    pattern=re.compile(r"(?:<Kpi\b|<StatCard\b|<MetricCard\b|<CompactMetricCard\b|<StatsCard\b|title=.[^\n]*(?:Total|Active|Overdue|Pending)|\b(?:const|let)\s+\w*(?:[Cc]ount|[Tt]otal|[Mm]etric|[Ss]tats|[Pp]ipelineValue)\w*\s*=)")
    frontend_paths=sorted([*(ROOT/"frontend/src").rglob("*.tsx"),*(ROOT/"frontend/interns-hub/src").rglob("*.tsx")])
    for path in frontend_paths:
        if path.name=="StatisticsAuditPage.tsx":continue
        for line,text in enumerate(path.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
            if pattern.search(text):
                rows.append({"id":path.relative_to(ROOT).as_posix()+":"+str(line),"module":module(path),"page":path.stem,"metric":text.strip()[:260],"current_source":path.relative_to(ROOT).as_posix(),"line":line,"function":"render / derived value","filters":[],"definition":"UI candidate; trace to authoritative endpoint before comparison","problem":"Discovered; loaded-page, error fallback and cache scope require review","fix":"Use authoritative totals; label previews, units and context explicitly","verification":"discovered","evidence":[]})
    for path in sorted((ROOT/"Flutter-Apps/lib").rglob("*.dart")):
        for line,text in enumerate(path.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
            if re.search(r"(?:total|count|summary|statistics|metric|overdue|pending).*(?:Text\(|\.length|\[)|(?:Text\(|_Stat|_Metric).*(?:total|count|overdue|pending)",text,re.I):
                rows.append({"id":path.relative_to(ROOT).as_posix()+":"+str(line),"module":"Mobile / Flutter","page":path.stem,"metric":text.strip()[:260],"current_source":path.relative_to(ROOT).as_posix(),"line":line,"function":"mobile render / derived value","filters":[],"definition":"Mobile counter candidate; trace API and local filtering before reconciliation","problem":"Discovered; mobile runtime not certified in this audit","fix":"Compare same backend unit, tenant, filters and pagination context","verification":"discovered","evidence":[]})
    manifest=OUTPUT.with_name("reviewed_sources.json")
    annotations=json.loads(manifest.read_text(encoding="utf-8")).get("annotations",{}) if manifest.exists() else {}
    for row in rows:
        row.update(annotations.get(row["id"],{}))
    return {"reviewed_source_locations":sum(r["verification"]!="discovered" for r in rows),"schema_version":1,"method":"AST endpoint and frontend source discovery; candidates are not automatically verified", "components_discovered":len(rows),"discovery_warnings":warnings,"items":rows}


if __name__=="__main__":
    result=discover();OUTPUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(f"Discovered {len(result['items'])} statistics source locations; runtime verification tracked separately")
