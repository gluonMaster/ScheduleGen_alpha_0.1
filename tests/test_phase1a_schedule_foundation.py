import json
import threading

import pytest

from gear_xls import base_schedule_manager
from gear_xls import group_occupancy_snapshot as occupancy
from gear_xls import integration
from gear_xls import schedule_mutation_coordinator as coordinator
from gear_xls import state_manager
from gear_xls.event_room_config import get_event_room_config, is_event_room, normalize_room_key
from gear_xls.schedule_mutation_coordinator import ScheduleMutationBusy, schedule_mutation
from gear_xls.schedule_state_errors import ScheduleStateReadError


def _individual_state(*blocks):
    return {"last_modified": "2026-07-01T10:00:00", "blocks": list(blocks)}


def _base_state(*blocks, published_at=None):
    return {"published_at": published_at, "published_by": "admin" if published_at else None, "blocks": list(blocks)}


def _individual_block(block_id="lesson-1"):
    return {
        "id": block_id,
        "building": "Villa",
        "day": "Mo",
        "room": "0.04",
        "subject": "Deutsch",
        "teacher": "Teacher",
        "students": "Student",
        "start_time": "10:00",
        "end_time": "11:00",
        "lesson_type": "individual",
    }


def _group_block(block_id="group-1", room="V0.04"):
    return {
        "id": block_id,
        "building": "Villa",
        "day": "Mo",
        "room": room,
        "subject": "Kunst",
        "teacher": "Teacher",
        "students": "2A",
        "start_time": "10:00",
        "end_time": "11:00",
        "lesson_type": "group",
    }


@pytest.fixture()
def isolated_paths(tmp_path, monkeypatch):
    individual_path = tmp_path / "individual_lessons.json"
    base_path = tmp_path / "base_schedule.json"
    snapshot_path = tmp_path / "group_occupancy_snapshot.json"
    coordinator_path = tmp_path / "schedule_mutation.lock"

    monkeypatch.setattr(state_manager, "INDIVIDUAL_LESSONS_PATH", str(individual_path))
    monkeypatch.setattr(state_manager, "INDIVIDUAL_LOCK_PATH", str(individual_path) + ".lock")
    monkeypatch.setattr(state_manager, "SCHEDULE_HTML_PATH", str(tmp_path / "missing_schedule.html"))
    monkeypatch.setattr(
        state_manager,
        "get_base_schedule",
        lambda: {"published_at": "2026-07-01T10:00:00", "blocks": []},
    )
    monkeypatch.setattr(base_schedule_manager, "BASE_SCHEDULE_PATH", str(base_path))
    monkeypatch.setattr(base_schedule_manager, "BASE_LOCK_PATH", str(base_path) + ".lock")
    monkeypatch.setattr(occupancy, "GROUP_OCCUPANCY_SNAPSHOT_PATH", str(snapshot_path))
    monkeypatch.setattr(coordinator, "SCHEDULE_MUTATION_LOCK_PATH", str(coordinator_path))

    return {
        "individual": individual_path,
        "base": base_path,
        "snapshot": snapshot_path,
        "coordinator": coordinator_path,
    }


def test_corrupt_individual_state_fails_closed_without_write(isolated_paths):
    path = isolated_paths["individual"]
    path.write_text("{not-json", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ScheduleStateReadError) as excinfo:
        state_manager.add_block(_individual_block("new-lesson"), "admin")

    assert excinfo.value.code == "INDIVIDUAL_STATE_CORRUPT"
    assert path.read_text(encoding="utf-8") == before


def test_corrupt_base_schedule_fails_closed_without_write(isolated_paths):
    path = isolated_paths["base"]
    path.write_text("{not-json", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ScheduleStateReadError) as excinfo:
        base_schedule_manager.publish_base([_group_block()], "admin", expected_base_revision=None)

    assert excinfo.value.code == "BASE_SCHEDULE_CORRUPT"
    assert path.read_text(encoding="utf-8") == before


def test_missing_snapshot_readiness_is_unavailable_not_free(isolated_paths):
    readiness = occupancy.get_occupancy_readiness(_base_state())

    assert readiness["ready"] is False
    assert readiness["code"] == "OCCUPANCY_UNAVAILABLE"
    assert not isolated_paths["snapshot"].exists()


def test_published_base_satisfies_occupancy_readiness_without_snapshot(isolated_paths):
    base = _base_state(_group_block(), published_at="2026-07-01T10:00:00")

    readiness = occupancy.get_occupancy_readiness(base)

    assert readiness["ready"] is True
    assert readiness["source"] == "base_schedule"
    assert readiness["generation_id"] == "2026-07-01T10:00:00"


def test_snapshot_replace_read_and_room_normalization(isolated_paths):
    snapshot = occupancy.build_group_occupancy_snapshot(
        [_group_block(room="V0.04")],
        source="test.xlsx",
        generation_id="gen-1",
        generated_at="2026-07-01T10:00:00Z",
    )

    occupancy.replace_group_occupancy_snapshot(snapshot)
    read_back = occupancy.read_group_occupancy_snapshot(required=True)

    assert read_back["schema_version"] == 1
    assert read_back["generation_id"] == "gen-1"
    assert read_back["blocks"][0]["building"] == "Villa"
    assert read_back["blocks"][0]["room"] == "0.04"


def test_corrupt_snapshot_fails_closed(isolated_paths):
    isolated_paths["snapshot"].write_text("{not-json", encoding="utf-8")

    with pytest.raises(ScheduleStateReadError) as excinfo:
        occupancy.read_group_occupancy_snapshot(required=True)

    assert excinfo.value.code == "OCCUPANCY_SNAPSHOT_CORRUPT"


def test_event_room_config_and_normalization():
    assert get_event_room_config() == {
        "Villa": ["0.04", "0.06", "0.08", "2.04"],
        "Kolibri": ["0.3", "0.2"],
    }
    assert normalize_room_key(" villa ", "V0.04") == ("Villa", "0.04")
    assert normalize_room_key("Kolibri", "K0.3") == ("Kolibri", "0.3")
    assert is_event_room("Villa", "V2.04") is True
    assert is_event_room("Villa", "1.01") is False


def test_snapshot_generation_from_buildings_filters_non_group_and_normalizes(isolated_paths):
    buildings = {
        "Villa": {
            "Mo": [
                {
                    "id": "group-1",
                    "room": "V0.04",
                    "start": 600,
                    "end": 660,
                    "subject": "Kunst",
                    "teacher": "Teacher",
                    "students": "2A",
                },
                {
                    "id": "trial-1",
                    "room": "V0.06",
                    "start": 700,
                    "end": 730,
                    "lesson_type": "trial",
                },
            ],
            "_rooms": ["0.04"],
        }
    }

    snapshot = occupancy.build_snapshot_from_buildings(
        buildings,
        source="generated.xlsx",
        generation_id="gen-buildings",
    )

    assert len(snapshot["blocks"]) == 1
    assert snapshot["blocks"][0]["id"] == "group-1"
    assert snapshot["blocks"][0]["room"] == "0.04"
    assert snapshot["blocks"][0]["start_time"] == "10:00"
    assert snapshot["blocks"][0]["end_time"] == "11:00"


def test_reset_web_editor_state_writes_occupancy_snapshot(tmp_path, monkeypatch, isolated_paths):
    monkeypatch.setattr(integration, "get_schedule_state_dir", lambda: str(tmp_path))
    buildings = {
        "Kolibri": {
            "Di": [
                {
                    "id": "group-2",
                    "room": "K0.3",
                    "start": 540,
                    "end": 600,
                    "subject": "Math",
                    "teacher": "Teacher",
                    "students": "3A",
                }
            ]
        }
    }

    integration.reset_web_editor_state([], group_buildings=buildings, snapshot_source="source.xlsx")

    snapshot_path = tmp_path / "group_occupancy_snapshot.json"
    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert data["source"] == "source.xlsx"
    assert data["blocks"][0]["building"] == "Kolibri"
    assert data["blocks"][0]["room"] == "0.3"


def test_schedule_mutation_coordinator_reports_busy(isolated_paths):
    results = []

    def contender():
        try:
            with schedule_mutation(timeout_seconds=0.05, retry_seconds=0.005):
                results.append("acquired")
        except ScheduleMutationBusy as exc:
            results.append(exc.code)

    with schedule_mutation(timeout_seconds=0.2):
        thread = threading.Thread(target=contender)
        thread.start()
        thread.join(timeout=1)

    assert results == ["SCHEDULE_MUTATION_BUSY"]
