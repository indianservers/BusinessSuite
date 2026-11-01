"""Summarize latest per-case audit evidence; never claim a fresh full-suite run."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/full-interaction-audit"
latest = {}
receipts = sorted([*OUT.glob("*.xml"), *OUT.glob("*.jsonl")], key=lambda path: path.stat().st_mtime)
for path in receipts:
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if "nodeid" in row and "outcome" in row:
                latest[row["nodeid"]] = {"status": row["outcome"], "receipt": path.name}
        continue
    try:
        cases = list(ET.parse(path).iter("testcase"))
    except ET.ParseError:
        continue
    for case in cases:
        parts = case.get("classname", "").split(".")
        for end in range(len(parts), 0, -1):
            filename = "/".join(parts[:end]) + ".py"
            if (ROOT / "backend" / filename).is_file():
                node = "::".join([filename, *parts[end:], case.get("name", "")])
                outcome = "failed" if any(case.find(tag) is not None for tag in ("failure", "error")) else "skipped" if case.find("skipped") is not None else "passed"
                latest[node] = {"status": outcome, "receipt": path.name}
                break
inventory = json.loads((OUT / "test-inventory.json").read_text(encoding="utf-8"))
summary = {
    "qualification": "Latest per-case evidence across separate local runs, not one fresh full-suite pass. Re-run affected cases after changing covered code.",
    "collected": len(inventory),
    "latest_status_counts": {state: sum(latest.get(node, {}).get("status") == state for node in inventory) for state in ("passed", "failed", "skipped")},
    "unvisited": [node for node in inventory if node not in latest],
    "failed": [{"nodeid": node, **latest[node]} for node in inventory if latest.get(node, {}).get("status") == "failed"],
    "skipped": [{"nodeid": node, **latest[node]} for node in inventory if latest.get(node, {}).get("status") == "skipped"],
}
(OUT / "latest-test-status.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
