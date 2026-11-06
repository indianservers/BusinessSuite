"""Audit the running local API using its normal seeded administrator login.

No mocked requests, database edits, credentials or tokens in the saved report.
"""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from app.db.init_db import DEMO_USERS

ROOT = "http://127.0.0.1:1534/api/v1"
admin = next(row for row in DEMO_USERS if row["email"] == "admin@aihrms.com")
with urlopen(Request(ROOT + "/auth/login", data=json.dumps({"email": admin["email"], "password": admin["password"]}).encode(), headers={"Content-Type": "application/json"}), timeout=60) as response:
    auth = json.load(response)
headers = {"Authorization": "Bearer " + auth["access_token"], "Content-Type": "application/json", "X-Suite-Organization": "1"}

def request(path, method="GET", body=None, params=None):
    url = ROOT + path + ("?" + urlencode(params) if params else "")
    req = Request(url, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(req, timeout=90) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())

status, branches = request("/branches/context")
assert status == 200, (status, branches)
branch = next(row for row in branches["branches"] if row["name"] == "QA CRUD Branch API 20261026")
headers["X-Suite-Branch"] = str(branch["id"])
report = {"origin": ROOT, "company": 1, "branch": branch["id"], "sources": {}}

def all_rows(path, **params):
    rows = []
    page = 1
    while True:
        status, result = request(path, params={**params, "page": page, "per_page": 100})
        assert status == 200, (path, status, result)
        batch = result.get("items", [])
        rows.extend(batch)
        if not batch or len(rows) >= result.get("total", len(rows)):
            return rows, result
        page += 1

contacts, _ = all_rows("/crm/contacts")
leads, _ = all_rows("/crm/lead-management/leads", record_type="Lead")
potential, _ = all_rows("/crm/lead-management/leads", record_type="Potential")
companies, _ = all_rows("/crm/companies")
hub, listing = all_rows("/crm/contact-directory")
hub_ids = {row["id"] for row in hub}
report["hub_total"] = len(hub)
report["hub_stats"] = listing.get("stats")
report["sources"]["contacts"] = {"count": len(contacts), "missing_ids": sorted({row["id"] for row in contacts} - hub_ids)}
for label, rows in [("leads", leads), ("potential_customers", potential)]:
    report["sources"][label] = {"count": len(rows), "names": [row.get("name") or row.get("full_name") for row in rows]}
for kind in ["Vendor", "Customer", "Prospect"]:
    sources = [row for row in companies if row.get("account_type") == kind]
    linked_ids = {row.get("companyId") for row in hub}
    report["sources"][kind] = {"count": len(sources), "missing_company_ids": sorted({row["id"] for row in sources} - linked_ids)}
for kind in ["Lead", "Prospect", "Customer", "Vendor"]:
    filtered, _ = all_rows("/crm/contact-directory", relationship=kind)
    report.setdefault("filters", {})[kind] = len(filtered)
for path in ["/access/services/catalog", "/integrations/whatsapp/status", "/crm/messages?entityType=contact&entityId=" + str(hub[0]["id"])]:
    status, data = request(path)
    report.setdefault("provider_checks", []).append({"path": path, "status": status, "response": data if status != 200 else {key: data[key] for key in ["channels", "providers", "enabled", "provider", "configured", "connected"] if key in data}})
from collections import Counter
company_counts = Counter(row.get("companyId") for row in hub if row.get("companyId"))
report["multiple_contacts_per_account"] = {"accounts": sum(count > 1 for count in company_counts.values()), "max_contacts": max(company_counts.values(), default=0)}
print(json.dumps(report, indent=2), flush=True)
output = Path("../docs/qa/relationship-hub/live-api-audit.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
