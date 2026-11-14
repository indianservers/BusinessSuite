from hashlib import sha256
from pathlib import Path

import pytest

from app.apps.crm.models import CRMFileAsset
from tests.rich_text_test_utils import organization_context
from tests.test_files_storage import storage_root


BASE = "/api/v1/crm/file-workspace"


def test_crm_upload_download_retains_exact_file_and_folder(client, db, superuser_headers, storage_root):
    headers = superuser_headers
    folder = client.post(BASE + "/folders", headers=headers, json={"name": "Audit attachments"})
    assert folder.status_code == 201
    body = "Synthetic QA attachment\nLine two: cafe \u00e9\n".encode("utf-8")
    created = client.post(BASE + "/upload", headers=headers, data={"folder_id": folder.json()["id"]}, files={"file": ("audit roundtrip.txt", body, "text/plain")})
    assert created.status_code == 201
    identity = created.json()["id"]
    listing = client.get(BASE, headers=headers)
    assert listing.status_code == 200
    row = next(item for item in listing.json()["files"] if item["id"] == identity)
    assert row["name"] == "audit roundtrip.txt" and row["folder_id"] == folder.json()["id"] and row["size"] == len(body)
    downloaded = client.get(BASE + f"/files/{identity}/download", headers=headers)
    assert downloaded.status_code == 200
    assert sha256(downloaded.content).digest() == sha256(body).digest()
    assert downloaded.headers["content-type"].startswith("text/plain")
    assert "attachment" in downloaded.headers["content-disposition"]
    assert client.get(BASE + f"/files/{identity}/download").status_code in {401, 403}
    assert client.get(BASE + "/files/999999/download", headers=headers).status_code in {403, 404}


@pytest.mark.parametrize("kind", ["empty", "unsupported", "missing_folder"])
def test_rejected_crm_upload_leaves_no_record_or_file(client, db, superuser_headers, storage_root, kind):
    body = b"" if kind == "empty" else b"Synthetic test data"
    mime = "application/x-msdownload" if kind == "unsupported" else "text/plain"
    data = {"folder_id": "999999"} if kind == "missing_folder" else {}
    response = client.post(BASE + "/upload", headers=superuser_headers, data=data, files={"file": ("rejected.txt", body, mime)})
    assert response.status_code in {400, 404}
    assert db.query(CRMFileAsset).count() == 0
    assert not [p for p in Path(storage_root).rglob("*") if p.is_file()]


@pytest.mark.parametrize("manage", [False, True])
def test_file_cabinet_advertises_server_write_permission(client, db, storage_root, manage):
    from admin_security_test_utils import auth_headers
    headers = auth_headers(client, db, email=f"audit-files-{int(manage)}@example.com", role_name=f"audit_files_{manage}", permissions=["crm_view", "crm_manage"] if manage else ["crm_view"])
    cabinet = client.get(BASE, headers=headers)
    assert cabinet.status_code == 200
    assert cabinet.json()["can_manage"] is manage
    folder = client.post(BASE + "/folders", headers=headers, json={"name": "Allowed only for managers"})
    assert folder.status_code == (201 if manage else 403)
