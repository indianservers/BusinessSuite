"""Bounded spreadsheet reader; no app, authentication, or persistence dependencies."""
import csv
import io
import json
import math
import zipfile
from datetime import date, datetime
from openpyxl import load_workbook

MAX_COLUMNS = 150


class TableReadError(ValueError):
    def __init__(self, message, sheets):
        super().__init__(message)
        self.sheets = sheets

def cell(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat().replace("T00:00:00", "")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers are not supported")
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value if value is not None else ""


def read_table(raw: bytes, filename: str, sheet: str = "", header_row: int = 1, max_rows: int = 5000):
    """Bounded parser shared by uploads and export conversions; never executes formulas."""
    if not 1 <= header_row <= 50:
        raise ValueError("Choose a header row from 1 to 50")
    sheets = []
    workbook = None
    try:
        if filename.lower().endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 60 * 1024 * 1024 or len(archive.infolist()) > 2000:
                    raise ValueError("Workbook is too large when expanded; split it into smaller files")
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
            sheets = workbook.sheetnames
            if sheet and sheet not in sheets:
                raise ValueError("Choose a worksheet from this workbook")
            active = workbook[sheet or sheets[0]]
            if active.max_column and active.max_column > MAX_COLUMNS:
                raise ValueError(f"Use at most {MAX_COLUMNS} columns; remove unused formatted columns")
            matrix = active.iter_rows(values_only=True)
        elif filename.lower().endswith(".json"):
            items = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(items, list) or not items or not all(isinstance(row, dict) for row in items):
                raise ValueError("JSON must contain a non-empty array of records")
            if len(items) > max_rows:
                raise ValueError(f"Use at most {max_rows:,} rows")
            headers = list(dict.fromkeys(key for row in items for key in row))
            matrix = iter([headers, *[[cell(row.get(key)) for key in headers] for row in items]])
        elif filename.lower().endswith((".csv", ".tsv", ".txt")):
            text = raw.decode("utf-8-sig")
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel_tab if filename.lower().endswith(".tsv") else csv.excel
            matrix = csv.reader(io.StringIO(text, newline=""), dialect, strict=True)
        else:
            raise ValueError("Choose an Excel .xlsx, CSV, TSV or JSON file. Save older .xls files as .xlsx first.")
        for _ in range(header_row - 1):
            next(matrix, None)
        original = list(next(matrix, []))
        while original and original[-1] in (None, ""):
            original.pop()
        headers = [str(value or "").strip() for value in original]
        if not headers or any(not h for h in headers):
            raise ValueError("Every column needs a header; choose the correct header row")
        if len(headers) > MAX_COLUMNS:
            raise ValueError(f"Use at most {MAX_COLUMNS} columns")
        if len({h.casefold() for h in headers}) != len(headers):
            raise ValueError("Column headers must be unique; rename duplicate headings")
        if any(len(h) > 200 for h in headers):
            raise ValueError("Column headers must be under 200 characters")
        rows, numbers = [], []
        for number, values in enumerate(matrix, start=header_row + 1):
            if number > max_rows + header_row + 1000:
                raise ValueError("Too many empty rows; remove unused rows")
            values = list(values)
            if not any(v not in (None, "") for v in values):
                continue
            if len(rows) >= max_rows:
                raise ValueError(f"Use at most {max_rows:,} rows; split the file and try again")
            if any(v not in (None, "") for v in values[len(headers):]):
                raise ValueError(f"Row {number} contains values without column headings")
            normalized = [cell(v) for v in values[:len(headers)]]
            if any(len(str(v)) > 50000 for v in normalized):
                raise ValueError(f"Row {number} contains a cell longer than 50,000 characters")
            rows.append(normalized + [""] * (len(headers) - len(normalized)))
            numbers.append(number)
        if not rows:
            raise ValueError("The selected sheet has no data below the header")
        return {"headers": headers, "rows": rows, "rowNumbers": numbers, "total": len(rows), "sheets": sheets, "sheet": sheet or (sheets[0] if sheets else ""), "headerRow": header_row}
    except ValueError as exc:
        if workbook:
            raise TableReadError(str(exc), workbook.sheetnames) from exc
        raise
    finally:
        if workbook:
            workbook.close()

