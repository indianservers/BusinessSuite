"""Run edit/delete acceptance tests against their own copied QA database."""
from pathlib import Path
source = Path(__file__).with_name("serve_verified_1582.py").read_text(encoding="utf-8")
exec(compile(source.replace("1582", "1583"), __file__, "exec"))
