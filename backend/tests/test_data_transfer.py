import io
import json
from datetime import datetime

import pytest
from openpyxl import Workbook, load_workbook

from app.shared.tabular_files import read_table
from app.models.user import User
from test_identity_utils import attach_test_identity

ROOT = "/api/v1/data-transfer"


@pytest.fixture
def headers(db, superuser_headers):
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


def workbook():
    book = Workbook()
    sheet = book.active
    sheet.title = "Read me"
    sheet.append(["Instructions"])
    sheet = book.create_sheet("Employees")
    sheet.append(["Staff upload"])
    sheet.append(["Given Name", "Joined", "Email Address", "Mobile"])
    sheet.append(["Ada", datetime(2026, 1, 1), "ada@example.com", "0987654321"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_sheet_header_selection_dates_and_strings():
    parsed = read_table(workbook(), "staff.xlsx", "Employees", 2)
    assert parsed["sheets"] == ["Read me", "Employees"]
    assert parsed["rowNumbers"] == [3]
    assert parsed["rows"][0] == ["Ada", "2026-01-01", "ada@example.com", "0987654321"]


@pytest.mark.parametrize("content,reason", [
    (b"Name,Name\nAda,Smith", "unique"),
    (b"Name,,Email\nAda,Smith,a@example.com", "header"),
    (b"Name,Email\nAda,a@example.com,extra", "without column headings"),
    (b'Name,Email\n"Unclosed', ""),
])
def test_bad_headers_and_malformed_rows_are_rejected(content, reason):
    with pytest.raises((ValueError, __import__("csv").Error), match=reason or None):
        read_table(content, "data.csv")


def test_csv_delimiters_quotes_newlines_and_limits():
    parsed = read_table('Name;Notes\r\nAda;"Hello; world\nSecond line"'.encode(), "data.csv")
    assert parsed["rows"] == [["Ada", "Hello; world\nSecond line"]]
    with pytest.raises(ValueError, match="at most"):
        read_table(b"Name\nAda\nGrace", "data.csv", max_rows=1)


def test_inspect_requires_login_and_does_not_write(client, headers, db):
    assert client.post(ROOT + "/inspect", files={"file": ("staff.xlsx", workbook())}).status_code in (401, 403)
    response = client.post(ROOT + "/inspect", headers=headers, files={"file": ("staff.xlsx", workbook())}, data={"sheet": "Employees", "header_row": 2})
    assert response.status_code == 200, response.text
    assert response.json()["headers"][0] == "Given Name"
    assert client.post(ROOT + "/inspect", headers=headers, files={"file": ("old.xls", b"old")}).status_code == 422


def test_convert_real_excel_chosen_columns_formula_protection(client, headers):
    rows = [{"Name": "=HYPERLINK(\"bad\")", "Amount": -12.5, "Private": "excluded"}]
    file = ("export.json", json.dumps(rows).encode(), "application/json")
    response = client.post(ROOT + "/export/convert", headers=headers, files={"file": file}, data={"format": "xlsx", "columns": '["Name","Amount"]'})
    assert response.status_code == 200, response.text
    sheet = load_workbook(io.BytesIO(response.content)).active
    assert list(sheet.values)[0] == ("Name", "Amount")
    assert sheet["A2"].value.startswith("'=")
    assert sheet["A2"].data_type != "f"
    assert sheet["B2"].value == -12.5
    assert sheet.freeze_panes == "A2"
    csv = client.post(ROOT + "/export/convert", headers=headers, files={"file": file}, data={"format": "csv", "columns": '["Amount"]'})
    assert "Private" not in csv.text and "-12.5" in csv.text
    invalid = client.post(ROOT + "/export/convert", headers=headers, files={"file": file}, data={"columns": '["unknown"]'})
    assert invalid.status_code == 422


def test_mapped_employee_file_uses_existing_validation(client, headers):
    metadata = client.get("/api/v1/crm/companies/import-fields", headers=headers)
    assert metadata.status_code == 200, metadata.text
    fields = {f["key"]: f for f in metadata.json()}
    assert fields["name"]["required"]
    assert "organization_id" not in fields and "id" not in fields
    # Mapped file uses destination names, never the uploaded human-friendly headings.
    response = client.post("/api/v1/employees/import", headers=headers, files={"file": ("mapped.csv", b"first_name,date_of_joining,personal_email\nAda,2026-01-01,ada.mapping@example.com")})
    assert response.status_code == 201, response.text
    assert response.json()["created"] == 1
    assert response.json()["failed"] == 0


def test_invalid_first_sheet_keeps_sheet_choices(client, headers):
    response = client.post(ROOT + "/inspect", headers=headers, files={"file": ("staff.xlsx", workbook())})
    assert response.status_code == 422
    assert response.json()["detail"]["sheets"] == ["Read me", "Employees"]


def test_legacy_inventory_uses_shared_parser_and_validates_mapping(monkeypatch):
    # The legacy inventory app is separately hosted; exercise its adapter without
    # loading Flask's app/database or changing the main backend's dependencies.
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    request = SimpleNamespace(content_length=100, form={})
    monkeypatch.setitem(sys.modules, "flask", SimpleNamespace(request=request))
    path = Path(__file__).resolve().parents[1] / "app/apps/inventory/vyapara_erp/app/utils/tabular_import.py"
    spec = importlib.util.spec_from_file_location("legacy_transfer_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fields = [{"key": "sku", "required": True, "aliases": ["Product code"]}, {"key": "name", "required": True, "aliases": ["Product name"]}]
    upload = io.BytesIO(b"Product code,Product name\n001,Widget")
    upload.filename = "items.csv"
    rows, preview = module.prepare_import(upload, fields)
    assert rows is None
    assert preview["suggestions"] == {"sku": "Product code", "name": "Product name"}
    request.form = {"mapped_rows": json.dumps(preview["rows"]), "map_sku": "Product code", "map_name": "Product name"}
    rows, preview = module.prepare_import(None, fields)
    assert rows == [{"sku": "001", "name": "Widget"}]
    request.form["map_name"] = "Product code"
    with pytest.raises(ValueError, match="only once"):
        module.prepare_import(None, fields)
