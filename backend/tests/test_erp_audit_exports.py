import csv
from io import BytesIO, StringIO

from openpyxl import load_workbook
from pypdf import PdfReader

from tests.analytics_test_utils import analytics_headers, create_analytics_deal


def test_report_downloads_preserve_every_matching_row(client, db, tmp_path, monkeypatch, record_property):
    from app.apps.analytics.services import engine
    monkeypatch.setattr(engine.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(engine, "persist_file", lambda path: None)
    headers = analytics_headers(client, db)
    expected = {f"Audit export row {index:03d}" + (" long content" * 8 if index == 50 else ""): str(1000 + index) for index in range(105)}
    for index, name in enumerate(expected):
        create_analytics_deal(db, name, 1000 + index)
    report = client.post("/api/v1/analytics/reports", headers=headers, json={"name": "Audit complete exports", "module_name": "crm_deals", "report_type": "table", "visibility": "public", "fields_json": ["name", "amount"]})
    assert report.status_code == 201
    for kind in ["csv", "xlsx", "pdf"]:
        exported = client.post(f"/api/v1/analytics/reports/{report.json()['id']}/export", headers=headers, json={"export_type": kind})
        assert exported.status_code == 201
        result = exported.json()
        assert result["status"] == "completed" and result["row_count"] == 105
        downloaded = client.get(f"/api/v1/analytics/exports/{result['id']}/download", headers=headers)
        assert downloaded.status_code == 200
        assert "attachment" in downloaded.headers["content-disposition"]
        if kind == "csv":
            rows = list(csv.DictReader(StringIO(downloaded.content.decode("utf-8"))))
            assert len(rows) == 105
            assert {row["name"] for row in rows} == set(expected)
            assert all(float(row["amount"]) == float(expected[row["name"]]) for row in rows)
        elif kind == "xlsx":
            workbook = load_workbook(BytesIO(downloaded.content), read_only=True)
            values = list(workbook.active.values)
            assert values[0] == ("name", "amount")
            assert len(values) == 106
            assert {row[0] for row in values[1:]} == set(expected)
            assert all(float(row[1]) == float(expected[row[0]]) for row in values[1:])
            workbook.close()
        else:
            record_property("pdf_path", result["file_path_or_reference"])
            reader = PdfReader(BytesIO(downloaded.content))
            text = "\n".join(page.extract_text() for page in reader.pages)
            assert len(reader.pages) > 1
            normalized = "".join(text.split())
            missing = [name for name in expected if "".join(name.split()) not in normalized]
            assert not missing, f"PDF claims 105 rows but omitted: {missing}"
