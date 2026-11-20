"""Index real-browser inventory evidence and validate exported snapshots."""
import html
import json
import re
from decimal import Decimal
from pathlib import Path
from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "inventory-live-audit"
REPORTS = ("overview", "summary", "ledger", "valuation", "purchases", "sales", "reorder", "aging", "expiry", "adjustments", "transfers", "dead-stock", "reconciliation")


def build():
    result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    cases = []

    def visit(suite):
        for spec in suite.get("specs", []):
            last = spec["tests"][0]["results"][-1]
            observations = OUT / (re.sub(r"[^a-zA-Z0-9]+", "-", spec["title"]) + "-observations.json")
            record = {"name": spec["title"], "status": last["status"], "observations": json.loads(observations.read_text(encoding="utf-8")) if observations.exists() else None}
            previous = next((index for index, case in enumerate(cases) if case["name"] == spec["title"]), None)
            if previous is None:
                cases.append(record)
            else:
                cases[previous] = record
        for child in suite.get("suites", []):
            visit(child)

    for suite in result["suites"]:
        visit(suite)
    runs = [result["stats"]]
    classic = OUT / "classic-rerun-results.json"
    if classic.exists():
        rerun = json.loads(classic.read_text(encoding="utf-8"))
        runs.append(rerun["stats"])
        for suite in rerun["suites"]:
            visit(suite)
    stats = {"total": len(cases), "passed": sum(case["status"] == "passed" for case in cases), "failed": sum(case["status"] in {"failed", "timedOut", "interrupted"} for case in cases), "skipped": sum(case["status"] == "skipped" for case in cases)}
    export_checks = []
    for source in ("fam", "srm"):
        for report in REPORTS:
            snapshot = json.loads((OUT / f"{source}-{report}-response.json").read_text(encoding="utf-8"))
            values = list(load_workbook(OUT / f"{source}-{report}.xlsx", data_only=True).active.values)
            expected = snapshot["items"]
            columns = list(expected[0]) if expected else ["No matching records"]
            header = next(index for index, row in enumerate(values) if list(row[:len(columns)]) == columns)
            actual = values[header + 1:]
            assert len(actual) == len(expected), (source, report, "export row count differs")
            for row, exported in zip(expected, actual):
                for key, cell in zip(columns, exported):
                    value = row[key]
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        assert abs(Decimal(str(cell)) - Decimal(str(value))) < Decimal("0.0000001"), (source, report, key)
                    else:
                        assert cell == value, (source, report, key, cell, value)
            reader = PdfReader(OUT / f"{source}-{report}.pdf")
            text = "".join(page.extract_text() for page in reader.pages)
            assert reader.pages and snapshot["as_of"] in text
            if expected:
                assert str(expected[0].get("sku", "")) in re.sub(r"\s", "", text)
            export_checks.append({"source": source, "report": report, "excel_rows": len(actual), "pdf_pages": len(reader.pages), "status": "passed"})
    summary = {"browser_stats": stats, "runs": runs, "cases": cases, "export_checks": export_checks}
    (OUT / "audit-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sections = []
    for report in REPORTS:
        figures = "".join(f'<figure><figcaption>{source.upper()}</figcaption><a href="{source}-{report}.png"><img loading="lazy" src="{source}-{report}.png" alt="{source} {report}"></a><p><a href="{source}-{report}.xlsx">Excel</a> · <a href="{source}-{report}.pdf">PDF</a> · <a href="{source}-{report}-response.json">Response</a></p></figure>' for source in ("fam", "srm"))
        sections.append(f'<h2>{html.escape(report.title())}</h2><section>{figures}</section>')
    responsive = "".join(f'<a href="responsive-{width}.png">{width} px</a> ' for width in (1920, 1366, 768, 390))
    case_list = "".join(f'<li>{html.escape(case["status"].upper())}: {html.escape(case["name"])}</li>' for case in cases)
    classic_links = '<h2>Existing report route screenshots</h2><ul>' + "".join(f'<li><a href="{path.name}">{html.escape(path.stem)}</a></li>' for path in sorted(OUT.glob('classic-*.png'))) + '</ul>'
    (OUT / "screenshots.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Inventory report evidence</title><style>body{font:15px system-ui;margin:24px;color:#202638;background:#f4f5f8}section{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:white;padding:12px}img{width:100%;height:auto}figcaption{font-weight:bold}a{color:#5836b3}li{margin:8px 0}</style><h1>Inventory report browser evidence</h1><p>Actual Chrome, HTTP requests and isolated posted transactions. Finance and Sales are separate stock ledgers. Unsupported or unverified requirements are detailed in the repository audit report.</p><p>Responsive: ''' + responsive + '</p><ol>' + case_list + '</ol>' + classic_links + "".join(sections), encoding="utf-8")
    print(json.dumps({"browser": stats, "export_pairs_validated": len(export_checks)}))


if __name__ == "__main__":
    build()
