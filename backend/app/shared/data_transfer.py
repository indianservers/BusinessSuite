"""Stateless file tools. Module endpoints still authorize and persist every import/export."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.styles import Font, PatternFill

from app.core.deps import get_current_user
from app.shared.tabular_files import read_table

router = APIRouter(prefix="/data-transfer", tags=["Shared data transfer"])


async def inspect_file(file, sheet, header_row, export=False):
    limit = (20 if export else 3) * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"Choose a file up to {limit // 1024 // 1024} MB")
    try:
        return read_table(raw, file.filename or "", sheet, header_row, 20000 if export else 5000)
    except (ValueError, TypeError, UnicodeError, csv.Error, zipfile.BadZipFile, KeyError, OSError, InvalidFileException, SyntaxError, EOFError) as exc:
        message = str(exc)[:300] or "Unable to read this file"
        raise HTTPException(422, {"message": message, "sheets": exc.sheets} if getattr(exc, "sheets", None) else message)


@router.post("/inspect")
async def inspect(file: UploadFile = File(...), sheet: str = Form(""), header_row: int = Form(1), user=Depends(get_current_user)):
    return await inspect_file(file, sheet, header_row)


@router.post("/export/inspect")
async def inspect_export(file: UploadFile = File(...), user=Depends(get_current_user)):
    return await inspect_file(file, "", 1, export=True)


def spreadsheet_cell(value):
    # Numeric negatives stay numeric. Untrusted text cannot execute as a formula.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.post("/export/convert")
async def convert(file: UploadFile = File(...), format: Literal["csv", "xlsx", "json", "clipboard"] = Form("xlsx"), columns: str = Form("[]"), user=Depends(get_current_user)):
    table = await inspect_file(file, "", 1, export=True)
    try:
        selected = json.loads(columns) or table["headers"]
        if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected) or any(key not in table["headers"] for key in selected):
            raise ValueError()
    except (TypeError, ValueError):
        raise HTTPException(422, "Choose valid export columns")
    indexes = [table["headers"].index(key) for key in selected]
    rows = [[row[i] for i in indexes] for row in table["rows"]]
    if format == "json":
        content = json.dumps([dict(zip(selected, row)) for row in rows], ensure_ascii=False)
        mime = "application/json"
    elif format == "xlsx":
        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("Export")
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = f"A1:{get_column_letter(len(selected))}{len(rows) + 1}"
        for index, heading in enumerate(selected):
            width = max([len(heading), *[len(str(row[index] or "")) for row in rows[:100]]])
            worksheet.column_dimensions[get_column_letter(index + 1)].width = min(50, max(15, width + 2))
        header = [WriteOnlyCell(worksheet, spreadsheet_cell(key)) for key in selected]
        for cell_ in header:
            cell_.font = Font(bold=True, color="FFFFFF")
            cell_.fill = PatternFill("solid", fgColor="334155")
        worksheet.append(header)
        for row in rows:
            worksheet.append([spreadsheet_cell(v) for v in row])
        output = io.BytesIO()
        workbook.save(output)
        content, mime = output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter="\t" if format == "clipboard" else ",")
        for row in [selected, *rows]:
            writer.writerow([spreadsheet_cell(value) for value in row])
        content = "\ufeff" + output.getvalue()
        mime = "text/tab-separated-values" if format == "clipboard" else "text/csv"
    return Response(content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="export.{"tsv" if format == "clipboard" else format}"'})
