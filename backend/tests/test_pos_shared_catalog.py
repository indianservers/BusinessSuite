"""Products and services share POS identities; edits preserve operational stock."""
import io
import pytest
from fastapi import HTTPException, UploadFile
from app.apps.srm.models import SRMProduct
from app.apps.crm.models import CRMProduct, CRMService
from app.models.user import User
from app.shared.catalog import ItemInput, save_item, get_item, list_items, upload_image


@pytest.fixture
def actor(db):
    user = User(email="pos-catalog@example.com", hashed_password="unused", is_active=True, is_superuser=True)
    db.add(user)
    db.flush()
    return user


def listing(db, actor, source):
    return list_items(source=source, kind=None, search="", category="", status="all", workspace_id=None, sort="name", direction="asc", page=1, per_page=100, db=db, user=actor)


def test_existing_pos_master_reused_without_creating_crm_copies(db, actor):
    pos = SRMProduct(organization_id=1, sku="POS-ONLY", item_name="Existing POS item", sales_rate=75, current_quantity=23, barcode="POS123", product_type="stock", active=True, track_inventory=True, created_by=actor.id)
    db.add(pos); db.flush()
    for source in ("crm", "pms", "srm"):
        item = listing(db, actor, source)["items"][0]
        assert item["id"] == pos.id and item["price"] == 75
    saved = save_item(db, actor, "crm", ItemInput(kind="product", name="Edited in CRM", code=pos.sku, price=90, tax=18, images=["https://example.com/photo.png"]), pos.id)
    assert saved["id"] == pos.id
    assert pos.sales_rate == 90 and pos.current_quantity == 23 and pos.barcode == "POS123"
    assert pos.metadata_json["images"] == saved["images"]
    assert get_item("product", pos.id, "pms", db, actor)["price"] == 90
    assert db.query(SRMProduct).count() == 1
    assert db.query(CRMProduct).count() == db.query(CRMService).count() == 0


def test_service_is_existing_pos_type_and_archiving_is_shared(db, actor):
    service = save_item(db, actor, "pms", ItemInput(kind="service", name="Consultation", code="CONSULT", price=200))
    row = db.get(SRMProduct, service["id"])
    assert row.product_type == "service" and row.track_inventory is False
    payload = {key: value for key, value in service.items() if key != "id"}
    payload["status"] = "Archived"
    save_item(db, actor, "srm", ItemInput(**payload), row.id)
    assert row.active is False
    assert get_item("service", row.id, "crm", db, actor)["status"] == "Archived"
    with pytest.raises(HTTPException) as error:
        get_item("product", row.id, "crm", db, actor)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_image_upload_validates_content_and_uses_existing_storage(db, actor, monkeypatch, tmp_path):
    from PIL import Image
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    buffer = io.BytesIO(); Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
    result = await upload_image("srm", "product", UploadFile(filename="image.png", file=io.BytesIO(buffer.getvalue())), db, actor)
    assert result["url"].startswith("/uploads/catalog/1/")
    assert (tmp_path / result["url"].removeprefix("/uploads/")).is_file()
    with pytest.raises(HTTPException) as error:
        await upload_image("crm", "service", UploadFile(filename="fake.png", file=io.BytesIO(b"<svg/>")), db, actor)
    assert error.value.status_code == 422


def test_pos_identity_works_in_crm_quote_price_book_and_uploaded_images(client, db, superuser_headers, monkeypatch, tmp_path):
    from PIL import Image
    from app.core.config import settings
    from test_identity_utils import attach_test_identity
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, user); db.commit()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    image = io.BytesIO(); Image.new("RGB", (8, 8), "green").save(image, format="PNG")
    uploaded = client.post("/api/v1/catalog/images?source=srm", headers=superuser_headers, files={"file": ("product.png", image.getvalue(), "image/png")})
    assert uploaded.status_code == 201, uploaded.text
    created = client.post("/api/v1/catalog/items?source=crm", headers=superuser_headers, json={"kind": "product", "name": "POS offering", "code": "ONE-MASTER", "price": 100, "images": [uploaded.json()["url"]]})
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    pos = client.get(f"/api/v1/srm/inventory/items/{ident}", headers=superuser_headers)
    assert pos.status_code == 200, pos.text
    assert pos.json()["metadata_json"]["images"]
    book = client.post("/api/v1/crm/price-books", headers=superuser_headers, json={"name": "POS pricing", "currency": "INR"})
    assert book.status_code == 201, book.text
    book_item = client.post("/api/v1/crm/price-book-items", headers=superuser_headers, json={"price_book_id": book.json()["id"], "item_type": "product", "product_id": ident, "unit_price": 100})
    assert book_item.status_code == 201, book_item.text
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={"quoteNumber": "POS-SHARED-001", "quoteDate": "2026-11-02", "validUntil": "2026-12-02", "status": "Draft"})
    assert quote.status_code == 201, quote.text
    line = client.post(f"/api/v1/crm/quotes/{quote.json()['id']}/lines", headers=superuser_headers, json={"product_id": ident, "name": "POS offering", "quantity": 1, "unit_price": 100})
    assert line.status_code == 201, line.text
    assert line.json()["product_id"] == ident
    assert db.query(SRMProduct).count() == 1 and db.query(CRMProduct).count() == 0
