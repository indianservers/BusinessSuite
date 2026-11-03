"""Use the suite's pure parser from the separately hosted legacy Flask app."""
import importlib.util
import csv
import json
import zipfile
from pathlib import Path

from flask import request

_path = Path(__file__).resolve().parents[5] / "shared" / "tabular_files.py"
_spec = importlib.util.spec_from_file_location("suite_tabular_files", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def prepare_import(upload, fields):
    if request.content_length and request.content_length > 5 * 1024 * 1024:
        raise ValueError("Choose a file under 3 MB")
    if request.form.get("mapped_rows"):
        rows = json.loads(request.form["mapped_rows"])
        if not isinstance(rows, list) or not 1 <= len(rows) <= 5000 or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Import 1 to 5,000 rows")
        if any(len(row) > 150 or any(not isinstance(value, (str, int, float, bool, type(None))) or len(str(value)) > 50000 for value in row.values()) for row in rows):
            raise ValueError("Invalid mapped row values")
        mapping = {f["key"]: request.form.get("map_" + f["key"], "") for f in fields}
        used = [value for value in mapping.values() if value]
        if len(set(used)) != len(used):
            raise ValueError("Map each uploaded column only once")
        if any(f.get("required") and not mapping[f["key"]] for f in fields):
            raise ValueError("Map all required fields")
        mapped = [{target: row[source] for target, source in mapping.items() if source and source in row} for row in rows]
        for index, row in enumerate(mapped, 2):
            if any(f.get("required") and row.get(f["key"]) in (None, "") for f in fields):
                raise ValueError(f"Row {index}: required value is missing")
        return mapped, None
    if not upload or not upload.filename:
        raise ValueError("Choose an Excel or CSV file")
    raw = upload.read(3 * 1024 * 1024 + 1)
    if len(raw) > 3 * 1024 * 1024:
        raise ValueError("Choose a file under 3 MB")
    try:
        parsed = _module.read_table(raw, upload.filename, request.form.get("sheet", ""), int(request.form.get("header_row", "1")))
    except (csv.Error, zipfile.BadZipFile, SyntaxError, OSError, EOFError) as exc:
        raise ValueError("Unable to read this file. Choose a valid Excel .xlsx or UTF-8 CSV file.") from exc
    rows = [dict(zip(parsed["headers"], row)) for row in parsed["rows"]]
    normalized = lambda value: "".join(c for c in value.lower() if c.isalnum())
    suggestions, used = {}, set()
    for field in fields:
        names = [field["key"], *field.get("aliases", [])]
        match = next((h for h in parsed["headers"] if h not in used and normalized(h) in [normalized(n) for n in names]), "")
        suggestions[field["key"]] = match
        if match:
            used.add(match)
    return None, {"headers": parsed["headers"], "sample": rows[:5], "rows": rows, "fields": fields, "suggestions": suggestions, "filename": upload.filename}
