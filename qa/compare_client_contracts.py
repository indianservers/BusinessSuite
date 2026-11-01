"""Compare inventoried literal client URLs with OpenAPI; does not invoke APIs."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/full-interaction-audit"
source = json.loads((OUT / "source-catalog.json").read_text(encoding="utf-8"))
contracts = json.loads((OUT / "api-contracts.json").read_text(encoding="utf-8"))
routes = [
    (row["method"], re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(row["path"])) + "$"))
    for row in contracts
]
checked = 0
missing = []
for call in source["apiCalls"]:
    literal = re.fullmatch(r'''["'](/[^"']*)["']''', call["url"])
    if not literal:
        continue  # Dynamic expressions need workflow verification, not guesses.
    url = literal[1].split("?")[0]
    if "/applications/approvals/" in call["file"]:
        url = "/power-apps/approvals" + url  # approvalApi's documented root.
    if not url.startswith("/api/"):
        url = "/api/v1" + url
    checked += 1
    if not any(method == call["method"] and pattern.fullmatch(url) for method, pattern in routes):
        missing.append({**call, "resolved_url": url})
report = {"literal_calls_compared": checked, "unmatched": missing, "dynamic_calls_excluded": True}
(OUT / "client-contract-comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"literal_calls_compared": checked, "unmatched": len(missing)}))
