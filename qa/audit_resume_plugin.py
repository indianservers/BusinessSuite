"""Opt-in pytest audit resume: skip only successful cases in supplied JUnit files.

Set SUITE_AUDIT_PASSED_XML to an os.pathsep-separated list of audit receipts.
Use only receipts whose covered code remains applicable. This is a coverage aid,
not a replacement for rerunning regressions affected by subsequent changes.
"""
import os
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "backend"


def pytest_collection_modifyitems(config, items):
    inventory = os.environ.get("SUITE_AUDIT_INVENTORY")
    if inventory:
        import json
        Path(inventory).write_text(json.dumps([item.nodeid for item in items], indent=2), encoding="utf-8")
    receipts = os.environ.get("SUITE_AUDIT_PASSED_XML", "")
    if not receipts:
        return
    passed = set()
    for receipt in receipts.split(os.pathsep):
        for case in ET.parse(receipt).iter("testcase"):
            if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
                continue
            parts = case.get("classname", "").split(".")
            for end in range(len(parts), 0, -1):
                filename = "/".join(parts[:end]) + ".py"
                if (ROOT / filename).is_file():
                    passed.add("::".join([filename, *parts[end:], case.get("name", "")]))
                    break
    import json
    for receipt in os.environ.get("SUITE_AUDIT_PASSED_JSONL", "").split(os.pathsep):
        if receipt:
            for line in Path(receipt).read_text(encoding="utf-8").splitlines():
                case = json.loads(line)
                if case["outcome"] == "passed":
                    passed.add(case["nodeid"])
    skipped = [item for item in items if item.nodeid in passed]
    items[:] = [item for item in items if item.nodeid not in passed]
    config.hook.pytest_deselected(items=skipped)
    config._suite_audit_resumed_count = len(skipped)
    partition = os.environ.get("SUITE_AUDIT_PARTITION")
    if partition:
        import zlib
        index, total = map(int, partition.split("/"))
        if not 0 <= index < total:
            raise ValueError("Invalid audit partition")
        excluded = [item for item in items if zlib.crc32(item.nodeid.encode()) % total != index]
        items[:] = [item for item in items if zlib.crc32(item.nodeid.encode()) % total == index]
        config.hook.pytest_deselected(items=excluded)


def pytest_terminal_summary(terminalreporter, config):
    count = getattr(config, "_suite_audit_resumed_count", 0)
    if count:
        terminalreporter.write_line(f"Audit resume: {count} previously passing cases excluded; this run certifies selected cases only.")


def pytest_runtest_logreport(report):
    """Keep an opt-in local receipt even if a long exploratory run is stopped."""
    destination = os.environ.get("SUITE_AUDIT_CASE_LOG")
    if not destination or report.when != "call":
        return
    import json
    record = {"nodeid": report.nodeid, "outcome": report.outcome, "duration": report.duration}
    if report.failed:
        record["failure"] = str(report.longrepr)
    with Path(destination).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def pytest_runtest_call(item):
    if os.environ.get("SUITE_AUDIT_SECURITY_LOG") == "1":
        import logging
        logger = logging.getLogger("businesssuite.security")
        logger.disabled = False
        logger.setLevel(logging.WARNING)
        logger.propagate = True
