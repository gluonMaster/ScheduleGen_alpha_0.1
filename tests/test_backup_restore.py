import io
import hashlib
import importlib
import json
import os
import re
import stat
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from gear_xls import backup_manager
from gear_xls import lock_manager
from gear_xls import restore_manager


MINIMAL_SCHEDULE_HTML = (
    "<html><head><style>.schedule-container{display:block}</style></head>"
    '<body><div id="menuDropdown"></div><div class="schedule-container"></div></body></html>'
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def project_root(tmp_path):
    root = tmp_path
    (root / "gear_xls" / "html_output").mkdir(parents=True)
    (root / "gear_xls" / "schedule_state").mkdir(parents=True)
    (root / "spiski").mkdir()
    (root / "xlsx_initial").mkdir()
    (root / "visualiser").mkdir()
    (root / "gui.py").write_text("", encoding="utf-8")
    (root / "gear_xls" / "server_routes.py").write_text("", encoding="utf-8")

    (root / "gear_xls" / "html_output" / "schedule.html").write_text(
        MINIMAL_SCHEDULE_HTML,
        encoding="utf-8",
    )
    _write_json(
        root / "gear_xls" / "schedule_state" / "base_schedule.json",
        {
            "published_at": "2026-05-01T10:00:00",
            "published_by": "admin",
            "blocks": [
                {
                    "building": "Villa",
                    "day": "Mo",
                    "room": "1.01",
                    "subject": "Math",
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "lesson_type": "group",
                }
            ],
        },
    )
    _write_json(
        root / "gear_xls" / "schedule_state" / "individual_lessons.json",
        {
            "last_modified": "2026-05-01T10:05:00",
            "blocks": [
                {
                    "id": "lesson-1",
                    "building": "Villa",
                    "day": "Di",
                    "room": "1.02",
                    "subject": "Deutsch",
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "lesson_type": "individual",
                }
            ],
        },
    )
    for filename in backup_manager.ALLOWED_SPISKI_FILENAMES:
        (root / "spiski" / filename).write_text(f"{filename} item\n", encoding="utf-8")
    return root


def _create_backup(project_root, comment=""):
    return backup_manager.create_backup(
        "admin",
        "Admin",
        comment=comment,
        project_root=str(project_root),
    )


def _read_zip_entry(path, name):
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _valid_entries(project_root, *, schedule_html=MINIMAL_SCHEDULE_HTML, schema=None, schema_version=None):
    effective_schema_version = (
        schema_version
        if schema_version is not None
        else backup_manager.BACKUP_SCHEMA_VERSION
    )
    base = {
        "published_at": "2026-05-01T10:00:00",
        "published_by": "admin",
        "blocks": [
            {
                "building": "Villa",
                "day": "Mo",
                "room": "1.01",
                "subject": "Math",
                "start_time": "10:00",
                "end_time": "11:00",
                "lesson_type": "group",
            }
        ],
    }
    individual = {
        "last_modified": "2026-05-01T10:05:00",
        "blocks": [
            {
                "id": "lesson-1",
                "building": "Villa",
                "day": "Di",
                "room": "1.02",
                "subject": "Deutsch",
                "start_time": "12:00",
                "end_time": "13:00",
                "lesson_type": "individual",
            }
        ],
    }
    entries = {
        "state/base_schedule.json": json.dumps(base).encode("utf-8"),
        "state/individual_lessons.json": json.dumps(individual).encode("utf-8"),
        "html/schedule.html": schedule_html.encode("utf-8"),
    }
    if effective_schema_version != 1:
        snapshot = {
            "schema_version": 1,
            "generation_id": "gen-test",
            "generated_at": "2026-05-01T10:00:00Z",
            "source": "test",
            "blocks": [
                {
                    "id": "group-1",
                    "building": "Villa",
                    "day": "Mo",
                    "room": "1.01",
                    "subject": "Math",
                    "teacher": "",
                    "students": "",
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "lesson_type": "group",
                }
            ],
        }
        entries[backup_manager.GROUP_OCCUPANCY_ARCHIVE_PATH] = json.dumps(snapshot).encode("utf-8")
    for archive_path in backup_manager.SPISKI_ARCHIVE_PATHS:
        entries[archive_path] = b"item\n"
    expected_content_paths = (
        backup_manager.V1_EXPECTED_CONTENT_PATHS
        if effective_schema_version == 1
        else backup_manager.EXPECTED_CONTENT_PATHS
    )
    manifest = {
        "schema": schema if schema is not None else backup_manager.BACKUP_SCHEMA,
        "schema_version": effective_schema_version,
        "backup_kind": "manual",
        "created_at": "2026-05-11T14:30:00Z",
        "created_by": "admin",
        "created_by_display_name": "Admin",
        "comment": "",
        "project_root_id": backup_manager.get_project_root_id(str(project_root)),
        "app": "Kolibri SchedGen",
        "source": "web_editor_persisted_state",
        "dirty_dom_included": False,
        "base_revision": base["published_at"],
        "individual_revision": individual["last_modified"],
        "includes": {
            "schedule_html": True,
            "base_schedule": True,
            "individual_lessons": True,
            "group_occupancy_snapshot": effective_schema_version != 1,
            "spiski": True,
            "lock_state": False,
            "restore_status": False,
            "source_excel": False,
        },
        "spiski_files": list(backup_manager.ALLOWED_SPISKI_FILENAMES),
        "files": [
            {
                "path": archive_path,
                "sha256": hashlib.sha256(entries[archive_path]).hexdigest(),
                "size": len(entries[archive_path]),
            }
            for archive_path in expected_content_paths
        ],
    }
    if effective_schema_version != 1:
        snapshot_data = json.loads(entries[backup_manager.GROUP_OCCUPANCY_ARCHIVE_PATH].decode("utf-8"))
        manifest["occupancy_snapshot"] = {
            "path": backup_manager.GROUP_OCCUPANCY_ARCHIVE_PATH,
            "generation_id": snapshot_data["generation_id"],
            "generated_at": snapshot_data["generated_at"],
            "source": snapshot_data["source"],
            "sha256": hashlib.sha256(entries[backup_manager.GROUP_OCCUPANCY_ARCHIVE_PATH]).hexdigest(),
        }
    return {"manifest.json": json.dumps(manifest).encode("utf-8"), **entries}


def _refresh_manifest(entries, **overrides):
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.update(overrides)
    for file_entry in manifest["files"]:
        data = entries[file_entry["path"]]
        file_entry["sha256"] = hashlib.sha256(data).hexdigest()
        file_entry["size"] = len(data)
    entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
    return entries


def _write_zip(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _zip_bytes(entries, *, info_by_name=None):
    output = io.BytesIO()
    info_by_name = info_by_name or {}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(info_by_name.get(name, name), data)
    return output.getvalue()


def _zip_bytes_with_raw_backslash_entry(project_root):
    entries = _valid_entries(project_root)
    entries["state/evil.json"] = b"evil"
    return _zip_bytes(entries).replace(b"state/evil.json", b"state\\evil.json")


def _login_admin(client):
    with client.session_transaction() as session:
        session["login"] = "admin"
        session["display_name"] = "Admin"
        session["role"] = "admin"


def _login_role(client, role, login=None):
    with client.session_transaction() as session:
        session["login"] = login or role
        session["display_name"] = (login or role).title()
        session["role"] = role


def _restore_status_path(project_root):
    return project_root / "gear_xls" / "schedule_state" / "restore_status.json"


def _utc_timestamp(seconds_ago=0):
    moment = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_restore_status(project_root, **overrides):
    status = dict(restore_manager.DEFAULT_RESTORE_STATUS)
    status.update(overrides)
    _write_json(_restore_status_path(project_root), status)
    return status


def _post_upload(client, payload, filename="client_backup.zip"):
    return client.post(
        "/api/backups/upload",
        data={"file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def test_create_backup_creates_expected_zip_and_manifest(project_root):
    backup = _create_backup(project_root, comment=" <b>plain text</b> ")
    assert backup["valid"] is True
    assert backup["id"].startswith("schedgen_backup_")

    with zipfile.ZipFile(backup_manager.get_backup_path(backup["id"], str(project_root))) as archive:
        assert set(archive.namelist()) == set(backup_manager.EXPECTED_ARCHIVE_PATHS)
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert manifest["schema"] == backup_manager.BACKUP_SCHEMA
    assert manifest["schema_version"] == backup_manager.BACKUP_SCHEMA_VERSION
    assert manifest["dirty_dom_included"] is False
    assert manifest["comment"] == "<b>plain text</b>"
    assert [entry["path"] for entry in manifest["files"]] == list(
        backup_manager.EXPECTED_CONTENT_PATHS
    )


def test_manifest_checksums_and_sizes_match_zip_entries(project_root):
    backup = _create_backup(project_root)
    path = backup_manager.get_backup_path(backup["id"], str(project_root))
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        for file_entry in manifest["files"]:
            data = archive.read(file_entry["path"])
            assert file_entry["size"] == len(data)
            assert file_entry["sha256"] == hashlib.sha256(data).hexdigest()


def test_missing_schedule_html_causes_clear_backup_error(project_root):
    os.remove(project_root / "gear_xls" / "html_output" / "schedule.html")
    with pytest.raises(backup_manager.BackupError) as excinfo:
        _create_backup(project_root)
    assert excinfo.value.code == "SCHEDULE_HTML_MISSING"


def test_missing_state_json_uses_empty_default_state(project_root):
    os.remove(project_root / "gear_xls" / "schedule_state" / "base_schedule.json")
    os.remove(project_root / "gear_xls" / "schedule_state" / "individual_lessons.json")
    backup = _create_backup(project_root)
    path = backup_manager.get_backup_path(backup["id"], str(project_root))

    assert json.loads(_read_zip_entry(path, "state/base_schedule.json")) == {
        "published_at": None,
        "published_by": None,
        "blocks": [],
    }
    assert json.loads(_read_zip_entry(path, "state/individual_lessons.json")) == {
        "last_modified": None,
        "blocks": [],
    }


def test_existing_invalid_state_json_fails_backup_creation(project_root):
    (project_root / "gear_xls" / "schedule_state" / "base_schedule.json").write_text(
        "{not json",
        encoding="utf-8",
    )
    with pytest.raises(backup_manager.BackupError) as excinfo:
        _create_backup(project_root)
    assert excinfo.value.code == "INVALID_JSON_STATE"


def test_missing_allowed_spiski_file_is_backed_up_as_empty_file(project_root):
    missing_name = backup_manager.ALLOWED_SPISKI_FILENAMES[0]
    os.remove(project_root / "spiski" / missing_name)
    backup = _create_backup(project_root)
    path = backup_manager.get_backup_path(backup["id"], str(project_root))
    assert _read_zip_entry(path, f"spiski/{missing_name}") == b""


def test_list_backups_returns_valid_metadata_and_marks_corrupted_zip(project_root):
    valid_backup = _create_backup(project_root)
    backup_dir = project_root / "gear_xls" / "backups"
    corrupted = backup_dir / "schedgen_backup_20990101_010101_deadbeef.zip"
    corrupted.write_bytes(b"not a zip")

    backups = backup_manager.list_backups(str(project_root))
    by_id = {item["id"]: item for item in backups}
    assert by_id[valid_backup["id"]]["valid"] is True
    assert by_id[valid_backup["id"]]["download_url"] == f"/api/backups/{valid_backup['id']}/download"
    assert by_id["schedgen_backup_20990101_010101_deadbeef"]["valid"] is False
    assert by_id["schedgen_backup_20990101_010101_deadbeef"]["invalid_reason"]


@pytest.fixture
def server_app(project_root, monkeypatch):
    monkeypatch.setenv("SCHEDGEN_PROJECT_ROOT", str(project_root))
    for module_name in (
        "auth",
        "base_schedule_manager",
        "state_manager",
        "lock_manager",
        "restore_manager",
        "gear_xls.server_routes",
    ):
        sys.modules.pop(module_name, None)
    server_routes = importlib.import_module("gear_xls.server_routes")
    server_routes.app.config.update(TESTING=True)
    return server_routes.app


def test_restore_status_default_returned_when_file_missing(project_root):
    assert not _restore_status_path(project_root).exists()
    assert restore_manager.get_restore_status(str(project_root)) == restore_manager.DEFAULT_RESTORE_STATUS


def test_restore_status_writes_are_persisted_and_read_back(project_root):
    started = restore_manager.begin_restore(
        "admin",
        "Restoring from backup",
        project_root=str(project_root),
    )

    assert started["active"] is True
    assert started["started_by"] == "admin"
    assert started["started_at"].endswith("Z")

    persisted = json.loads(_restore_status_path(project_root).read_text(encoding="utf-8"))
    assert persisted["active"] is True
    assert restore_manager.get_restore_status(str(project_root))["message"] == "Restoring from backup"

    completed = restore_manager.complete_restore(
        "admin",
        "schedgen_backup_20260511_120000_deadbeef",
        project_root=str(project_root),
    )
    assert completed["active"] is False
    assert completed["generation"] == started["generation"] + 1
    assert completed["last_completed_at"].endswith("Z")
    assert completed["last_restored_from"] == "schedgen_backup_20260511_120000_deadbeef"


def test_restore_status_api_requires_login_and_returns_json(server_app):
    with server_app.test_client() as client:
        unauthorized = client.get("/api/restore/status")
        _login_admin(client)
        authorized = client.get("/api/restore/status")

    assert unauthorized.status_code == 401
    assert unauthorized.is_json
    assert authorized.status_code == 200
    body = authorized.get_json()
    assert body["ok"] is True
    assert body["restore_in_progress"] is False
    assert body["active"] is False
    assert body["generation"] == 0


def test_restore_status_clear_requires_admin_and_confirm(project_root, server_app):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(restore_manager.RESTORE_STALE_AFTER_SECONDS + 5),
        started_by="admin",
    )

    with server_app.test_client() as client:
        _login_role(client, "editor")
        forbidden = client.post("/api/restore/status/clear", json={"confirm": True})
        _login_admin(client)
        missing_confirm = client.post("/api/restore/status/clear", json={})

    assert forbidden.status_code == 403
    assert missing_confirm.status_code == 400
    assert missing_confirm.get_json()["code"] == "CONFIRM_REQUIRED"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/lock/status"),
        ("POST", "/api/lock/acquire"),
        ("POST", "/api/lock/release"),
        ("POST", "/api/lock/heartbeat"),
        ("DELETE", "/api/lock"),
        ("GET", "/api/schedule"),
        ("GET", "/api/individual_lessons"),
        ("POST", "/api/schedule/publish"),
        ("POST", "/api/blocks"),
        ("PUT", "/api/blocks/block-1"),
        ("DELETE", "/api/blocks/block-1"),
        ("POST", "/api/blocks/block-1/convert"),
        ("POST", "/api/columns"),
        ("DELETE", "/api/columns"),
        ("POST", "/api/spiski/add"),
        ("POST", "/api/backups"),
        ("POST", "/api/backups/upload"),
        ("POST", "/export_to_excel"),
    ],
)
def test_active_restore_blocks_schedule_sensitive_endpoint_families(
    project_root, server_app, method, path
):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(),
        started_by="admin",
        message="Restore in progress",
        generation=5,
    )

    with server_app.test_client() as client:
        _login_admin(client)
        response = client.open(path, method=method, json={})

    assert response.status_code == 423
    body = response.get_json()
    assert body["code"] == "RESTORE_IN_PROGRESS"
    assert body["restore_generation"] == 5


def test_active_restore_allows_restore_status_and_api_status(project_root, server_app):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(),
        started_by="admin",
        message="Restore in progress",
        generation=6,
    )

    with server_app.test_client() as client:
        _login_admin(client)
        restore_response = client.get("/api/restore/status")
        status_response = client.get("/api/status")

    assert restore_response.status_code == 200
    assert restore_response.get_json()["restore_in_progress"] is True
    assert status_response.status_code == 200
    assert status_response.get_json()["restore"]["active"] is True
    assert status_response.get_json()["restore"]["generation"] == 6


def test_active_restore_does_not_serve_editable_schedule(project_root, server_app):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(),
        started_by="admin",
        message="Restore in progress",
    )

    with server_app.test_client() as client:
        _login_role(client, "editor")
        response = client.get("/schedule")

    body = response.get_data(as_text=True)
    assert response.status_code == 423
    assert "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" in body
    assert "schedule-container" not in body


def test_stale_non_recovery_restore_mode_can_be_cleared_by_admin(project_root, server_app):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(restore_manager.RESTORE_STALE_AFTER_SECONDS + 5),
        started_by="admin",
        message="Stale restore",
        generation=7,
    )

    with server_app.test_client() as client:
        _login_admin(client)
        response = client.post("/api/restore/status/clear", json={"confirm": True})

    assert response.status_code == 200
    status = response.get_json()["status"]
    assert status["active"] is False
    assert status["recovery_required"] is False
    assert status["generation"] == 7
    assert restore_manager.get_restore_status(str(project_root))["active"] is False


def test_recovery_mode_cannot_be_silently_auto_cleared(project_root, server_app):
    _write_restore_status(
        project_root,
        active=True,
        started_at=_utc_timestamp(restore_manager.RESTORE_STALE_AFTER_SECONDS + 5),
        started_by="admin",
        recovery_required=True,
        recovery_message="Manual recovery required",
        safety_backup_id="schedgen_backup_20260511_120000_deadbeef",
    )

    assert restore_manager.get_restore_status(str(project_root))["recovery_required"] is True

    with server_app.test_client() as client:
        _login_admin(client)
        status_response = client.get("/api/restore/status")
        missing_confirm = client.post("/api/restore/status/clear", json={})

    assert status_response.status_code == 200
    assert status_response.get_json()["recovery_required"] is True
    assert missing_confirm.status_code == 400
    assert missing_confirm.get_json()["code"] == "CONFIRM_REQUIRED"
    assert restore_manager.get_restore_status(str(project_root))["recovery_required"] is True


def test_api_status_includes_restore_fields(project_root, server_app):
    _write_restore_status(
        project_root,
        generation=12,
        last_completed_at="2026-05-11T10:00:00Z",
        last_completed_by="admin",
        last_restored_from="schedgen_backup_20260511_095500_deadbeef",
    )

    with server_app.test_client() as client:
        _login_admin(client)
        response = client.get("/api/status")

    assert response.status_code == 200
    restore = response.get_json()["restore"]
    assert restore == {
        "active": False,
        "generation": 12,
        "last_completed_at": "2026-05-11T10:00:00Z",
        "recovery_required": False,
        "message": None,
    }


def test_download_validates_backup_id_and_rejects_unsafe_ids(project_root, server_app):
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.get_backup_path("../evil", str(project_root))
    assert excinfo.value.code == "INVALID_BACKUP_ID"

    with server_app.test_client() as client:
        with client.session_transaction() as session:
            session["login"] = "admin"
            session["display_name"] = "Admin"
            session["role"] = "admin"
        response = client.get("/api/backups/not-a-valid-id/download")

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_BACKUP_ID"


def test_backup_api_create_and_list_for_admin(server_app):
    with server_app.test_client() as client:
        with client.session_transaction() as session:
            session["login"] = "admin"
            session["display_name"] = "Admin"
            session["role"] = "admin"
        created = client.post("/api/backups", json={"comment": "api backup"})
        listed = client.get("/api/backups")

    assert created.status_code == 200
    backup = created.get_json()["backup"]
    assert backup["backup_kind"] == "manual"
    assert backup["download_url"] == f"/api/backups/{backup['id']}/download"
    assert listed.status_code == 200
    listed_backups = listed.get_json()["backups"]
    assert any(item["id"] == backup["id"] and item["valid"] for item in listed_backups)


def test_backup_api_rejects_too_long_comment(server_app):
    with server_app.test_client() as client:
        with client.session_transaction() as session:
            session["login"] = "admin"
            session["display_name"] = "Admin"
            session["role"] = "admin"
        response = client.post("/api/backups", json={"comment": "x" * 501})

    assert response.status_code == 400
    assert response.get_json()["code"] == "COMMENT_TOO_LONG"


def test_validation_rejects_non_zip(project_root, tmp_path):
    path = tmp_path / "backup.zip"
    path.write_bytes(b"not a zip")
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "INVALID_BACKUP_ZIP"


def test_validation_rejects_path_traversal_zip_entry(project_root, tmp_path):
    entries = _valid_entries(project_root)
    entries["../evil.txt"] = b"evil"
    path = tmp_path / "backup.zip"
    _write_zip(path, entries)
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "UNSAFE_ZIP_ENTRY"


def test_validation_rejects_duplicate_zip_entries(project_root, tmp_path):
    entries = _valid_entries(project_root)
    path = tmp_path / "backup.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("html/schedule.html", entries["html/schedule.html"])
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "DUPLICATE_ZIP_ENTRY"


def test_validation_rejects_checksum_mismatch(project_root, tmp_path):
    entries = _valid_entries(project_root)
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
    path = tmp_path / "backup.zip"
    _write_zip(path, entries)
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "CHECKSUM_MISMATCH"


@pytest.mark.parametrize(
    ("schema", "schema_version", "expected_code"),
    [
        ("unknown", backup_manager.BACKUP_SCHEMA_VERSION, "UNSUPPORTED_BACKUP_SCHEMA"),
        (backup_manager.BACKUP_SCHEMA, 999, "UNSUPPORTED_BACKUP_SCHEMA_VERSION"),
    ],
)
def test_validation_rejects_unknown_schema_or_version(
    project_root, tmp_path, schema, schema_version, expected_code
):
    path = tmp_path / "backup.zip"
    _write_zip(
        path,
        _valid_entries(project_root, schema=schema, schema_version=schema_version),
    )
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == expected_code


def test_validation_rejects_extra_unexpected_file(project_root, tmp_path):
    entries = _valid_entries(project_root)
    entries["extra.txt"] = b"extra"
    path = tmp_path / "backup.zip"
    _write_zip(path, entries)
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "UNEXPECTED_BACKUP_FILE"


@pytest.mark.parametrize("marker", ["saveSchedule", "/save_intermediate"])
def test_validation_rejects_old_schedule_html_artifacts(project_root, tmp_path, marker):
    html = (
        "<html><head><style>.schedule-container{display:block}</style></head>"
        f'<body><div id="menuDropdown"></div><script>{marker}</script>'
        '<div class="schedule-container"></div></body></html>'
    )
    path = tmp_path / "backup.zip"
    _write_zip(path, _valid_entries(project_root, schedule_html=html))
    with pytest.raises(backup_manager.BackupError) as excinfo:
        backup_manager.validate_backup_zip(path)
    assert excinfo.value.code == "INVALID_SCHEDULE_HTML"


def test_upload_rejects_missing_file(server_app):
    with server_app.test_client() as client:
        _login_admin(client)
        response = client.post(
            "/api/backups/upload",
            data={},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert response.get_json()["code"] == "MISSING_UPLOAD_FILE"


def test_upload_rejects_empty_file(server_app):
    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, b"", "empty.zip")

    assert response.status_code == 400
    assert response.get_json()["code"] == "EMPTY_UPLOAD_FILE"


def test_upload_rejects_non_zip(server_app):
    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, b"not a zip", "not-a-backup.zip")

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_BACKUP_ZIP"


@pytest.mark.parametrize(
    ("unsafe_name", "expected_code"),
    [
        ("../evil.txt", "UNSAFE_ZIP_ENTRY"),
        ("/absolute.txt", "UNSAFE_ZIP_ENTRY"),
        ("C:/absolute.txt", "UNSAFE_ZIP_ENTRY"),
    ],
)
def test_upload_rejects_unsafe_zip_entry_paths(
    project_root, server_app, unsafe_name, expected_code
):
    entries = _valid_entries(project_root)
    entries[unsafe_name] = b"evil"

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes(entries))

    assert response.status_code == 400
    assert response.get_json()["code"] == expected_code


def test_upload_rejects_backslash_path_entry(project_root, server_app):
    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes_with_raw_backslash_entry(project_root))

    assert response.status_code == 400
    assert response.get_json()["code"] == "UNSAFE_ZIP_ENTRY"


def test_upload_rejects_symlink_entry(project_root, server_app):
    entries = _valid_entries(project_root)
    symlink_info = zipfile.ZipInfo("html/schedule.html")
    symlink_info.create_system = 3
    symlink_info.external_attr = (stat.S_IFLNK | 0o777) << 16

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(
            client,
            _zip_bytes(entries, info_by_name={"html/schedule.html": symlink_info}),
        )

    assert response.status_code == 400
    assert response.get_json()["code"] == "UNSAFE_ZIP_ENTRY"


def test_upload_rejects_duplicate_entries(project_root, server_app):
    entries = _valid_entries(project_root)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("html/schedule.html", entries["html/schedule.html"])

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, payload.getvalue())

    assert response.status_code == 400
    assert response.get_json()["code"] == "DUPLICATE_ZIP_ENTRY"


def test_upload_rejects_checksum_mismatch(project_root, server_app):
    entries = _valid_entries(project_root)
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    entries["manifest.json"] = json.dumps(manifest).encode("utf-8")

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes(entries))

    assert response.status_code == 400
    assert response.get_json()["code"] == "CHECKSUM_MISMATCH"


@pytest.mark.parametrize(
    ("schema", "schema_version", "expected_code"),
    [
        ("unknown", backup_manager.BACKUP_SCHEMA_VERSION, "UNSUPPORTED_BACKUP_SCHEMA"),
        (backup_manager.BACKUP_SCHEMA, 999, "UNSUPPORTED_BACKUP_SCHEMA_VERSION"),
    ],
)
def test_upload_rejects_unknown_schema_or_version(
    project_root, server_app, schema, schema_version, expected_code
):
    entries = _valid_entries(project_root, schema=schema, schema_version=schema_version)

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes(entries))

    assert response.status_code == 400
    assert response.get_json()["code"] == expected_code


def test_upload_rejects_extra_unexpected_file(project_root, server_app):
    entries = _valid_entries(project_root)
    entries["extra.txt"] = b"extra"

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes(entries))

    assert response.status_code == 400
    assert response.get_json()["code"] == "UNEXPECTED_BACKUP_FILE"


def test_upload_rejects_old_schedule_html_artifacts(project_root, server_app):
    html = (
        "<html><head><style>.schedule-container{display:block}</style></head>"
        '<body><div id="menuDropdown"></div><script>saveSchedule</script>'
        '<div class="schedule-container"></div></body></html>'
    )

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(
            client,
            _zip_bytes(_valid_entries(project_root, schedule_html=html)),
        )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_SCHEDULE_HTML"


def test_valid_upload_is_stored_under_safe_filename_and_listed_as_uploaded(
    project_root, server_app
):
    payload = _zip_bytes(_valid_entries(project_root))

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, payload, "../user-chosen-name.zip")
        listed = client.get("/api/backups")

    assert response.status_code == 200
    body = response.get_json()
    backup = body["backup"]
    assert body["warnings"] == []
    assert backup["backup_kind"] == "uploaded"
    assert backup["project_root_matches"] is True
    assert backup["filename"] != "user-chosen-name.zip"
    assert re.fullmatch(r"schedgen_backup_\d{8}_\d{6}_[0-9a-f]{8}\.zip", backup["filename"])

    path = backup_manager.get_backup_path(backup["id"], str(project_root))
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    assert manifest["backup_kind"] == "uploaded"
    assert manifest["uploaded_by"] == "admin"
    assert manifest["uploaded_original_filename"] == "user-chosen-name.zip"

    listed_backups = listed.get_json()["backups"]
    assert any(
        item["id"] == backup["id"] and item["backup_kind"] == "uploaded"
        for item in listed_backups
    )


def test_project_mismatch_upload_succeeds_with_warning(project_root, server_app):
    entries = _valid_entries(project_root)
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["project_root_id"] = "foreign-project-root"
    entries["manifest.json"] = json.dumps(manifest).encode("utf-8")

    with server_app.test_client() as client:
        _login_admin(client)
        response = _post_upload(client, _zip_bytes(entries), "foreign.zip")
        listed = client.get("/api/backups")

    assert response.status_code == 200
    body = response.get_json()
    assert body["backup"]["backup_kind"] == "uploaded"
    assert body["backup"]["project_root_matches"] is False
    assert body["warnings"] == ["PROJECT_ROOT_MISMATCH"]

    listed_backup = next(
        item for item in listed.get_json()["backups"] if item["id"] == body["backup"]["id"]
    )
    assert listed_backup["backup_kind"] == "uploaded"
    assert listed_backup["project_root_matches"] is False


def test_restore_route_requires_admin(server_app, project_root):
    backup = _create_backup(project_root)

    with server_app.test_client() as client:
        _login_role(client, "editor")
        response = client.post(
            f"/api/backups/{backup['id']}/restore",
            json={"confirm": True},
        )

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_restore_route_requires_confirm(server_app, project_root):
    backup = _create_backup(project_root)

    with server_app.test_client() as client:
        _login_admin(client)
        assert client.post("/api/lock/acquire").status_code == 200
        response = client.post(f"/api/backups/{backup['id']}/restore", json={})

    assert response.status_code == 400
    assert response.get_json()["code"] == "CONFIRM_REQUIRED"


def test_restore_route_requires_active_lock_held_by_current_admin(server_app, project_root):
    backup = _create_backup(project_root)

    with server_app.test_client() as client:
        _login_admin(client)
        response = client.post(
            f"/api/backups/{backup['id']}/restore",
            json={"confirm": True},
        )

    assert response.status_code == 403
    assert response.get_json()["code"] == "NO_LOCK"


def test_restore_rejects_project_mismatch_without_allow(server_app, project_root):
    backup = _create_backup(project_root)
    path = backup_manager.get_backup_path(backup["id"], str(project_root))
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    _refresh_manifest(entries, project_root_id="foreign-project-root")
    _write_zip(path, entries)

    with server_app.test_client() as client:
        _login_admin(client)
        assert client.post("/api/lock/acquire").status_code == 200
        response = client.post(
            f"/api/backups/{backup['id']}/restore",
            json={"confirm": True},
        )

    assert response.status_code == 409
    assert response.get_json()["code"] == "PROJECT_ROOT_MISMATCH"


def test_restore_writes_state_spiski_html_revisions_and_clears_lock(server_app, project_root):
    backup = _create_backup(project_root)
    _write_json(
        project_root / "gear_xls" / "schedule_state" / "base_schedule.json",
        {"published_at": None, "published_by": None, "blocks": []},
    )
    _write_json(
        project_root / "gear_xls" / "schedule_state" / "individual_lessons.json",
        {"last_modified": None, "blocks": []},
    )
    for filename in backup_manager.ALLOWED_SPISKI_FILENAMES:
        (project_root / "spiski" / filename).write_text("changed\n", encoding="utf-8")
    (project_root / "gear_xls" / "html_output" / "schedule.html").write_text(
        MINIMAL_SCHEDULE_HTML.replace("schedule-container", "changed schedule-container"),
        encoding="utf-8",
    )

    with server_app.test_client() as client:
        _login_admin(client)
        assert client.post("/api/lock/acquire").get_json()["ok"] is True
        response = client.post(
            f"/api/backups/{backup['id']}/restore",
            json={"confirm": True},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["restored_from"] == backup["id"]
    assert body["safety_backup"]["id"].startswith("schedgen_backup_")
    assert body["base_revision"] == body["individual_revision"]
    assert body["restore_generation"] == 1

    base = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "base_schedule.json").read_text(
            encoding="utf-8"
        )
    )
    individual = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "individual_lessons.json").read_text(
            encoding="utf-8"
        )
    )
    assert base["published_at"] == body["base_revision"]
    assert base["published_by"] == "admin"
    assert base["blocks"][0]["subject"] == "Math"
    assert individual["last_modified"] == body["individual_revision"]
    assert individual["blocks"][0]["subject"] == "Deutsch"
    assert (project_root / "spiski" / "teachers.txt").read_text(encoding="utf-8") == "teachers.txt item\n"
    assert "changed schedule-container" not in (
        project_root / "gear_xls" / "html_output" / "schedule.html"
    ).read_text(encoding="utf-8")

    lock_state = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock_state["holder"] is None
    assert lock_state["last_holder"] == "admin"
    assert lock_state["released_by"] == "admin"
    assert lock_state["release_reason"] == "restore_completed"

    backups = backup_manager.list_backups(str(project_root))
    assert any(item["id"] == body["safety_backup"]["id"] and item["backup_kind"] == "safety" for item in backups)


def test_restore_keeps_empty_unpublished_base_revision_null(project_root):
    entries = _valid_entries(project_root)
    entries["state/base_schedule.json"] = json.dumps(
        {"published_at": None, "published_by": None, "blocks": []}
    ).encode("utf-8")
    _refresh_manifest(entries, base_revision=None)
    backup_dir = project_root / "gear_xls" / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_id = "schedgen_backup_20260511_120000_deadbeef"
    _write_zip(backup_dir / f"{backup_id}.zip", entries)

    lock_manager.acquire_lock("admin", project_root=str(project_root))
    result = restore_manager.restore_backup(
        backup_id,
        "admin",
        "Admin",
        project_root=str(project_root),
    )

    assert result["base_revision"] is None
    base = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "base_schedule.json").read_text(
            encoding="utf-8"
        )
    )
    assert base["published_at"] is None
    assert base["published_by"] is None


def test_restore_normalizes_trial_dates_and_removes_stale_non_trial_dates(project_root):
    entries = _valid_entries(project_root)
    individual = {
        "last_modified": "2026-05-01T10:05:00",
        "blocks": [
            {
                "id": "trial-1",
                "building": "Villa",
                "day": "Mo",
                "room": "1.02",
                "subject": "Trial",
                "start_time": "12:00",
                "end_time": "13:00",
                "lesson_type": "trial",
                "trial_dates": ["2026-05-11", "2026-05-04", "2026-05-04"],
            },
            {
                "id": "lesson-2",
                "building": "Villa",
                "day": "Di",
                "room": "1.03",
                "subject": "Deutsch",
                "start_time": "14:00",
                "end_time": "15:00",
                "lesson_type": "individual",
                "trial_dates": ["not-a-date"],
            },
        ],
    }
    entries["state/individual_lessons.json"] = json.dumps(individual).encode("utf-8")
    _refresh_manifest(entries, individual_revision=individual["last_modified"])
    backup_dir = project_root / "gear_xls" / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_id = "schedgen_backup_20260511_121000_deadbeef"
    _write_zip(backup_dir / f"{backup_id}.zip", entries)

    lock_manager.acquire_lock("admin", project_root=str(project_root))
    restore_manager.restore_backup(
        backup_id,
        "admin",
        "Admin",
        project_root=str(project_root),
    )

    restored = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "individual_lessons.json").read_text(
            encoding="utf-8"
        )
    )
    trial, regular = restored["blocks"]
    assert trial["trial_dates"] == ["2026-05-04", "2026-05-11"]
    assert "trial_dates" not in regular


def test_restore_domain_validation_rejects_invalid_time_and_lesson_type(project_root):
    entries = _valid_entries(project_root)
    base = json.loads(entries["state/base_schedule.json"].decode("utf-8"))
    base["blocks"][0]["end_time"] = "10:00"
    entries["state/base_schedule.json"] = json.dumps(base).encode("utf-8")
    _refresh_manifest(entries, base_revision=base["published_at"])
    backup_dir = project_root / "gear_xls" / "backups"
    backup_dir.mkdir(exist_ok=True)
    invalid_time_id = "schedgen_backup_20260511_122000_deadbeef"
    _write_zip(backup_dir / f"{invalid_time_id}.zip", entries)

    lock_manager.acquire_lock("admin", project_root=str(project_root))
    with pytest.raises(restore_manager.RestoreError) as invalid_time:
        restore_manager.restore_backup(
            invalid_time_id,
            "admin",
            "Admin",
            project_root=str(project_root),
        )
    assert invalid_time.value.code == "INVALID_JSON_STATE"

    entries = _valid_entries(project_root)
    individual = json.loads(entries["state/individual_lessons.json"].decode("utf-8"))
    individual["blocks"][0]["lesson_type"] = "group"
    entries["state/individual_lessons.json"] = json.dumps(individual).encode("utf-8")
    _refresh_manifest(entries, individual_revision=individual["last_modified"])
    invalid_type_id = "schedgen_backup_20260511_123000_deadbeef"
    _write_zip(backup_dir / f"{invalid_type_id}.zip", entries)

    with pytest.raises(restore_manager.RestoreError) as invalid_type:
        restore_manager.restore_backup(
            invalid_type_id,
            "admin",
            "Admin",
            project_root=str(project_root),
        )
    assert invalid_type.value.code == "INVALID_JSON_STATE"


def test_partial_restore_failure_rolls_back_from_safety_backup(project_root, monkeypatch):
    original_base = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "base_schedule.json").read_text(
            encoding="utf-8"
        )
    )
    backup = _create_backup(project_root)
    with zipfile.ZipFile(backup_manager.get_backup_path(backup["id"], str(project_root))) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    base = json.loads(entries["state/base_schedule.json"].decode("utf-8"))
    base["blocks"][0]["subject"] = "Restored"
    entries["state/base_schedule.json"] = json.dumps(base).encode("utf-8")
    _refresh_manifest(entries, base_revision=base["published_at"])
    _write_zip(backup_manager.get_backup_path(backup["id"], str(project_root)), entries)

    calls = {"count": 0}
    original_replace = restore_manager._replace_file

    def flaky_replace(path, data):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated replace failure")
        return original_replace(path, data)

    monkeypatch.setattr(restore_manager, "_replace_file", flaky_replace)
    lock_manager.acquire_lock("admin", project_root=str(project_root))

    with pytest.raises(restore_manager.RestoreError) as excinfo:
        restore_manager.restore_backup(
            backup["id"],
            "admin",
            "Admin",
            project_root=str(project_root),
        )

    assert excinfo.value.code == "RESTORE_ROLLED_BACK"
    rolled_back_base = json.loads(
        (project_root / "gear_xls" / "schedule_state" / "base_schedule.json").read_text(
            encoding="utf-8"
        )
    )
    assert rolled_back_base["blocks"] == original_base["blocks"]
    status = restore_manager.get_restore_status(str(project_root))
    assert status["active"] is False
    assert status["generation"] == 1


def test_rollback_failure_sets_recovery_required(project_root, monkeypatch):
    backup = _create_backup(project_root)
    calls = {"count": 0}
    original_replace = restore_manager._replace_file

    def failing_replace(path, data):
        calls["count"] += 1
        if calls["count"] in (2, 3):
            raise OSError("simulated rollback failure")
        return original_replace(path, data)

    monkeypatch.setattr(restore_manager, "_replace_file", failing_replace)
    lock_manager.acquire_lock("admin", project_root=str(project_root))

    with pytest.raises(restore_manager.RestoreError) as excinfo:
        restore_manager.restore_backup(
            backup["id"],
            "admin",
            "Admin",
            project_root=str(project_root),
        )

    assert excinfo.value.code == "RESTORE_PARTIAL_FAILURE"
    status = restore_manager.get_restore_status(str(project_root))
    assert status["active"] is True
    assert status["recovery_required"] is True
    assert status["safety_backup_id"]
