"""Photo byte reuse must not bypass authorization or cache documents."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from app.core.photo_cache import private_file_response
from app.core.middleware.security_headers import SecurityHeadersMiddleware


def test_photo_revalidation_and_revocation(tmp_path):
    photo = tmp_path / "photos" / "portrait.png"
    photo.parent.mkdir()
    photo.write_bytes(b"portrait")
    allowed = True
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/photo")
    def read(request: Request):
        if not allowed:
            raise HTTPException(403)
        return private_file_response(str(photo), request)

    client = TestClient(app)
    first = client.get("/api/photo")
    assert first.content == b"portrait"
    assert first.headers["cache-control"] == "private, no-cache, must-revalidate"
    headers = {"If-None-Match": first.headers["etag"]}
    unchanged = client.get("/api/photo", headers=headers)
    assert unchanged.status_code == 304
    assert unchanged.content == b""
    assert client.get("/api/photo", headers={"If-None-Match": '"other", W/' + first.headers["etag"]}).status_code == 304
    photo.write_bytes(b"replacement portrait")
    assert client.get("/api/photo", headers=headers).content == b"replacement portrait"
    allowed = False
    assert client.get("/api/photo", headers=headers).status_code == 403


def test_documents_remain_uncacheable(tmp_path):
    document = tmp_path / "identity.png"
    document.write_bytes(b"private document")
    request = Request({"type": "http", "headers": [(b"if-none-match", b"*")]})
    response = private_file_response(str(document), request)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"

