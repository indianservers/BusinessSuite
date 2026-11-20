"""Build a local screenshot comparison and case index from real browser results."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "offerings-live-audit"
KINDS = ("product", "service", "membership", "subscription", "bundle")


def build():
    result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    cases_by_name = {}
    runs = []

    def visit(suite):
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                last = test["results"][-1]
                observation = OUT / (re.sub(r"[^a-zA-Z0-9]+", "-", spec["title"]) + "-observations.json")
                previous = cases_by_name.get(spec["title"], {})
                attempts = previous.get("attempts", []) + [{"status": last["status"], "start_time": last.get("startTime"), "duration_ms": last["duration"]}]
                cases_by_name[spec["title"]] = {"name": spec["title"], "status": last["status"], "duration_ms": last["duration"], "attempts": attempts,
                    "observations": json.loads(observation.read_text(encoding="utf-8")) if observation.exists() else None}
        for child in suite.get("suites", []):
            visit(child)

    interrupted = OUT / "interrupted-server-run-results.json"
    sources = [json.loads(interrupted.read_text(encoding="utf-8"))] if interrupted.exists() else []
    sources.extend(json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUT.glob("rerun-results-*.json")))
    sources.append(result)
    for source in sources:
        runs.append(source["stats"])
        for suite in source["suites"]:
            visit(suite)
    cases = list(cases_by_name.values())
    stats = {"total": len(cases), "passed": sum(c["status"] == "passed" for c in cases), "failed": sum(c["status"] in {"failed", "timedOut", "interrupted"} for c in cases), "skipped": sum(c["status"] == "skipped" for c in cases)}
    (OUT / "case-summary.json").write_text(json.dumps({"stats": stats, "runs": runs, "cases": cases}, indent=2), encoding="utf-8")
    rows = []
    for width, height in [(1920, 1080), (1366, 768), (768, 1024), (390, 844)]:
        for view in ("listing", "editor"):
            images = "".join(f'<figure><figcaption>{kind.title()}</figcaption><a href="{width}-{kind}-{view}.png"><img src="{width}-{kind}-{view}.png" alt="{kind} {view} at {width} by {height}" loading="lazy"></a></figure>' for kind in KINDS)
            rows.append(f'<h2>{width} × {height}: {view}</h2><section>{images}</section>')
    case_list = "".join(f'<li><strong>{html.escape(case["status"].upper())}</strong> {html.escape(case["name"])}</li>' for case in cases)
    (OUT / "comparison.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Business Suite real-browser comparison</title>
<style>body{font:15px system-ui;margin:24px;background:#f4f5f7;color:#18212f}section{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}figure{margin:0;background:white;padding:8px}img{width:100%;height:auto}figcaption{font-weight:600;margin-bottom:8px}li{margin:8px 0}a{color:inherit}</style>
<h1>Real-browser offering audit</h1><p>Synthetic isolated SQLite data; actual Chrome and HTTP workflows. Click screenshots for full resolution. Passing cases do not establish production readiness.</p>''' + "".join(rows) + '<h2>Executed cases</h2><ol>' + case_list + '</ol></html>', encoding="utf-8")
    try:
        from PIL import Image, ImageDraw
        sheet = Image.new("RGB", (1500, 760), "#eef0f3")
        draw = ImageDraw.Draw(sheet)
        for index, kind in enumerate(KINDS):
            draw.text((index * 300 + 10, 10), kind.title(), fill="black")
            image = Image.open(OUT / f"390-{kind}-editor.png").convert("RGB")
            image.thumbnail((290, 710))
            sheet.paste(image, (index * 300 + 5, 40))
        sheet.save(OUT / "mobile-editors-side-by-side.png")
    except ImportError:
        pass
    print(json.dumps(stats))


if __name__ == "__main__":
    build()
