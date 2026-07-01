from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

from gear_xls.runtime_paths import get_group_occupancy_snapshot_path
from gear_xls.room_name_utils import normalize_room_fields
from gear_xls.schedule_mutation_coordinator import schedule_mutation
from gear_xls.schedule_state_errors import OccupancyUnavailable, ScheduleStateReadError
from gear_xls.time_utils import minutes_to_time


SNAPSHOT_SCHEMA_VERSION = 1
GROUP_OCCUPANCY_SNAPSHOT_PATH = get_group_occupancy_snapshot_path()
UNAVAILABLE_SNAPSHOT_SOURCE = "occupancy_unavailable"
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _derived_block_id(block: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(block).encode("utf-8")).hexdigest()[:16]
    return f"group-{digest}"


def _normal_text(value: object) -> str:
    return str(value or "").strip()


def _coerce_time(value: object) -> str:
    if isinstance(value, int):
        return minutes_to_time(value)
    return _normal_text(value)


def normalize_group_occupancy_block(block: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    if not isinstance(block, dict):
        raise ScheduleStateReadError(
            f"group_occupancy_snapshot.json block {index} must be an object",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )

    normalized = normalize_room_fields(
        {
            "id": _normal_text(block.get("id")),
            "day": _normal_text(block.get("day")),
            "building": _normal_text(block.get("building")),
            "room": _normal_text(block.get("room_display") or block.get("room")),
            "start_time": _coerce_time(block.get("start_time", block.get("start"))),
            "end_time": _coerce_time(block.get("end_time", block.get("end"))),
            "lesson_type": _normal_text(block.get("lesson_type") or "group").lower(),
            "subject": _normal_text(block.get("subject")),
            "teacher": _normal_text(block.get("teacher")),
            "students": _normal_text(block.get("students")),
        }
    )
    if not normalized["id"]:
        id_source = dict(normalized)
        id_source.pop("id", None)
        normalized["id"] = _derived_block_id(id_source)

    for field in ("id", "day", "building", "room", "start_time", "end_time", "lesson_type"):
        if not normalized.get(field):
            raise ScheduleStateReadError(
                f"group_occupancy_snapshot.json block {index}: {field} required",
                "OCCUPANCY_SNAPSHOT_CORRUPT",
            )
    if normalized["lesson_type"] != "group":
        raise ScheduleStateReadError(
            f"group_occupancy_snapshot.json block {index}: lesson_type must be group",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    if not _TIME_RE.fullmatch(normalized["start_time"]) or not _TIME_RE.fullmatch(normalized["end_time"]):
        raise ScheduleStateReadError(
            f"group_occupancy_snapshot.json block {index}: invalid time format",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    if normalized["end_time"] <= normalized["start_time"]:
        raise ScheduleStateReadError(
            f"group_occupancy_snapshot.json block {index}: end_time must be greater than start_time",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    return normalized


def _validate_snapshot(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ScheduleStateReadError(
            "group_occupancy_snapshot.json must be a JSON object",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    if data.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ScheduleStateReadError(
            "group_occupancy_snapshot.json has unsupported schema_version",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    generation_id = _normal_text(data.get("generation_id"))
    generated_at = _normal_text(data.get("generated_at"))
    source = _normal_text(data.get("source"))
    blocks = data.get("blocks")
    if not generation_id or not generated_at or not source or not isinstance(blocks, list):
        raise ScheduleStateReadError(
            "group_occupancy_snapshot.json metadata is incomplete",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        )
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleStateReadError(
            "group_occupancy_snapshot.json generated_at is invalid",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        ) from exc

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generation_id": generation_id,
        "generated_at": generated_at,
        "source": source,
        "blocks": [
            normalize_group_occupancy_block(block, index=index)
            for index, block in enumerate(blocks)
        ],
    }


def validate_group_occupancy_snapshot(data: Any) -> dict[str, Any]:
    return _validate_snapshot(data)


def read_group_occupancy_snapshot(*, required: bool = False) -> dict[str, Any] | None:
    if not os.path.exists(GROUP_OCCUPANCY_SNAPSHOT_PATH):
        if required:
            raise OccupancyUnavailable()
        return None
    try:
        with open(GROUP_OCCUPANCY_SNAPSHOT_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        raise ScheduleStateReadError(
            "group_occupancy_snapshot.json is not valid JSON",
            "OCCUPANCY_SNAPSHOT_CORRUPT",
        ) from exc
    return _validate_snapshot(data)


def build_group_occupancy_snapshot(
    blocks: list[dict[str, Any]],
    *,
    source: str,
    generation_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    normalized_blocks = [
        normalize_group_occupancy_block(block, index=index)
        for index, block in enumerate(blocks or [])
    ]
    normalized_blocks.sort(
        key=lambda item: (
            item["building"],
            item["day"],
            item["room"],
            item["start_time"],
            item["end_time"],
            item["id"],
        )
    )
    if generation_id is None:
        generation_id = hashlib.sha256(
            _canonical_json({"source": source, "blocks": normalized_blocks}).encode("utf-8")
        ).hexdigest()[:24]
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generation_id": str(generation_id),
        "generated_at": generated_at or _utc_timestamp(),
        "source": str(source or "unknown"),
        "blocks": normalized_blocks,
    }
    return _validate_snapshot(snapshot)


def collect_group_occupancy_blocks_from_buildings(buildings: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for building, building_data in (buildings or {}).items():
        if str(building).startswith("_") or not isinstance(building_data, dict):
            continue
        for day, intervals in building_data.items():
            if str(day).startswith("_") or not isinstance(intervals, list):
                continue
            for interval in intervals:
                if not isinstance(interval, dict):
                    continue
                lesson_type = _normal_text(interval.get("lesson_type") or "group").lower()
                if lesson_type != "group":
                    continue
                blocks.append(
                    {
                        "id": interval.get("id"),
                        "day": day,
                        "building": building,
                        "room": interval.get("room_display") or interval.get("room"),
                        "start_time": interval.get("start_time", interval.get("start")),
                        "end_time": interval.get("end_time", interval.get("end")),
                        "lesson_type": "group",
                        "subject": interval.get("subject"),
                        "teacher": interval.get("teacher"),
                        "students": interval.get("students"),
                    }
                )
    return blocks


def build_snapshot_from_buildings(
    buildings: dict[str, Any],
    *,
    source: str,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return build_group_occupancy_snapshot(
        collect_group_occupancy_blocks_from_buildings(buildings),
        source=source,
        generation_id=generation_id,
    )


def build_snapshot_from_base_state(base_state: dict[str, Any]) -> dict[str, Any]:
    revision = _normal_text(base_state.get("published_at")) or "unpublished"
    return build_group_occupancy_snapshot(
        [
            dict(block, lesson_type="group")
            for block in (base_state.get("blocks") or [])
            if isinstance(block, dict) and (block.get("lesson_type") or "group") == "group"
        ],
        source=f"base_schedule:{revision}",
        generation_id=f"base:{hashlib.sha256(revision.encode('utf-8')).hexdigest()[:16]}",
    )


def replace_group_occupancy_snapshot(
    snapshot: dict[str, Any],
    *,
    path: str | None = None,
) -> dict[str, Any]:
    validated = _validate_snapshot(snapshot)
    target_path = path or GROUP_OCCUPANCY_SNAPSHOT_PATH
    with schedule_mutation("occupancy_snapshot_replace"):
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(target_path),
                delete=False,
                suffix=".tmp",
                mode="w",
                encoding="utf-8",
            ) as tmp:
                json.dump(validated, tmp, ensure_ascii=False, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, target_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    return validated


def get_occupancy_readiness(base_state: dict[str, Any] | None = None) -> dict[str, Any]:
    if base_state is None:
        from gear_xls.base_schedule_manager import get_base_schedule_strict

        base_state = get_base_schedule_strict()

    if base_state.get("published_at"):
        return {
            "ready": True,
            "source": "base_schedule",
            "generation_id": base_state.get("published_at"),
            "blocks": base_state.get("blocks", []),
        }

    snapshot = read_group_occupancy_snapshot(required=False)
    if snapshot is None:
        return {
            "ready": False,
            "source": None,
            "code": "OCCUPANCY_UNAVAILABLE",
            "error": "No published base schedule or group occupancy snapshot is available",
        }
    if snapshot.get("source") == UNAVAILABLE_SNAPSHOT_SOURCE:
        return {
            "ready": False,
            "source": UNAVAILABLE_SNAPSHOT_SOURCE,
            "generation_id": snapshot.get("generation_id"),
            "code": "OCCUPANCY_UNAVAILABLE",
            "error": "No published base schedule or usable group occupancy snapshot is available",
        }
    return {
        "ready": True,
        "source": "group_occupancy_snapshot",
        "generation_id": snapshot["generation_id"],
        "blocks": snapshot["blocks"],
    }
