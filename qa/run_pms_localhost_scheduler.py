"""Optional clock for the isolated localhost sandbox; production uses cron."""
import argparse
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import httpx

ROOT = Path(__file__).resolve().parents[1]


def tick():
    info = json.loads((ROOT / ".local/workflow-localhost-session.json").read_text())
    assert re.fullmatch(r"business_suite_workflow_localhost_[a-f0-9]+_test", info["database"])
    assert urlsplit(info["api"]).hostname in {"localhost", "127.0.0.1"}
    response = httpx.get(info["api"] + "/api/v1/internal/pms-automations",
        headers={"Authorization": "Bearer " + info["scheduler_secret"]}, timeout=120)
    response.raise_for_status()
    print(json.dumps(response.json()), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    while True:
        try:
            tick()
        except Exception as error:
            print(json.dumps({"scheduler_error": type(error).__name__}), flush=True)
            if args.once:
                raise SystemExit(1)
        if args.once:
            break
        time.sleep(max(30, min(args.interval, 3600)))
