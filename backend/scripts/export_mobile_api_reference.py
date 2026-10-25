"""Export the registered API without starting the server or connecting to a database.

Run from the repository root with backend/venv/Scripts/python.exe.
Only docs/mobile-api-reference is written. No .env files or credentials are exported.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote
import warnings

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "mobile-api-reference"
METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
BASE = "https://businesssuite-rosy.vercel.app"


def main():
    # Fixed, non-secret configuration. Importing app does not run its lifespan.
    os.environ.update(INSTALLED_APPS="hrms,crm,project_management,srm,fam",
                      ENVIRONMENT="test", DATABASE_URL="postgresql+psycopg://reference:reference@127.0.0.1:5432/reference",
                      DATABASE_AUTO_MIGRATE="false", SEED_DEMO_DATA="false",
                      STORAGE_BACKEND="local", SERVERLESS="false")
    sys.path.insert(0, str(ROOT / "backend"))
    warnings.filterwarnings("ignore", message='Field "model_name" has conflict')
    from fastapi.routing import APIRoute, APIWebSocketRoute
    from app.main import app

    OUT.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    schema["servers"] = [{"url": BASE, "description": "Deployed host; verify module availability"},
                         {"url": "http://localhost:1534", "description": "Repository start-backend.cmd"},
                         {"url": "http://10.0.2.2:1534", "description": "Android emulator to host backend"}]
    schemas = schema.get("components", {}).get("schemas", {})
    generated = datetime.now(timezone.utc).isoformat()

    def write_json(name, data):
        (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def source(endpoint):
        endpoint = inspect.unwrap(endpoint)
        try:
            return {"file": Path(inspect.getsourcefile(endpoint)).resolve().relative_to(ROOT).as_posix(),
                    "line": inspect.getsourcelines(endpoint)[1],
                    "handler": endpoint.__name__}
        except (TypeError, ValueError, OSError):
            return {}

    def dependencies(dep, seen=None):
        seen = set() if seen is None else seen
        result = []
        for child in dep.dependencies:
            call = child.call
            if id(call) in seen:
                continue
            seen.add(id(call))
            name = getattr(call, "__name__", type(call).__name__)
            entry = {"name": name}
            if hasattr(call, "permissions"):
                entry["any_of_permissions"] = sorted(call.permissions)
            result.append(entry)
            result.extend(dependencies(child, seen))
        return result

    def group(path):
        part = path.removeprefix("/api/v1/").split("/")[0]
        if part in {"crm", "srm", "fam", "project-management", "ai-operator"}:
            return part
        if part in {"auth", "users"}:
            return "authentication-and-users"
        if part in {"automation", "customization", "communication", "analytics", "ai-copilot", "admin-security", "saas", "business-os", "ai-agents", "approval-os", "workflow-engine", "scheduling", "scheduled-jobs", "logs"}:
            return "shared-platform"
        if not path.startswith("/api/v1/"):
            return "system"
        return "hrms-and-shared-services"

    def resolve(s):
        return schemas.get(s.get("$ref", "").rsplit("/", 1)[-1], s)

    def typename(s):
        if not s:
            return "unspecified (no typed contract)"
        if "$ref" in s:
            return s["$ref"].rsplit("/", 1)[-1]
        if "anyOf" in s or "oneOf" in s:
            return " | ".join(typename(v) for v in s.get("anyOf", s.get("oneOf", [])))
        if s.get("type") == "array":
            return "array<" + typename(s.get("items", {})) + ">"
        result = s.get("type", "object")
        if s.get("format"):
            result += " (" + s["format"] + ")"
        if "enum" in s:
            result += " enum=" + json.dumps(s["enum"], ensure_ascii=False)
        return result

    def fields(s):
        s = resolve(s)
        return [{"name": name, "required": name in s.get("required", []), "schema": spec}
                for name, spec in s.get("properties", {}).items()]

    route_map = {}
    hidden, sockets, registered_sources = [], [], set()
    for route in app.routes:
        if not isinstance(route, (APIRoute, APIWebSocketRoute)):
            continue
        src = source(route.endpoint)
        if src:
            registered_sources.add((src["file"], src["handler"]))
        if isinstance(route, APIWebSocketRoute):
            sockets.append({"path": route.path, "source": src, "description": inspect.getdoc(route.endpoint) or ""})
        elif not route.include_in_schema:
            hidden.append({"path": route.path, "methods": sorted(route.methods), "source": src,
                           "parameters": [{"name": p.name, "required": p.required} for p in route.dependant.query_params]})
        else:
            for method in route.methods:
                route_map[(method.lower(), route.path)] = route

    operations, counts, missing = [], Counter(), []
    for path, item in sorted(schema["paths"].items()):
        for method, op in sorted(item.items()):
            if method not in METHODS:
                continue
            route = route_map[(method, path)]
            deps = dependencies(route.dependant)
            required_auth = any(d["name"] == "get_current_user" for d in deps)
            body = op.get("requestBody", {})
            responses = op.get("responses", {})
            untyped = any(not media.get("schema") for code, response in responses.items()
                          if code.startswith("2") for media in response.get("content", {}).values())
            if untyped:
                missing.append({"method": method.upper(), "path": path})
            record = {"method": method.upper(), "path": path, "group": group(path),
                      "tags": op.get("tags", []), "operation_id": op.get("operationId"),
                      "summary": op.get("summary", route.name.replace("_", " ")),
                      "description": op.get("description", ""),
                      "url_template": BASE + path,
                      "swagger_url": BASE + "/api/v1/docs#/" + quote((op.get("tags") or ["default"])[0], safe="") + "/" + op["operationId"],
                      "source": source(route.endpoint),
                      "auth": "Bearer access token" if required_auth else "No get_current_user dependency; check handler-specific credentials",
                      "security": op.get("security", []), "dependencies": deps,
                      "parameters": op.get("parameters", []), "request_body": body,
                      "request_fields": {media: fields(spec.get("schema", {})) for media, spec in body.get("content", {}).items()},
                      "responses": responses, "untyped_success_response": untyped,
                      "deprecated": op.get("deprecated", False)}
            operations.append(record)
            counts[record["group"]] += 1

    # Inventory route declarations outside the registered main app. Paths here
    # are decorator-local and intentionally not represented as callable suite URLs.
    unmounted = []
    for file in sorted((ROOT / "backend" / "app").rglob("*.py")):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeError):
            continue
        rel = file.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                kind = dec.func.attr
                if kind not in METHODS | {"route", "api_route", "websocket"} or not dec.args:
                    continue
                if (rel, node.name) in registered_sources:
                    continue
                try:
                    local_path = ast.literal_eval(dec.args[0])
                except (ValueError, TypeError):
                    continue
                methods = [kind.upper()]
                for kw in dec.keywords:
                    if kw.arg == "methods":
                        methods = ast.literal_eval(kw.value)
                if kind == "route" and methods == ["ROUTE"]:
                    methods = ["GET"]
                unmounted.append({"declared_path": local_path, "methods": methods,
                                  "source": {"file": rel, "line": node.lineno, "handler": node.name},
                                  "description": ast.get_docstring(node) or node.name.replace("_", " "),
                                  "status": "Not registered in the main FastAPI app with all five product modules enabled; may belong to a separate app"})

    write_json("openapi.json", schema)
    write_json("endpoints.json", {"generated_at_utc": generated, "source": "Current working tree; all five product modules enabled; no lifespan executed",
                                 "base_url": BASE, "counts": dict(sorted(counts.items())),
                                 "http_operations": operations, "hidden_http_routes": hidden, "websocket_routes": sockets})
    write_json("unmounted-route-declarations.json", unmounted)

    def compact(s):
        return json.dumps(s, ensure_ascii=False, separators=(",", ":"))

    lines = ["# Business Suite backend endpoint catalog", "",
             "Reference for iOS and Android implementation. Generated from the current registered FastAPI application with HRMS, CRM, Project Management, SRM, and FAM enabled.", "",
             f"{len(operations):,} HTTP operations; {len(sockets)} WebSocket route(s); {len(hidden)} hidden application HTTP route(s).", "",
             "[Mobile integration guide](README.md) · [OpenAPI schemas](openapi.json) · [Machine-readable endpoint details](endpoints.json) · [Postman collection](postman.collection.json)", "",
             "Paths already include `/api/v1`. Prefix them with the origin only. URL templates contain placeholders: substitute IDs and URL-encode values before calling. Swagger links open documentation, not mutations.", "",
             "Descriptions use declared summaries/docstrings. When no docstring exists the summary is the handler-derived label; inspect the linked source for business rules. Auth metadata identifies dependencies and declared security, not a complete authorization policy. Responses list declared status codes; handlers and middleware can return additional errors.", "",
             "An unspecified response means the backend does not declare a typed schema. Do not generate a concrete mobile DTO from it; inspect the handler or validate a staging response. Detailed constraints, nested definitions and references are retained in openapi.json.", "", "## Modules", ""]
    for key, count in sorted(counts.items()):
        lines.append(f"- [{key}](#{key}): {count:,} operations")
    for key in sorted(counts):
        lines.extend(["", f"## {key}", ""])
        for r in (r for r in operations if r["group"] == key):
            lines.extend([f"### {r['method']} {r['path']}", "", r["summary"], ""])
            if r["description"]:
                lines.extend([r["description"], ""])
            src = r["source"]
            lines.extend([f"- URL template: `{r['url_template']}`",
                          f"- Links: [Swagger operation]({r['swagger_url']}) · [Handler source](../../{src['file']}#L{src['line']})",
                          f"- Auth: {r['auth']}.", f"- Tags: {', '.join(r['tags']) or 'default'}."])
            checks = [d for d in r["dependencies"] if d.get("any_of_permissions") or d["name"] == "get_current_active_superuser"]
            for check in checks:
                lines.append("- Declared access dependency: " + compact(check))
            if r["parameters"]:
                lines.extend(["", "Parameters:", ""])
                for p in r["parameters"]:
                    lines.append(f"- `{p['name']}` ({p['in']}; {'required' if p.get('required') else 'optional'}): `{compact(p.get('schema', {}))}`" + (" — " + p["description"] if p.get("description") else ""))
            if r["request_body"]:
                lines.extend(["", "Request body (" + ("required" if r["request_body"].get("required") else "optional") + "):", ""])
                for media, spec in r["request_body"].get("content", {}).items():
                    lines.append(f"- `{media}`: `{typename(spec.get('schema', {}))}`")
                    for f in r["request_fields"][media]:
                        lines.append(f"  - `{f['name']}` ({'required' if f['required'] else 'optional'}): `{compact(f['schema'])}`")
            lines.extend(["", "Declared responses:", ""])
            for code, resp in r["responses"].items():
                content = resp.get("content", {})
                details = "; ".join(media + ": " + typename(spec.get("schema", {})) for media, spec in content.items())
                lines.append(f"- `{code}` {resp.get('description', '')}" + (" — " + details if details else " — no response body schema declared"))
            lines.append("")
    lines.extend(["## Additional registered routes", ""])
    for r in hidden + sockets:
        src = r["source"]
        lines.append(f"- `{','.join(r.get('methods', ['WEBSOCKET']))} {r['path']}` — [source](../../{src['file']}#L{src['line']}). See mobile guide for transport and signed-file behavior.")
    lines.extend(["", "## Route files outside the main app", "",
                  f"[Unmounted declarations](unmounted-route-declarations.json) contains {len(unmounted)} decorator declarations found in source but not registered in the main app. These include the separate legacy inventory application. Their paths are local to the declaring router or blueprint; do not call them as suite endpoints without a separate deployment contract.", ""])
    (OUT / "ENDPOINTS.md").write_text("\n".join(lines), encoding="utf-8")

    folders = []
    for key in sorted(counts):
        requests = []
        for r in (r for r in operations if r["group"] == key):
            raw_path = re.sub(r"\{([^}]+)\}", r":\1", r["path"])
            params = [{"key": p["name"], "value": str(p.get("schema", {}).get("default", "")),
                       "disabled": not p.get("required", False), "description": compact(p.get("schema", {}))}
                      for p in r["parameters"] if p["in"] == "query"]
            url = {"raw": "{{origin}}" + raw_path + ("?" + "&".join(p["key"] + "=" + p["value"] for p in params if not p["disabled"]) if any(not p["disabled"] for p in params) else ""),
                   "host": ["{{origin}}"], "path": raw_path.lstrip("/").split("/"), "query": params,
                   "variable": [{"key": name, "value": "", "description": "Replace with an accessible resource ID"} for name in re.findall(r"\{([^}]+)\}", r["path"])]}
            request = {"method": r["method"], "url": url, "header": [],
                       "description": r["summary"] + "\n\n" + r["description"] + "\n\n" + r["auth"] + "\n\nSwagger: " + r["swagger_url"]}
            if "Bearer" not in r["auth"]:
                request["auth"] = {"type": "noauth"}
            content = r["request_body"].get("content", {})
            if "application/json" in content:
                request["header"].append({"key": "Content-Type", "value": "application/json"})
                request["body"] = {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}
                request["description"] += "\n\nFill JSON body from the OpenAPI request schema; {} is a placeholder, not a valid example."
            elif "multipart/form-data" in content:
                request["body"] = {"mode": "formdata", "formdata": [{"key": f["name"], "type": "file" if f["schema"].get("format") == "binary" else "text", "disabled": not f["required"]} for f in r["request_fields"].get("multipart/form-data", [])]}
            elif "application/x-www-form-urlencoded" in content:
                request["body"] = {"mode": "urlencoded", "urlencoded": [{"key": f["name"], "value": "", "disabled": not f["required"]} for f in r["request_fields"].get("application/x-www-form-urlencoded", [])]}
            requests.append({"name": r["method"] + " " + r["path"], "request": request, "response": []})
        folders.append({"name": key, "item": requests})
    write_json("postman.collection.json", {"info": {"name": "Business Suite mobile backend reference", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json", "description": "All registered HTTP operations. Configure origin and access_token, fill path/query/body placeholders. Contains destructive/admin operations: run requests individually against authorized test data. No credentials or automatic execution scripts included."},
                                           "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
                                           "variable": [{"key": "origin", "value": BASE}, {"key": "access_token", "value": ""}], "item": folders})

    # Validate coverage, uniqueness, JSON references and source targets before delivery.
    keys = [(r["method"], r["path"]) for r in operations]
    assert len(keys) == len(set(keys)) == len(route_map)
    assert sum(len(f["item"]) for f in folders) == len(operations)
    def validate_refs(value):
        if isinstance(value, dict):
            if "$ref" in value and value["$ref"].startswith("#/"):
                target = schema
                for part in value["$ref"][2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                validate_refs(child)
        elif isinstance(value, list):
            for child in value:
                validate_refs(child)
    validate_refs(schema)
    for r in operations:
        assert (ROOT / r["source"]["file"]).is_file()
    manifest = {"generated_at_utc": generated, "http_operations": len(operations), "paths": len(schema["paths"]),
                "groups": dict(sorted(counts.items())), "schemas": len(schemas),
                "hidden_http_routes": hidden, "websocket_routes": sockets,
                "unmounted_route_declarations": len(unmounted),
                "untyped_success_responses": len(missing), "untyped_operations": missing,
                "validation": "Operation coverage, uniqueness, source file targets, Postman count and local schema references passed. No business API calls or database startup executed."}
    write_json("manifest.json", manifest)
    if "--check-deployed" in sys.argv:
        import httpx
        checks = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "origin": BASE,
                  "scope": "Unauthenticated documentation reads only; no business handlers or mutations tested"}
        try:
            with httpx.Client(timeout=45, follow_redirects=True) as client:
                checks["docs_status"] = client.get(BASE + "/api/v1/docs").status_code
                response = client.get(BASE + "/api/v1/openapi.json")
                checks["openapi_status"] = response.status_code
                response.raise_for_status()
                deployed = response.json()
            local_keys = set(keys)
            deployed_keys = {(m.upper(), p) for p, item in deployed["paths"].items() for m in item if m in METHODS}
            checks.update(deployed_http_operations=len(deployed_keys),
                          local_only_operations=[{"method": m, "path": p} for m, p in sorted(local_keys - deployed_keys)],
                          deployed_only_operations=[{"method": m, "path": p} for m, p in sorted(deployed_keys - local_keys)],
                          shared_operations=len(local_keys & deployed_keys))
            inventory = json.loads((OUT / "endpoints.json").read_text(encoding="utf-8"))
            catalog = (OUT / "ENDPOINTS.md").read_text(encoding="utf-8")
            for record in inventory["http_operations"]:
                present = (record["method"], record["path"]) in deployed_keys
                record["deployment_path_present"] = present
                if not present:
                    heading = f"### {record['method']} {record['path']}\n"
                    catalog = catalog.replace(heading, heading + "\n**Deployment:** Absent from the deployed OpenAPI snapshot. Requires deployment before mobile can use this route on the linked host.\n", 1)
            write_json("endpoints.json", inventory)
            catalog = catalog.replace("## Modules\n", f"Deployment comparison: {len(deployed_keys):,} operations on the deployed host; {len(local_keys - deployed_keys)} operations exist only in this local export. Those entries are marked below. See [comparison snapshot](deployment-check.json) for the check time.\n\n## Modules\n", 1)
            (OUT / "ENDPOINTS.md").write_text(catalog, encoding="utf-8")
        except (httpx.HTTPError, ValueError, KeyError) as error:
            checks["error"] = type(error).__name__
        write_json("deployment-check.json", checks)
        print(json.dumps(checks, indent=2))
    print(json.dumps({key: value for key, value in manifest.items() if key not in {"untyped_operations", "hidden_http_routes", "websocket_routes"}}, indent=2))


if __name__ == "__main__":
    main()
