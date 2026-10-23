"""Inventory OpenAPI operations and perform a bounded read-only live sweep.

Supply credentials through SUITE_AUDIT_ACCOUNTS_JSON (module, email, password).
No response records, credentials or tokens are written to the report.
Mutations and authentication callbacks are inventoried but never invoked here.
"""
import argparse
import concurrent.futures
import csv
from datetime import date
import json
import os
from pathlib import Path
import re
import threading
import time

import httpx

METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def run(base, output, workers=4):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(base_url=base.rstrip("/"), timeout=40, follow_redirects=False)
    schema = client.get("/api/v1/openapi.json")
    schema.raise_for_status()
    schema = schema.json()
    accounts = json.loads(os.environ["SUITE_AUDIT_ACCOUNTS_JSON"])
    headers = {}
    for account in accounts:
        response = client.post("/api/v1/auth/login", json={key: account[key] for key in ["email", "password", "module"]})
        if response.status_code != 200:
            print(f"Account unavailable: {account['module']} ({response.status_code})", flush=True)
            continue
        headers[account["module"]] = {"Authorization": "Bearer " + response.json()["access_token"]}
    if not headers:
        raise RuntimeError("No audit account could authenticate")
    default_headers = headers.get("hrms", next(iter(headers.values())))
    rows = []
    resources = {}
    lock = threading.Lock()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in METHODS:
                continue
            module = path.split("/")[3] if path.startswith("/api/v1/") else "system"
            rows.append({"method": method.upper(), "path": path, "module": module,
                         "summary": operation.get("summary", ""), "status": "", "coverage": "not_executed",
                         "note": "Mutation: requires a dedicated safe fixture" if method != "get" else "Pending read probe",
                         "elapsed_ms": "", "_operation": operation})

    def parameter_value(parameter):
        name = parameter["name"]
        definition = parameter.get("schema", {})
        if definition.get("enum"):
            return definition["enum"][0]
        if definition.get("default") is not None:
            return definition["default"]
        if definition.get("format") == "date" or name in {"from_date", "to_date", "date", "from", "to"}:
            return date.today().replace(day=1).isoformat() if "from" in name else date.today().isoformat()
        values = {"month": date.today().month, "year": date.today().year,
                  "financialYear": "2026-2027", "financial_year": "2026-2027", "entity_type": "employee",
                  "entityType": "employee", "q": "audit", "metric": "headcount", "from_currency": "INR",
                  "amount": 1, "gross_taxable_income": 1, "token": "invalid-audit-token"}
        if name in values:
            return values[name]
        return 1 if definition.get("type") in {"number", "integer"} else "audit"

    def resource_id(path, name):
        prefix = path.split("{" + name + "}")[0].rstrip("/")
        with lock:
            record = resources.get(prefix)
        if record is not None:
            return record, True
        known = {"project_id": 4, "task_id": 16, "workspace_id": 2, "document_id": 1, "version": 1}
        if "project-management" in path and name in known:
            return known[name], True
        singular = name.removesuffix("_id")
        with lock:
            candidates = [value for key, value in resources.items() if key.split("/")[-1].replace("-", "_").rstrip("s") == singular]
        if candidates:
            return candidates[0], True
        return 2147483647, False

    def check(row):
        path = row["path"]
        if "/callback/" in path:
            row.update(coverage="not_executed", note="Authentication callback: requires provider-specific flow")
            return
        known = True
        for name in re.findall(r"{([^}]+)}", path):
            value, exists = resource_id(row["path"], name)
            path = path.replace("{" + name + "}", str(value))
            known = known and exists
        params = {parameter["name"]: parameter_value(parameter) for parameter in row["_operation"].get("parameters", [])
                  if parameter["in"] == "query" and parameter.get("required")}
        # Keep list responses and downloads bounded; do not retain private records.
        definitions = row["_operation"].get("parameters", [])
        for parameter in definitions:
            if parameter["in"] == "query" and parameter["name"] in {"limit", "pageSize", "page_size"}:
                params[parameter["name"]] = 5
        selected = {"project-management": "project_management", "crm": "crm", "srm": "srm", "fam": "fam"}.get(row["module"], "hrms")
        start = time.monotonic()
        try:
            with client.stream("GET", path, params=params, headers=headers.get(selected, default_headers)) as response:
                row.update(status=response.status_code, coverage="live_read" if known else "live_missing_resource_probe",
                           note="", elapsed_ms=round((time.monotonic() - start) * 1000))
                if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > 500_000:
                            break
                    if len(body) <= 500_000:
                        try:
                            data = json.loads(body)
                            items = data if isinstance(data, list) else next((data[key] for key in ["items", "data", "results", "employees"] if isinstance(data, dict) and isinstance(data.get(key), list)), [])
                            if items and isinstance(items[0], dict) and items[0].get("id") is not None:
                                with lock:
                                    resources[row["path"].rstrip("/")] = items[0]["id"]
                        except (ValueError, TypeError):
                            pass
                if response.status_code >= 500:
                    row["note"] = "Server failure: inspect runtime exception logs"
                elif response.status_code in {401, 403}:
                    row["note"] = "Access blocked: handler functionality not certified"
                elif response.status_code in {400, 404, 422}:
                    row["note"] = "Input/resource rejection: valid workflow not certified"
                elif response.status_code == 429:
                    row["note"] = "Rate limited: retry separately"
        except httpx.HTTPError as error:
            row.update(status="network_error", coverage="attempted", note=type(error).__name__)

    def save():
        fields = [key for key in rows[0] if not key.startswith("_")]
        public_rows = [{key: row[key] for key in fields} for row in rows]
        (output / "endpoint-inventory.json").write_text(json.dumps(public_rows, indent=2), encoding="utf-8")
        with (output / "endpoint-inventory.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(public_rows)
        failures = [row for row in public_rows if isinstance(row["status"], int) and row["status"] >= 500]
        (output / "server-failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")

    reads = [row for row in rows if row["method"] == "GET"]
    save()
    complete = 0
    for parameterized in [False, True]:
        batch = [row for row in reads if ("{" in row["path"]) == parameterized]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for _ in executor.map(check, batch):
                complete += 1
                if complete % 25 == 0:
                    save()
                    print(f"Checked {complete}/{len(reads)} reads; server failures: {sum(isinstance(row['status'], int) and row['status'] >= 500 for row in rows)}", flush=True)
    save()
    client.close()
    print(f"Inventory saved: {len(rows)} operations, {len(reads)} read operations reviewed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(args.base_url, args.output, args.workers)
