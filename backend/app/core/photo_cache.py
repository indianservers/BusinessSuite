"""Conditional photo responses, called only after file authorization succeeds."""
from pathlib import Path

from starlette.responses import FileResponse, Response


def private_file_response(path: str, request):
    file = Path(path)
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    # Only employee portraits qualify. Documents and arbitrary image attachments
    # keep no-store. Revalidation always runs token/session/permission checks.
    photo = file.parent.name == "photos" and file.suffix.lower() in {".jpg", ".jpeg", ".png"}
    if photo:
        headers["Cache-Control"] = "private, no-cache, must-revalidate"
        request.state.private_photo_cacheable = True
    response = FileResponse(str(file), filename=file.name, headers=headers, stat_result=file.stat())
    if photo:
        tags = request.headers.get("if-none-match", "")
        if any(tag.strip().removeprefix("W/") in {"*", response.headers["etag"]} for tag in tags.split(",")):
            return Response(status_code=304, headers={
                key: response.headers[key]
                for key in ("cache-control", "etag", "last-modified", "referrer-policy", "x-content-type-options")
            })
    return response
