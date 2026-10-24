from uuid import uuid4
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.project_management.chat_models import ChatMessage, ChatMember
from app.models.notification import Notification


def create(client, wid, h, **kw):
    result = client.post(
        f"{BASE}/workspaces/{wid}/chat/conversations", headers=h, json=kw
    )
    assert result.status_code == 201, result.text
    return result.json()


def send(client, path, h, body="hello", **kw):
    result = client.post(
        path + "/messages",
        headers=h,
        json={"body": body, "client_id": str(uuid4()), **kw},
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_channels_threads_read_search_files_and_revocation(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    base = f"{BASE}/workspaces/{wid}/chat"
    assert (
        client.post(
            base + "/conversations",
            headers=mh,
            json={"kind": "channel", "name": "denied"},
        ).status_code
        == 403
    )
    room = create(
        client,
        wid,
        oh,
        kind="channel",
        name="secret",
        participants=[member.id],
        visibility="private",
    )
    path = base + f"/conversations/{room['id']}"
    assert not any(
        r["name"] == "secret"
        for r in client.get(base + "/conversations", headers=ah).json()["conversations"]
    )
    assert client.get(path + "/messages", headers=ah).status_code == 404
    root = send(client, path, oh, "alpha secret")
    reply = send(client, path, mh, "beta reply", parent_id=root["id"])
    assert len(client.get(path + "/messages", headers=mh).json()["messages"]) == 1
    assert (
        client.get(path + f"/messages?parent_id={root['id']}", headers=mh).json()[
            "messages"
        ][0]["id"]
        == reply["id"]
    )
    assert (
        client.post(
            path + "/messages",
            headers=mh,
            json={"body": "x", "client_id": str(uuid4()), "parent_id": reply["id"]},
        ).status_code
        == 422
    )
    assert client.get(base + "/search?q=alpha", headers=ah).json()["results"] == []
    assert (
        client.get(base + "/search?q=alpha", headers=mh).json()["results"][0]["id"]
        == root["id"]
    )
    attachment = client.post(
        path + "/attachments",
        headers=oh,
        files={"file": ("note.txt", b"safe file", "text/plain")},
    )
    assert attachment.status_code == 201, attachment.text
    aid = attachment.json()["id"]
    assert client.get(path + f"/attachments/{aid}", headers=mh).status_code == 404
    filemsg = send(client, path, oh, "", attachment_ids=[aid])
    assert client.get(path + f"/attachments/{aid}", headers=mh).content == b"safe file"
    assert client.get(path + f"/attachments/{aid}", headers=ah).status_code == 404
    assert (
        client.get(base + "/search?q=note.txt&attachments=true", headers=mh).json()[
            "results"
        ][0]["id"]
        == filemsg["id"]
    )
    assert (
        client.post(
            path + "/attachments",
            headers=oh,
            files={"file": ("attack.svg", b"<svg/>", "image/svg+xml")},
        ).status_code
        == 422
    )
    assert (
        client.put(
            path + "/read", headers=mh, json={"message_id": filemsg["id"]}
        ).status_code
        == 200
    )
    client.put(path + "/read", headers=mh, json={"message_id": root["id"]})
    assert db.get(ChatMember, (room["id"], member.id)).read_id == filemsg["id"]
    assert (
        client.delete(path + f"/messages/{filemsg['id']}", headers=oh).status_code
        == 200
    )
    assert client.get(path + f"/attachments/{aid}", headers=mh).status_code == 404
    assert client.delete(path + f"/members/{member.id}", headers=oh).status_code == 200
    assert client.get(path + "/messages", headers=mh).status_code == 404
    assert client.get(base + "/search?q=alpha", headers=mh).json()["results"] == []


def test_groups_history_idempotency_mute_and_legacy(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    other, xh = account(db, "chat-other@example.invalid")
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=other.id, role="Member"))
    db.commit()
    base = f"{BASE}/workspaces/{wid}/chat"
    room = create(
        client, wid, oh, kind="group", name="Group", participants=[member.id, other.id]
    )
    path = base + f"/conversations/{room['id']}"
    old = send(client, path, oh, "old history")
    admin_id = client.get(f"{BASE}/workspaces/{wid}/members", headers=oh).json()
    admin_id = next(m["user_id"] for m in admin_id if m["role"] == "Admin")
    assert (
        client.post(
            path + "/members", headers=mh, json={"user_id": admin_id}
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + "/members", headers=oh, json={"user_id": admin_id}
        ).status_code
        == 200
    )
    assert client.get(path + "/messages", headers=ah).json()["messages"] == []
    assert client.get(base + "/search?q=old", headers=ah).json()["results"] == []
    assert (
        client.post(
            path + "/messages",
            headers=ah,
            json={"body": "x", "client_id": str(uuid4()), "parent_id": old["id"]},
        ).status_code
        == 422
    )
    client.put(path + "/mute", headers=mh, json={"muted": True})
    before = (
        db.query(Notification)
        .filter_by(user_id=member.id, event_type="chat.message")
        .count()
    )
    key = str(uuid4())
    payload = {"body": "new", "client_id": key}
    a = client.post(path + "/messages", headers=oh, json=payload)
    b = client.post(path + "/messages", headers=oh, json=payload)
    assert a.json()["id"] == b.json()["id"]
    assert (
        db.query(Notification)
        .filter_by(user_id=member.id, event_type="chat.message")
        .count()
        == before
    )
    assert (
        client.post(
            path + "/messages", headers=oh, json={**payload, "body": "different"}
        ).status_code
        == 409
    )
    assert (
        client.get(path + "/messages", headers=ah).json()["messages"][0]["body"]
        == "new"
    )
    hidden = send(client, path, oh, "old thread continuation", parent_id=old["id"])
    assert (
        client.get(base + "/search?q=continuation", headers=ah).json()["results"] == []
    )
    assert (
        client.get(path + f"/messages?around={hidden['id']}", headers=ah).status_code
        == 404
    )
    dm = create(client, wid, oh, kind="dm", participants=[member.id])
    assert create(client, wid, mh, kind="dm", participants=[owner.id])["id"] == dm["id"]
    dm_path = base + f"/conversations/{dm['id']}"
    msg = send(client, dm_path, oh, "compatible")
    assert msg["legacy_message_id"]
    old_dm = client.get(
        f"{BASE}/workspaces/{wid}/direct-conversations", headers=oh
    ).json()["conversations"][0]["id"]
    assert (
        client.get(
            f"{BASE}/workspaces/{wid}/direct-conversations/{old_dm}/messages",
            headers=mh,
        ).json()["messages"][0]["id"]
        == msg["legacy_message_id"]
    )
    db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=member.id).delete()
    db.commit()
    assert client.get(dm_path + "/messages", headers=mh).status_code == 404


def test_public_archive_pagination_foreign_parent_and_workspace_scope(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    base = f"{BASE}/workspaces/{wid}/chat"
    room = create(client, wid, oh, kind="channel", name="public", visibility="public")
    path = base + f"/conversations/{room['id']}"
    assert client.get(path + "/messages", headers=mh).status_code == 404
    assert client.post(path + "/join", headers=gh).status_code == 403
    assert client.post(path + "/join", headers=mh).status_code == 200
    roots = [send(client, path, oh, f"record {i}") for i in range(5)]
    page = client.get(path + "/messages?limit=2", headers=mh).json()
    assert [m["id"] for m in page["messages"]] == [r["id"] for r in roots[-2:]]
    older = client.get(
        path + f"/messages?limit=2&before={page['before']}", headers=mh
    ).json()
    assert not set(m["id"] for m in page["messages"]) & set(
        m["id"] for m in older["messages"]
    )
    assert (
        client.get(path + f"/messages?around={roots[0]['id']}", headers=mh).json()[
            "messages"
        ][-1]["id"]
        == roots[0]["id"]
    )
    second = create(
        client, wid, oh, kind="channel", name="other", participants=[member.id]
    )
    assert (
        client.post(
            base + f"/conversations/{second['id']}/messages",
            headers=mh,
            json={
                "body": "forged",
                "client_id": str(uuid4()),
                "parent_id": roots[0]["id"],
            },
        ).status_code
        == 422
    )
    other = client.post(
        BASE + "/workspaces", headers=oh, json={"name": "isolated"}
    ).json()["id"]
    assert (
        client.get(
            f"{BASE}/workspaces/{other}/chat/conversations/{room['id']}/messages",
            headers=oh,
        ).status_code
        == 404
    )
    assert (
        client.put(
            path, headers=oh, json={"name": "public", "archived": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            path + "/messages",
            headers=mh,
            json={"body": "blocked", "client_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert client.get(path + "/messages", headers=mh).status_code == 200
    unread = client.get(BASE + "/messaging/unread", headers=mh).json()["unread"]
    assert unread == 5
    assert client.post(base + "/read-all", headers=mh).status_code == 200
    assert client.get(BASE + "/messaging/unread", headers=mh).json()["unread"] == 0


def test_additive_migrations_repeat_and_history_backfill(client, db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.apps.project_management.models import PMSWorkspaceEntry

    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    entry = PMSWorkspaceEntry(
        workspace_id=wid, author_id=owner.id, kind="chat", body="preserved"
    )
    db.add(entry)
    db.commit()
    entry_id = entry.id
    db.add_all(
        [
            PMSWorkspaceEntry(
                workspace_id=wid,
                author_id=owner.id,
                kind="chat",
                body=f"chunked history {i}",
            )
            for i in range(201)
        ]
    )
    db.commit()
    for filename in [
        "alembic/versions/20261024_005_messaging.py",
        "alembic_postgresql/versions/pg_20261024_005_messaging.py",
    ]:
        path = Path(__file__).resolve().parents[1] / filename
        spec = importlib.util.spec_from_file_location("chat_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.op = Operations(MigrationContext.configure(db.connection()))
        module.upgrade()
        module.upgrade()
    path = f"{BASE}/workspaces/{wid}/chat/conversations"
    client.get(path, headers=oh)
    client.get(path, headers=oh)
    assert db.query(ChatMessage).filter_by(legacy_entry_id=entry_id).count() == 1
    assert (
        db.query(ChatMessage).filter(ChatMessage.legacy_entry_id.is_not(None)).count()
        == 202
    )
    assert db.get(PMSWorkspaceEntry, entry_id).body == "preserved"
    assert db.query(Notification).filter_by(event_type="chat.message").count() == 0


def test_upload_cleanup_project_file_retention_and_bounds(
    client, db, tmp_path, monkeypatch
):
    from datetime import datetime, timedelta
    from app.core.config import settings
    from app.apps.project_management.chat_cleanup import (
        cleanup_chat_uploads,
        delete_chat_blob,
    )
    from app.apps.project_management.chat_models import ChatAttachment
    from app.apps.project_management.models import PMSFileAsset
    import pytest

    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    room = create(client, wid, oh, kind="channel", name="files")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    root = tmp_path / "pms" / "chat" / str(room["id"])
    root.mkdir(parents=True)
    abandoned = root / "stale.txt"
    abandoned.write_text("stale")
    source = tmp_path / "source.txt"
    source.write_text("project original")
    f = PMSFileAsset(
        project_id=pid,
        file_name="source.txt",
        original_name="source.txt",
        storage_path=str(source),
    )
    db.add(f)
    db.flush()
    for path, fileid in [(abandoned, None), (source, f.id)]:
        db.add(
            ChatAttachment(
                conversation_id=room["id"],
                owner_id=owner.id,
                name=path.name,
                mime="text/plain",
                size=5,
                path=str(path),
                project_file_id=fileid,
                created_at=datetime.utcnow() - timedelta(days=2),
            )
        )
    db.commit()
    assert cleanup_chat_uploads(db)["removed"] == 2
    assert not abandoned.exists() and source.read_text() == "project original"
    with pytest.raises(ValueError):
        delete_chat_blob(str(source))


def test_group_owner_transfer_and_guest_management(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    admin_id = next(
        m["user_id"]
        for m in client.get(f"{BASE}/workspaces/{wid}/members", headers=oh).json()
        if m["role"] == "Admin"
    )
    room = create(client, wid, oh, kind="group", participants=[member.id, admin_id])
    path = f"{BASE}/workspaces/{wid}/chat/conversations/{room['id']}"
    assert client.delete(path + f"/members/{owner.id}", headers=oh).status_code == 200
    assert client.get(path + "/messages", headers=oh).status_code == 404
    assert client.get(path + "/messages", headers=mh).status_code == 200


def test_attachment_ownership_atomicity_and_project_sharing(
    client, db, tmp_path, monkeypatch
):
    from app.core.config import settings
    from app.apps.project_management.models import PMSFileAsset
    from app.apps.project_management.chat_models import ChatAttachment

    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    room = create(
        client, wid, oh, kind="channel", name="attachments", participants=[member.id]
    )
    base = f"{BASE}/workspaces/{wid}/chat"
    path = base + f"/conversations/{room['id']}"
    uploaded = client.post(
        path + "/attachments",
        headers=oh,
        files={"file": ("../../safe.txt", b"harmless", "text/plain")},
    ).json()
    assert uploaded["name"] == "safe.txt"
    for headers, ids in [(mh, [uploaded["id"]]), (oh, [uploaded["id"], 999999])]:
        assert (
            client.post(
                path + "/messages",
                headers=headers,
                json={"client_id": str(uuid4()), "attachment_ids": ids},
            ).status_code
            == 422
        )
    assert db.query(ChatMessage).filter_by(conversation_id=room["id"]).count() == 0
    assert db.get(ChatAttachment, uploaded["id"]).message_id is None
    send(client, path, oh, "", attachment_ids=[uploaded["id"]])
    assert (
        client.post(
            path + "/messages",
            headers=oh,
            json={"client_id": str(uuid4()), "attachment_ids": [uploaded["id"]]},
        ).status_code
        == 422
    )
    source = tmp_path / "project.txt"
    source.write_text("original project content")
    f = PMSFileAsset(
        project_id=pid,
        file_name="project.txt",
        original_name="project.txt",
        storage_path=str(source),
        mime_type="text/plain",
        size_bytes=24,
    )
    db.add(f)
    db.commit()
    assert (
        client.get(base + "/project-files", headers=oh).json()["items"][0]["id"] == f.id
    )
    staged = client.post(path + "/project-file", headers=oh, json={"file_id": f.id})
    assert staged.status_code == 201, staged.text
    shared = send(client, path, oh, "", attachment_ids=[staged.json()["id"]])
    assert (
        client.get(path + f"/attachments/{staged.json()['id']}", headers=mh).content
        == b"original project content"
    )
    other = client.post(
        BASE + "/workspaces", headers=oh, json={"name": "Foreign workspace"}
    ).json()["id"]
    otherpid = client.post(
        BASE + "/projects",
        headers=oh,
        json={"name": "Foreign", "project_key": "FOREIGNCHAT", "workspace_id": other},
    ).json()["id"]
    foreign = PMSFileAsset(
        project_id=otherpid,
        file_name="private.txt",
        original_name="private.txt",
        storage_path=str(source),
    )
    db.add(foreign)
    db.commit()
    assert (
        client.post(
            path + "/project-file", headers=oh, json={"file_id": foreign.id}
        ).status_code
        == 422
    )
    assert not any(
        x["id"] == foreign.id
        for x in client.get(base + "/project-files", headers=oh).json()["items"]
    )
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    assert (
        client.post(
            path + "/attachments",
            headers=oh,
            files={"file": ("large.txt", b"x" * (1024 * 1024 + 1), "text/plain")},
        ).status_code
        == 413
    )
    assert (
        client.post(
            path + "/attachments",
            headers=oh,
            files={"file": ("fake.png", b"not a PNG", "image/png")},
        ).status_code
        == 422
    )


def test_organization_mismatch_and_search_validation(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    base = f"{BASE}/workspaces/{wid}/chat"
    owner.organization_id = 998
    assert client.get(base + "/conversations", headers=oh).status_code == 404
    assert client.get(base + "/search?q=private", headers=oh).status_code == 404
    owner.organization_id = None
    assert (
        client.get(
            base + "/search?q=" + "+".join(["word"] * 13), headers=oh
        ).status_code
        == 422
    )
    assert (
        client.get(
            base + "/search?date_from=2026-10-20&date_to=2026-10-01", headers=oh
        ).status_code
        == 422
    )
