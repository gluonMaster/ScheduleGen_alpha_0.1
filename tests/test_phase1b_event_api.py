import importlib
import json
import sys

import pytest

from gear_xls import base_schedule_manager
from gear_xls import group_occupancy_snapshot
from gear_xls import schedule_mutation_coordinator


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_state(*blocks, published_at="base-1"):
    return {
        "published_at": published_at,
        "published_by": "admin" if published_at else None,
        "blocks": list(blocks),
    }


def _individual_state(*blocks):
    return {"last_modified": "state-1", "blocks": list(blocks)}


def _event(block_id="event-1", created_by="em1", owner_kind="event_manager", version=1, **overrides):
    block = {
        "id": block_id,
        "day": "Mo",
        "building": "Villa",
        "room": "0.04",
        "start_time": "10:00",
        "end_time": "11:00",
        "lesson_type": "veranstaltung",
        "subject": "Veranstaltung",
        "teacher": "Event Manager 1",
        "students": "Parents",
        "color": "#7c3aed",
        "event_dates": [],
        "created_by": created_by,
        "created_by_name": "Event Manager 1",
        "owner_kind": owner_kind,
        "version": version,
    }
    block.update(overrides)
    return block


def _regular_block(**overrides):
    block = {
        "day": "Mo",
        "building": "Villa",
        "room": "0.04",
        "start_time": "10:30",
        "end_time": "11:30",
        "lesson_type": "individual",
        "subject": "Deutsch",
        "teacher": "Teacher",
        "students": "Student",
    }
    block.update(overrides)
    return block


def _event_payload(**overrides):
    payload = {
        "day": "Mo",
        "building": "Villa",
        "room": "0.04",
        "start_time": "10:00",
        "end_time": "11:00",
        "students": "Parents",
        "event_dates": ["2026-07-10", "2026-07-10", "2026-07-03"],
        "subject": "Unsafe",
        "teacher": "Unsafe",
        "created_by": "someone-else",
        "owner_kind": "admin",
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def event_server(tmp_path, monkeypatch):
    server_routes = importlib.import_module("gear_xls.server_routes")
    server_routes.app.config.update(TESTING=True)

    individual_path = tmp_path / "individual_lessons.json"
    base_path = tmp_path / "base_schedule.json"
    snapshot_path = tmp_path / "group_occupancy_snapshot.json"
    coordinator_path = tmp_path / "schedule_mutation.lock"

    route_state_manager = server_routes.state_manager
    monkeypatch.setattr(route_state_manager, "INDIVIDUAL_LESSONS_PATH", str(individual_path))
    monkeypatch.setattr(route_state_manager, "INDIVIDUAL_LOCK_PATH", str(individual_path) + ".lock")
    monkeypatch.setattr(route_state_manager, "SCHEDULE_HTML_PATH", str(tmp_path / "missing_schedule.html"))
    monkeypatch.setattr(base_schedule_manager, "BASE_SCHEDULE_PATH", str(base_path))
    monkeypatch.setattr(base_schedule_manager, "BASE_LOCK_PATH", str(base_path) + ".lock")
    top_level_base = sys.modules.get("base_schedule_manager")
    if top_level_base is not None:
        monkeypatch.setattr(top_level_base, "BASE_SCHEDULE_PATH", str(base_path))
        monkeypatch.setattr(top_level_base, "BASE_LOCK_PATH", str(base_path) + ".lock")
    monkeypatch.setattr(group_occupancy_snapshot, "GROUP_OCCUPANCY_SNAPSHOT_PATH", str(snapshot_path))
    monkeypatch.setattr(schedule_mutation_coordinator, "SCHEDULE_MUTATION_LOCK_PATH", str(coordinator_path))
    monkeypatch.setattr(
        server_routes.restore_manager,
        "get_restore_status",
        lambda: {"active": False, "recovery_required": False, "generation": 0},
    )
    monkeypatch.setattr(
        server_routes,
        "load_users",
        lambda: [
            {
                "login": "em1",
                "display_name": "Event Manager 1",
                "role": "event_manager",
                "password_hash": "secret",
            },
            {
                "login": "em2",
                "display_name": "Event Manager 2",
                "role": "event_manager",
                "password_hash": "secret",
            },
        ],
    )
    _write_json(base_path, _base_state())
    return {
        "routes": server_routes,
        "individual_path": individual_path,
        "base_path": base_path,
        "snapshot_path": snapshot_path,
    }


def _login(client, role, login=None, display_name=None):
    login = login or role
    display_name = display_name or login.title()
    with client.session_transaction() as session:
        session["login"] = login
        session["display_name"] = display_name
        session["role"] = role


def _read_individual(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_event_manager_creates_canonical_event_without_legacy_lock(event_server, monkeypatch):
    routes = event_server["routes"]
    monkeypatch.setattr(routes.lock_manager, "get_lock_status", lambda: {"holder": "admin", "version": 7})

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        lock_response = client.post("/api/lock/acquire")
        legacy_block_response = client.post("/api/blocks", json=_regular_block())
        column_response = client.post("/api/columns", json={"building": "Villa", "day": "Mo", "room": "0.04"})
        response = client.post("/api/events", json=_event_payload())

    body = response.get_json()
    persisted = _read_individual(event_server["individual_path"])
    block = body["block"]

    assert lock_response.status_code == 403
    assert legacy_block_response.status_code == 403
    assert column_response.status_code == 403
    assert response.status_code == 200
    assert block["lesson_type"] == "veranstaltung"
    assert block["subject"] == "Veranstaltung"
    assert block["teacher"] == "Event Manager 1"
    assert block["created_by"] == "em1"
    assert block["created_by_name"] == "Event Manager 1"
    assert block["owner_kind"] == "event_manager"
    assert block["version"] == 1
    assert block["event_dates"] == ["2026-07-03", "2026-07-10"]
    assert persisted["blocks"][0] == block


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (_event_payload(room="1.01"), "Event room is outside allowed event room scope"),
        (_event_payload(start_time="10:10"), "Event times must align to 15-minute boundaries"),
        (_event_payload(start_time="08:00", end_time="09:00"), "Event times must fit inside the event grid bounds"),
        (_event_payload(event_dates=["2026-06-30"]), "event_dates must include today or a future date"),
    ],
)
def test_event_manager_create_validation_rejects_invalid_event_payload(event_server, payload, expected_error):
    routes = event_server["routes"]

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        response = client.post("/api/events", json=payload)

    body = response.get_json()
    assert response.status_code == 400
    assert body["code"] == "VALIDATION_ERROR"
    assert body["error"] == expected_error
    assert not event_server["individual_path"].exists()


def test_update_and_delete_require_current_event_version(event_server):
    routes = event_server["routes"]
    _write_json(event_server["individual_path"], _individual_state(_event()))

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        updated = client.put("/api/events/event-1", json={"version": 1, "students": "Team"})
        stale_delete = client.delete("/api/events/event-1", json={"version": 1})
        deleted = client.delete("/api/events/event-1", json={"version": 2})

    assert updated.status_code == 200
    assert updated.get_json()["block"]["version"] == 2
    assert updated.get_json()["block"]["students"] == "Team"
    assert stale_delete.status_code == 409
    assert stale_delete.get_json()["code"] == "EVENT_VERSION_CONFLICT"
    assert deleted.status_code == 200
    assert _read_individual(event_server["individual_path"])["blocks"] == []


def test_event_manager_cannot_update_another_manager_or_admin_owned_event(event_server):
    routes = event_server["routes"]
    _write_json(
        event_server["individual_path"],
        _individual_state(
            _event(block_id="other", created_by="em2", created_by_name="Event Manager 2"),
            _event(block_id="admin-event", created_by="admin", created_by_name="Admin", owner_kind="admin"),
        ),
    )

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        other_response = client.put("/api/events/other", json={"version": 1, "students": "Nope"})
        admin_response = client.delete("/api/events/admin-event", json={"version": 1})

    assert other_response.status_code == 403
    assert other_response.get_json()["code"] == "FORBIDDEN"
    assert admin_response.status_code == 403
    assert admin_response.get_json()["code"] == "FORBIDDEN"


def test_admin_can_create_delegated_and_admin_owned_events(event_server):
    routes = event_server["routes"]

    with routes.app.test_client() as client:
        _login(client, "admin", "admin", "Admin")
        delegated = client.post("/api/events", json=_event_payload(author_login="em1"))
        admin_owned = client.post(
            "/api/events",
            json=_event_payload(
                start_time="11:00",
                end_time="12:00",
                event_dates=[],
                created_by="",
                owner_kind="",
            ),
        )
        users = client.get("/api/users/event_managers")

    delegated_block = delegated.get_json()["block"]
    admin_block = admin_owned.get_json()["block"]
    listed_user = users.get_json()["users"][0]

    assert delegated.status_code == 200
    assert delegated_block["created_by"] == "em1"
    assert delegated_block["teacher"] == "Event Manager 1"
    assert delegated_block["owner_kind"] == "event_manager"
    assert admin_owned.status_code == 200
    assert admin_block["created_by"] == "admin"
    assert admin_block["owner_kind"] == "admin"
    assert "password_hash" not in listed_user
    assert listed_user == {"login": "em1", "display_name": "Event Manager 1", "role": "event_manager"}


def test_event_conflict_uses_group_occupancy_snapshot_when_base_unpublished(event_server):
    routes = event_server["routes"]
    _write_json(event_server["base_path"], _base_state(published_at=None))
    _write_json(
        event_server["snapshot_path"],
        {
            "schema_version": 1,
            "generation_id": "gen-1",
            "generated_at": "2026-07-01T10:00:00Z",
            "source": "test.xlsx",
            "blocks": [
                {
                    "id": "group-1",
                    "day": "Mo",
                    "building": "Villa",
                    "room": "0.04",
                    "start_time": "10:30",
                    "end_time": "11:30",
                    "lesson_type": "group",
                    "subject": "Kunst",
                    "teacher": "Teacher",
                    "students": "2A",
                }
            ],
        },
    )

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        conflict = client.post("/api/events", json=_event_payload())
        back_to_back = client.post(
            "/api/events",
            json=_event_payload(start_time="09:30", end_time="10:30"),
        )

    assert conflict.status_code == 409
    assert conflict.get_json()["code"] == "EVENT_ROOM_CONFLICT"
    assert back_to_back.status_code == 200


def test_missing_occupancy_source_blocks_event_create_without_write(event_server):
    routes = event_server["routes"]
    _write_json(event_server["base_path"], _base_state(published_at=None))

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        response = client.post("/api/events", json=_event_payload())

    body = response.get_json()
    assert response.status_code == 503
    assert body["code"] == "OCCUPANCY_UNAVAILABLE"
    assert not event_server["individual_path"].exists()


def test_active_restore_blocks_event_mutation(event_server, monkeypatch):
    routes = event_server["routes"]
    monkeypatch.setattr(
        routes.restore_manager,
        "get_restore_status",
        lambda: {"active": True, "recovery_required": False, "generation": 5, "message": "Restore in progress"},
    )

    with routes.app.test_client() as client:
        _login(client, "event_manager", "em1", "Event Manager 1")
        response = client.post("/api/events", json=_event_payload())

    assert response.status_code == 423
    assert response.get_json()["code"] == "RESTORE_IN_PROGRESS"


def test_legacy_block_mutation_rejects_conflict_with_saved_event(event_server, monkeypatch):
    routes = event_server["routes"]
    _write_json(event_server["individual_path"], _individual_state(_event()))
    monkeypatch.setattr(routes.lock_manager, "get_lock_status", lambda: {"holder": "admin", "version": 1})

    with routes.app.test_client() as client:
        _login(client, "admin", "admin", "Admin")
        response = client.post("/api/blocks", json=_regular_block())

    assert response.status_code == 409
    assert response.get_json()["code"] == "EVENT_ROOM_CONFLICT"
    persisted = _read_individual(event_server["individual_path"])
    assert len(persisted["blocks"]) == 1
    assert persisted["blocks"][0]["id"] == "event-1"


@pytest.mark.parametrize("role", ["editor", "organizer", "viewer"])
def test_non_event_roles_cannot_use_event_endpoints(event_server, role):
    routes = event_server["routes"]

    with routes.app.test_client() as client:
        _login(client, role, role, role.title())
        response = client.post("/api/events", json=_event_payload())

    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"
