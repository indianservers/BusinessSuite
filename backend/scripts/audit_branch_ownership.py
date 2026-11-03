"""Read-only runtime-model inventory; does not infer unknown historical owners."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base
from app.branches.catalog import inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = inventory(Base.metadata)
    report = {"source": "Enabled SQLAlchemy runtime models; embedded standalone Flask application excluded", "tables": len(rows), "categories": dict(Counter(row["category"] for row in rows)), "ownership": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "ownership"}))


if __name__ == "__main__": main()
