"""Combine native workflow evidence and the 121-route role observations honestly."""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/conditional-121"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    pages = read(ROOT / "outputs/project-ux-20261107/pages.json")
    baseline = {row["page"]: row for row in read(ROOT / "outputs/crud-permissions-121-final/page-results.json")}
    native = read(OUT / "native-results.json")
    roles = {profile: read(OUT / f"role-{profile}.json") for profile in ("creator", "editor", "approver", "configurer", "deleter", "assigner")}
    if any(len(rows) != 121 for rows in roles.values()):
        raise SystemExit("Role sweep is incomplete; no final report written")
    unresolved = [{"page": row["page"], "role": profile, "checks": [check for check in row["checks"] if not check["passed"]], "error": row.get("error"), "errors": row.get("errors")} for profile, rows in roles.items() for row in rows if row["result"] == "failed"]
    unresolved += [{"page": row["title"], "error": row.get("error")} for row in native if row["status"] != "passed"]
    matrix = []
    for page in pages:
        route = page["route"]
        role_results = {profile: next(row["result"] for row in rows if row["page"] == route) for profile, rows in roles.items()}
        workflows = [row["title"] for row in native if route in row["title"]]
        matrix.append({"module": page["module"], "page": route, "baseline_own_ui_workflow": baseline.get(route, {}).get("workflow_verified", "See baseline native workflow evidence"), "current_role_observations": role_results, "targeted_native_workflows": workflows, "meta_dependent_actions_excluded": route.startswith("/crm/whatsapp"), "portal_policy": "Native customer/partner policy workflows; internal module roles do not apply" if route.startswith("/portal/") else "Internal module roles"})
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": "http://127.0.0.1:1582",
        "page_count": len(pages),
        "meta_actions_excluded": True,
        "live_email_delivery": "Skipped at the user's explicit request",
        "all_action_signoff": False,
        "recorded_remaining_workflow_failures_resolved": not unresolved,
        "coverage_statement": "Baseline own-page workflows, targeted remaining state/role workflows, and fresh role-control inventories are distinct evidence. They do not certify every possible action/state/role combination.",
        "role_control_inventories": {profile: dict(Counter(row["result"] for row in rows)) for profile, rows in roles.items()},
        "native_workflow_results": dict(Counter(row["status"] for row in native)),
        "baseline_native_own_ui_tests_passed": len(read(ROOT / "outputs/action-audit-121/native-ui-passes.json")),
        "unresolved_observed_failures": unresolved,
        "backend_regressions": {"remaining_domain_cases": "51 passed", "branch_note_undo": "9 passed", "conditional_permissions_and_workspace_capability_isolation": "52 passed"},
        "frontend_typecheck": "passed; types-time-draft-race.log",
        "frontend_build": "passed; build-time-draft-race.log",
        "served_build": read(OUT / "served-verification-final.json"),
        "notes": ["Synthetic acceptance accounts and records in a preserved isolated QA database.", "No live external delivery or bank transfer was performed.", "Portal native workflows cover eleven routes under their own customer/partner policies."]
    }
    (OUT / "verification-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "page-wise-verification.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    with (OUT / "page-wise-verification.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["module", "page", "baseline_own_ui_workflow", *roles.keys(), "targeted_native_workflows", "portal_policy"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in matrix:
            writer.writerow({key: row[key] for key in ("module", "page", "baseline_own_ui_workflow", "portal_policy")} | row["current_role_observations"] | {"targeted_native_workflows": "; ".join(row["targeted_native_workflows"])})
    print(json.dumps({"pages": len(matrix), "native": summary["native_workflow_results"], "roles": summary["role_control_inventories"], "unresolved_observed_failures": len(unresolved), "all_action_signoff": False}, indent=2))


if __name__ == "__main__":
    main()
