import json
import logging
import os
import re
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from gear_xls.runtime_paths import (
    get_individual_lessons_path,
    get_schedule_html_path,
)
from gear_xls.day_constants import DAY_TO_WEEKDAY, TRIAL_ONLY_DAYS, WEB_EDITOR_DAY_SET
from gear_xls.event_domain import (
    EVENT_DEFAULT_COLOR,
    EVENT_OWNER_ADMIN,
    EVENT_OWNER_EVENT_MANAGER,
    EVENT_OWNER_KINDS,
    EVENT_SUBJECT,
    LESSON_TYPE_EVENT,
    ROLE_EVENT_MANAGER,
)
from gear_xls.event_room_config import is_event_room
from gear_xls.room_name_utils import normalize_room_fields
from gear_xls.schedule_mutation_coordinator import schedule_mutation
from gear_xls.schedule_state_errors import OccupancyUnavailable, ScheduleStateReadError

try:
    from .base_schedule_manager import (
        BASE_SCHEDULE_PATH,
        base_has_group_lessons_in_column,
        get_base_revision,
        get_base_schedule,
        publish_base,
    )
except ImportError:
    from base_schedule_manager import (
        BASE_SCHEDULE_PATH,
        base_has_group_lessons_in_column,
        get_base_revision,
        get_base_schedule,
        publish_base,
    )


INDIVIDUAL_LESSONS_PATH = get_individual_lessons_path()
INDIVIDUAL_LOCK_PATH = INDIVIDUAL_LESSONS_PATH + ".lock"
SCHEDULE_HTML_PATH = get_schedule_html_path()
VALID_DAYS = WEB_EDITOR_DAY_SET
_DAY_TO_WEEKDAY = DAY_TO_WEEKDAY
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_PATTERN = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
_EVENT_TARGET_MAX_LENGTH = 500
_EVENT_GRID_START_MINUTES = 9 * 60
_EVENT_GRID_END_MINUTES = 20 * 60
_ind_mutex = threading.Lock()
logger = logging.getLogger(__name__)
_HTML_BLOCK_PATTERN = re.compile(
    r"<div(?P<attrs>[^>]*class=['\"][^'\"]*activity-block[^'\"]*['\"][^>]*)>(?P<body>.*?)</div>",
    re.I | re.S,
)


def _empty_state():
    return {"last_modified": None, "blocks": []}


def _normalize_block(block):
    normalized = {}
    for key, value in (block or {}).items():
        normalized[key] = value.strip() if isinstance(value, str) else value
    return normalized


def _acquire_file_lock(fp):
    try:
        import msvcrt

        fp.seek(0)
        if os.path.getsize(fp.name) == 0:
            fp.write(b"0")
            fp.flush()
            fp.seek(0)
        msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
        return "msvcrt"
    except ImportError:
        try:
            import fcntl
        except ImportError as exc:
            raise RuntimeError("Cannot acquire file lock") from exc
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return "fcntl"
        except OSError as exc:
            raise RuntimeError("Cannot acquire file lock") from exc
    except OSError as exc:
        raise RuntimeError("Cannot acquire file lock") from exc


def _release_file_lock(fp, backend):
    try:
        if backend == "msvcrt":
            import msvcrt

            fp.seek(0)
            msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
            return
        if backend == "fcntl":
            import fcntl

            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        logger.warning("Failed to release individual lock: %s", exc)


@contextmanager
def _locked_individual_file():
    os.makedirs(os.path.dirname(INDIVIDUAL_LOCK_PATH), exist_ok=True)
    with open(INDIVIDUAL_LOCK_PATH, "a+b") as lock_fp:
        backend = _acquire_file_lock(lock_fp)
        try:
            yield
        finally:
            _release_file_lock(lock_fp, backend)


def _read_individual():
    if not os.path.exists(INDIVIDUAL_LESSONS_PATH):
        return _empty_state()
    try:
        with open(INDIVIDUAL_LESSONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to read individual lessons: %s", exc)
        raise ScheduleStateReadError(
            "individual_lessons.json is not valid JSON",
            "INDIVIDUAL_STATE_CORRUPT",
        ) from exc

    if not isinstance(data, dict):
        raise ScheduleStateReadError(
            "individual_lessons.json must be a JSON object",
            "INDIVIDUAL_STATE_CORRUPT",
        )
    blocks = data.get("blocks", [])
    if not isinstance(blocks, list):
        raise ScheduleStateReadError(
            "individual_lessons.json blocks must be a list",
            "INDIVIDUAL_STATE_CORRUPT",
        )
    last_modified = data.get("last_modified")
    if last_modified is not None and not isinstance(last_modified, str):
        raise ScheduleStateReadError(
            "individual_lessons.json last_modified must be a string or null",
            "INDIVIDUAL_STATE_CORRUPT",
        )
    return {
        "last_modified": last_modified,
        "blocks": blocks,
    }


def get_individual_lessons_strict():
    with _ind_mutex:
        with _locked_individual_file():
            return _read_individual()


def _write_individual_payload(payload):
    os.makedirs(os.path.dirname(INDIVIDUAL_LESSONS_PATH), exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=os.path.dirname(INDIVIDUAL_LESSONS_PATH),
            delete=False,
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, INDIVIDUAL_LESSONS_PATH)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def replace_individual_state(state):
    blocks = state.get("blocks", []) if isinstance(state, dict) else None
    last_modified = state.get("last_modified") if isinstance(state, dict) else None
    if not isinstance(blocks, list):
        raise ScheduleStateReadError(
            "individual_lessons.json blocks must be a list",
            "INDIVIDUAL_STATE_CORRUPT",
        )
    if last_modified is not None and not isinstance(last_modified, str):
        raise ScheduleStateReadError(
            "individual_lessons.json last_modified must be a string or null",
            "INDIVIDUAL_STATE_CORRUPT",
        )
    with schedule_mutation("individual_state_replace"):
        with _ind_mutex:
            with _locked_individual_file():
                payload = {"last_modified": last_modified, "blocks": blocks}
                _write_individual_payload(payload)
                return payload


def _write_individual(state):
    payload = {
        "last_modified": datetime.utcnow().isoformat(),
        "blocks": state.get("blocks", []),
    }
    _write_individual_payload(payload)
    state["last_modified"] = payload["last_modified"]


def _pristine_individual_state(state):
    return state.get("last_modified") is None and not state.get("blocks")


def _to_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_embedded_individual_block(attrs_text, body):
    attrs = {
        key: unescape(value)
        for key, value in re.findall(r"data-([\w-]+)=['\"]([^'\"]*)['\"]", attrs_text)
    }
    lesson_type = (attrs.get("lesson-type") or "").strip()
    style_match = re.search(r"style=['\"]([^'\"]*)['\"]", attrs_text, re.I)
    color_match = (
        re.search(r"background-color\s*:\s*([^;]+)", style_match.group(1), re.I)
        if style_match
        else None
    )
    lines = [
        unescape(line)
        for line in (
            re.sub(r"<[^>]+>", "", raw_line).strip()
            for raw_line in re.sub(r"<br\s*/?>", "\n", body, flags=re.I).splitlines()
        )
        if line
    ]
    time_match = None
    time_index = -1
    block = None
    error = None

    if lesson_type not in ("individual", "nachhilfe", "trial"):
        return None

    for index in range(len(lines) - 1, -1, -1):
        time_match = re.fullmatch(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", lines[index]
        )
        if time_match:
            time_index = index
            break

    if time_index < 1:
        return None

    block = {
        "id": str(uuid.uuid4()),
        "day": (attrs.get("day") or "").strip(),
        "building": (attrs.get("building") or "").strip(),
        "room": lines[time_index - 1].strip(),
        "start_time": time_match.group(1),
        "end_time": time_match.group(2),
        "subject": lines[0] if lines else "",
        "teacher": lines[1] if len(lines) > 1 else "",
        "students": lines[2] if len(lines) > 2 else "",
        "lesson_type": lesson_type,
    }

    if lesson_type == "trial":
        raw_trial_dates = attrs.get("trial-dates")
        if raw_trial_dates:
            try:
                parsed_trial_dates = json.loads(raw_trial_dates)
                if isinstance(parsed_trial_dates, list):
                    block["trial_dates"] = [str(item) for item in parsed_trial_dates if item is not None]
                else:
                    block["trial_dates"] = []
                    logger.warning("Skip invalid embedded trial-dates payload: %r", raw_trial_dates)
            except Exception as exc:
                block["trial_dates"] = []
                logger.warning("Failed to parse embedded trial-dates JSON: %s", exc)

    if color_match:
        block["color"] = color_match.group(1).strip()

    if attrs.get("start-row") is not None:
        block["start_row"] = _to_int_or_none(attrs.get("start-row"))
    if attrs.get("row-span") is not None:
        block["row_span"] = _to_int_or_none(attrs.get("row-span"))

    error = _validate_block(block, "admin")
    if error:
        logger.warning("Skip embedded non-group block due to validation error: %s", error)
        return None

    return block


def _load_embedded_individual_blocks():
    if not os.path.exists(SCHEDULE_HTML_PATH):
        return []

    try:
        with open(SCHEDULE_HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as exc:
        logger.warning("Failed to read schedule HTML for individual bootstrap: %s", exc)
        return []

    blocks = []
    for match in _HTML_BLOCK_PATTERN.finditer(html):
        block = _parse_embedded_individual_block(
            match.group("attrs"), match.group("body")
        )
        if block:
            blocks.append(block)
    return blocks


def _bootstrap_individual_from_html_if_needed(state):
    embedded_blocks = []

    if not _pristine_individual_state(state):
        return state

    if get_base_schedule().get("published_at") is not None:
        return state

    embedded_blocks = _load_embedded_individual_blocks()
    if not embedded_blocks:
        return state

    state["blocks"] = embedded_blocks
    _write_individual(state)
    logger.info(
        "Bootstrapped %d non-group blocks from %s into individual_lessons.json",
        len(embedded_blocks),
        SCHEDULE_HTML_PATH,
    )
    return state


_ROLE_ALLOWED_TYPES = {
    "admin":     {"group", "individual", "nachhilfe", "trial"},
    "editor":    {"individual", "nachhilfe", "trial"},
    "organizer": {"trial"},
}


@dataclass
class IndividualMutationResult:
    value: object = None
    error: str | None = None
    individual_revision: str | None = None
    individual_cleanup_removed: int = 0
    cleanup_removed_ids: list | None = None

    def __iter__(self):
        yield self.value
        yield self.error

    @property
    def force_individual_refresh(self):
        return self.individual_cleanup_removed > 0


@dataclass
class EventMutationResult:
    value: object = None
    ok: bool = False
    error: str | None = None
    code: str | None = None
    status_code: int = 200
    individual_revision: str | None = None
    individual_cleanup_removed: int = 0
    cleanup_removed_ids: list | None = None

    @property
    def force_individual_refresh(self):
        return self.individual_cleanup_removed > 0


def _today_local_date() -> date:
    return datetime.now().date()


def _parse_iso_date_or_none(value):
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time_minutes(value):
    if not isinstance(value, str) or not _TIME_PATTERN.fullmatch(value.strip()):
        return None
    hours, minutes = value.strip().split(":", 1)
    return int(hours) * 60 + int(minutes)


def _format_time_minutes(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _validate_time_range(block, *, require_15_minute=False):
    start_minutes = _parse_time_minutes(str(block.get("start_time", "")).strip())
    end_minutes = _parse_time_minutes(str(block.get("end_time", "")).strip())
    if start_minutes is None or end_minutes is None:
        return "Invalid time format"
    if start_minutes >= end_minutes:
        return "end_time must be greater than start_time"
    if require_15_minute and (start_minutes % 15 != 0 or end_minutes % 15 != 0):
        return "Event times must align to 15-minute boundaries"
    block["start_time"] = _format_time_minutes(start_minutes)
    block["end_time"] = _format_time_minutes(end_minutes)
    return None


def _validate_event_grid_bounds(block):
    start_minutes = _parse_time_minutes(str(block.get("start_time", "")).strip())
    end_minutes = _parse_time_minutes(str(block.get("end_time", "")).strip())
    if start_minutes is None or end_minutes is None:
        return "Invalid time format"
    if start_minutes < _EVENT_GRID_START_MINUTES or end_minutes > _EVENT_GRID_END_MINUTES:
        return "Event times must fit inside the event grid bounds"
    return None


def _positive_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_event_dates(values, *, allow_invalid=False):
    if values in (None, ""):
        return [], None
    if not isinstance(values, list):
        return None, "event_dates must be a list"

    normalized = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
            if allow_invalid:
                continue
            return None, "event_dates entries must be YYYY-MM-DD strings"
        parsed = _parse_iso_date_or_none(value)
        if parsed is None:
            if allow_invalid:
                continue
            return None, f"event_dates contains invalid date: {value}"
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    normalized.sort()
    return normalized, None


def _event_dates_expired(event_dates, today=None):
    if not event_dates:
        return False
    parsed_dates = [_parse_iso_date_or_none(value) for value in event_dates]
    if any(value is None for value in parsed_dates):
        return False
    today = today or _today_local_date()
    return max(parsed_dates) < today


def _is_expired_event_block(block, today=None):
    if not isinstance(block, dict) or block.get("lesson_type") != LESSON_TYPE_EVENT:
        return False
    event_dates, _error = _normalize_event_dates(block.get("event_dates"), allow_invalid=True)
    return _event_dates_expired(event_dates, today=today)


def _normalize_persisted_event_block(block):
    if not isinstance(block, dict) or block.get("lesson_type") != LESSON_TYPE_EVENT:
        return False

    before = json.dumps(block, ensure_ascii=False, sort_keys=True, default=str)
    block["lesson_type"] = LESSON_TYPE_EVENT
    block["subject"] = EVENT_SUBJECT
    block["version"] = _positive_int(block.get("version"), default=1)
    if block.get("owner_kind") not in EVENT_OWNER_KINDS:
        block["owner_kind"] = EVENT_OWNER_ADMIN

    event_dates, _error = _normalize_event_dates(block.get("event_dates"), allow_invalid=True)
    block["event_dates"] = event_dates

    created_by = str(block.get("created_by") or "").strip()
    created_by_name = str(block.get("created_by_name") or block.get("teacher") or created_by).strip()
    block["created_by"] = created_by
    block["created_by_name"] = created_by_name
    block["teacher"] = created_by_name
    block["students"] = str(block.get("students") or "").strip()
    block["color"] = str(block.get("color") or EVENT_DEFAULT_COLOR).strip() or EVENT_DEFAULT_COLOR

    normalized_room = normalize_room_fields(block)
    block.update(normalized_room)

    for name, min_value in (("start_row", 0), ("row_span", 1), ("col_index", 0)):
        if block.get(name) is None:
            continue
        block[name] = _positive_int(block.get(name), default=min_value)
        if block[name] < min_value:
            block[name] = min_value

    after = json.dumps(block, ensure_ascii=False, sort_keys=True, default=str)
    return before != after


def _normalize_persisted_events(state):
    changed = False
    for block in state.get("blocks", []) if isinstance(state, dict) else []:
        if _normalize_persisted_event_block(block):
            changed = True
    return changed


def _eligible_trial_dates_for_cleanup(block):
    if not isinstance(block, dict):
        return None
    if block.get("lesson_type") != "trial":
        return None

    trial_dates = block.get("trial_dates")
    if not isinstance(trial_dates, list) or not trial_dates:
        return None

    day = str(block.get("day", "")).strip()
    expected_weekday = _DAY_TO_WEEKDAY.get(day)
    if expected_weekday is None:
        return None

    parsed_dates = []
    for value in trial_dates:
        parsed = _parse_iso_date_or_none(value)
        if parsed is None:
            return None
        if parsed.weekday() != expected_weekday:
            return None
        parsed_dates.append(parsed)

    return parsed_dates


def _is_expired_trial_block(block, today=None):
    parsed_dates = _eligible_trial_dates_for_cleanup(block)
    if not parsed_dates:
        return False
    today = today or _today_local_date()
    return max(parsed_dates) < today


def _prune_expired_trial_blocks(state, today=None):
    blocks = state.get("blocks", []) if isinstance(state, dict) else []
    if not isinstance(blocks, list) or not blocks:
        return {"removed": 0, "removed_ids": []}

    today = today or _today_local_date()
    remaining = []
    removed_ids = []

    for block in blocks:
        if _is_expired_trial_block(block, today=today):
            removed_ids.append(block.get("id") if isinstance(block, dict) else None)
        else:
            remaining.append(block)

    if removed_ids:
        state["blocks"] = remaining

    return {"removed": len(removed_ids), "removed_ids": removed_ids}


def _prune_expired_event_blocks(state, today=None):
    blocks = state.get("blocks", []) if isinstance(state, dict) else []
    if not isinstance(blocks, list) or not blocks:
        return {"removed": 0, "removed_ids": []}

    today = today or _today_local_date()
    remaining = []
    removed_ids = []

    for block in blocks:
        if _is_expired_event_block(block, today=today):
            removed_ids.append(block.get("id") if isinstance(block, dict) else None)
        else:
            remaining.append(block)

    if removed_ids:
        state["blocks"] = remaining

    return {"removed": len(removed_ids), "removed_ids": removed_ids}


def _prepare_individual_state_for_lifecycle(state, today=None):
    changed = _normalize_persisted_events(state)
    trial_cleanup = _prune_expired_trial_blocks(state, today=today)
    event_cleanup = _prune_expired_event_blocks(state, today=today)
    removed_ids = list(trial_cleanup.get("removed_ids") or []) + list(event_cleanup.get("removed_ids") or [])
    removed = int(trial_cleanup.get("removed") or 0) + int(event_cleanup.get("removed") or 0)
    return {
        "removed": removed,
        "removed_ids": removed_ids,
        "changed": bool(changed or removed),
    }


def _validate_trial_not_expired_for_write(block, today=None):
    if _is_expired_trial_block(block, today=today):
        return "trial_dates must include today or a future date"
    return None


def _mutation_result(value, error, state, cleanup):
    return IndividualMutationResult(
        value=value,
        error=error,
        individual_revision=state.get("last_modified") if isinstance(state, dict) else None,
        individual_cleanup_removed=int(cleanup.get("removed") or 0) if isinstance(cleanup, dict) else 0,
        cleanup_removed_ids=list(cleanup.get("removed_ids") or []) if isinstance(cleanup, dict) else [],
    )


def _finish_mutation(value, error, state, cleanup, should_write):
    if should_write:
        _write_individual(state)
    return _mutation_result(value, error, state, cleanup)


def _validate_block(block, role):
    for field in ("day", "start_time", "end_time", "lesson_type", "subject", "room", "building"):
        if not str(block.get(field, "")).strip():
            return f"{field} required"
    block.update(normalize_room_fields(block))
    if block.get("lesson_type") != LESSON_TYPE_EVENT and str(block.get("subject", "")).strip() == EVENT_SUBJECT:
        return "subject Veranstaltung is reserved for event blocks"
    if block["day"] not in VALID_DAYS:
        return "Invalid day"
    allowed = _ROLE_ALLOWED_TYPES.get(role)
    if allowed is not None and block.get("lesson_type") not in allowed:
        return "Forbidden lesson_type"
    if block["day"] in TRIAL_ONLY_DAYS and block.get("lesson_type") != "trial":
        return "Sunday is allowed only for trial lessons"
    if block.get("lesson_type") == "trial":
        dates = block.get("trial_dates", [])
        if not isinstance(dates, list):
            return "trial_dates must be a list"
        expected_weekday = _DAY_TO_WEEKDAY[block["day"]]
        normalized_dates = []
        seen_dates = set()
        for d in dates:
            if not isinstance(d, str) or not _ISO_DATE_PATTERN.fullmatch(d):
                return "trial_dates entries must be YYYY-MM-DD strings"
            try:
                parsed_date = datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                return f"trial_dates contains invalid date: {d}"
            if parsed_date.weekday() != expected_weekday:
                return f"trial_dates contains date {d} not matching block day {block['day']}"
            if d not in seen_dates:
                seen_dates.add(d)
                normalized_dates.append(d)
        if not normalized_dates:
            return "trial_dates must contain at least one date"
        block["trial_dates"] = sorted(normalized_dates)
    else:
        # Strip trial_dates from non-trial blocks to avoid stale data
        block.pop("trial_dates", None)
    for name, min_value in (("start_row", 0), ("row_span", 1)):
        value = block.get(name)
        if value is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            return f"{name} invalid"
        if value < min_value:
            return f"{name} invalid"
        block[name] = value
    return None


def _event_result(value=None, *, ok=False, error=None, code=None, status_code=200, state=None, cleanup=None):
    cleanup = cleanup or {}
    return EventMutationResult(
        value=value,
        ok=ok,
        error=error,
        code=code,
        status_code=status_code,
        individual_revision=state.get("last_modified") if isinstance(state, dict) else None,
        individual_cleanup_removed=int(cleanup.get("removed") or 0),
        cleanup_removed_ids=list(cleanup.get("removed_ids") or []),
    )


def _validation_event_result(message, state=None, cleanup=None):
    return _event_result(
        error=message,
        code="VALIDATION_ERROR",
        status_code=400,
        state=state,
        cleanup=cleanup,
    )


def _event_not_found_result(state=None, cleanup=None):
    return _event_result(
        error="Event not found",
        code="EVENT_NOT_FOUND",
        status_code=404,
        state=state,
        cleanup=cleanup,
    )


def _event_forbidden_result(state=None, cleanup=None):
    return _event_result(
        error="Forbidden",
        code="FORBIDDEN",
        status_code=403,
        state=state,
        cleanup=cleanup,
    )


def _event_version_conflict_result(state=None, cleanup=None):
    return _event_result(
        error="Event version conflict",
        code="EVENT_VERSION_CONFLICT",
        status_code=409,
        state=state,
        cleanup=cleanup,
    )


def _event_room_conflict_result(conflict, state=None, cleanup=None):
    return _event_result(
        error="Event room conflict",
        code="EVENT_ROOM_CONFLICT",
        status_code=409,
        state=state,
        cleanup=cleanup,
    )


def _prepare_state_for_event_mutation(state):
    _normalize_persisted_events(state)
    trial_cleanup = _prune_expired_trial_blocks(state)
    event_cleanup = _prune_expired_event_blocks(state)
    return {
        "removed": int(trial_cleanup.get("removed") or 0) + int(event_cleanup.get("removed") or 0),
        "removed_ids": list(trial_cleanup.get("removed_ids") or []) + list(event_cleanup.get("removed_ids") or []),
    }


def _block_time_interval(block, *, state_code):
    start = _parse_time_minutes(str(block.get("start_time", "")).strip())
    end = _parse_time_minutes(str(block.get("end_time", "")).strip())
    if start is None or end is None or start >= end:
        raise ScheduleStateReadError("Stored schedule block has invalid time range", state_code)
    return start, end


def _half_open_overlap(candidate, existing):
    candidate_start, candidate_end = _block_time_interval(candidate, state_code="INDIVIDUAL_STATE_CORRUPT")
    existing_start, existing_end = _block_time_interval(existing, state_code="INDIVIDUAL_STATE_CORRUPT")
    return candidate_start < existing_end and existing_start < candidate_end


def _same_room_day(left, right):
    left_norm = normalize_room_fields(left)
    right_norm = normalize_room_fields(right)
    return (
        str(left_norm.get("building") or "").strip() == str(right_norm.get("building") or "").strip()
        and str(left_norm.get("room") or "").strip() == str(right_norm.get("room") or "").strip()
        and str(left_norm.get("day") or "").strip() == str(right_norm.get("day") or "").strip()
    )


def _find_room_time_conflict(candidate, blocks, *, exclude_id=None, allowed_types=None, state_code="INDIVIDUAL_STATE_CORRUPT"):
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        if exclude_id is not None and block.get("id") == exclude_id:
            continue
        lesson_type = block.get("lesson_type") or "group"
        if allowed_types is not None and lesson_type not in allowed_types:
            continue
        if not _same_room_day(candidate, block):
            continue
        candidate_start, candidate_end = _block_time_interval(candidate, state_code=state_code)
        existing_start, existing_end = _block_time_interval(block, state_code=state_code)
        if candidate_start < existing_end and existing_start < candidate_end:
            return {
                "id": block.get("id"),
                "lesson_type": lesson_type,
                "day": block.get("day"),
                "building": block.get("building"),
                "room": block.get("room"),
                "start_time": block.get("start_time"),
                "end_time": block.get("end_time"),
            }
    return None


def _validate_saved_event_conflict_for_legacy(block, state, *, exclude_id=None):
    if block.get("lesson_type") == LESSON_TYPE_EVENT:
        return None
    error = _validate_time_range(block)
    if error:
        return error
    conflict = _find_room_time_conflict(
        block,
        state.get("blocks", []),
        exclude_id=exclude_id,
        allowed_types={LESSON_TYPE_EVENT},
    )
    return "EVENT_ROOM_CONFLICT" if conflict else None


def _read_group_occupancy_blocks_for_event_mutation():
    from gear_xls.base_schedule_manager import get_base_schedule_strict
    from gear_xls.group_occupancy_snapshot import get_occupancy_readiness

    base_state = get_base_schedule_strict()
    readiness = get_occupancy_readiness(base_state)
    if not readiness.get("ready"):
        raise OccupancyUnavailable(readiness.get("error") or "Occupancy snapshot is unavailable")
    return list(readiness.get("blocks") or []), readiness.get("source")


def _validate_event_target_audience(value):
    text = str(value or "").strip()
    if len(text) > _EVENT_TARGET_MAX_LENGTH:
        return None, f"students must be {_EVENT_TARGET_MAX_LENGTH} characters or fewer"
    if any(ord(ch) < 32 for ch in text):
        return None, "students contains invalid control characters"
    return text, None


def _validate_event_dates_for_write(block, today=None):
    event_dates, error = _normalize_event_dates(block.get("event_dates"))
    if error:
        return error
    if _event_dates_expired(event_dates, today=today):
        return "event_dates must include today or a future date"
    block["event_dates"] = event_dates
    return None


def _normalize_event_int_fields(block):
    for name, min_value in (("start_row", 0), ("row_span", 1), ("col_index", 0)):
        if block.get(name) is None:
            block.pop(name, None)
            continue
        try:
            value = int(block.get(name))
        except (TypeError, ValueError):
            return f"{name} invalid"
        if value < min_value:
            return f"{name} invalid"
        block[name] = value
    return None


def _canonicalize_event_payload(payload, *, actor, author, existing=None):
    payload = payload if isinstance(payload, dict) else {}
    actor = actor or {}
    author = author or {}
    if existing is not None:
        block = dict(existing)
    else:
        block = {}

    for field in ("day", "building", "room", "start_time", "end_time", "students", "color", "event_dates"):
        if existing is None or field in payload:
            block[field] = payload.get(field)
    for field in ("start_row", "row_span", "col_index"):
        if field in payload:
            block[field] = payload.get(field)

    block.update(normalize_room_fields(block))
    block["lesson_type"] = LESSON_TYPE_EVENT
    block["subject"] = EVENT_SUBJECT

    created_by = str(author.get("login") or block.get("created_by") or "").strip()
    created_by_name = str(author.get("display_name") or block.get("created_by_name") or created_by).strip()
    owner_kind = str(author.get("owner_kind") or block.get("owner_kind") or "").strip()
    block["created_by"] = created_by
    block["created_by_name"] = created_by_name
    block["teacher"] = created_by_name
    block["owner_kind"] = owner_kind

    if not created_by:
        return None, "author login required"
    if owner_kind not in EVENT_OWNER_KINDS:
        return None, "owner_kind invalid"

    for field in ("day", "building", "room", "start_time", "end_time"):
        if not str(block.get(field, "")).strip():
            return None, f"{field} required"
    if block["day"] not in VALID_DAYS:
        return None, "Invalid day"
    if block["day"] in TRIAL_ONLY_DAYS:
        return None, "Sunday is allowed only for trial lessons"
    if not is_event_room(block.get("building"), block.get("room")):
        return None, "Event room is outside allowed event room scope"

    error = _validate_time_range(block, require_15_minute=True)
    if error:
        return None, error
    error = _validate_event_grid_bounds(block)
    if error:
        return None, error
    error = _validate_event_dates_for_write(block)
    if error:
        return None, error
    students, error = _validate_event_target_audience(block.get("students"))
    if error:
        return None, error
    block["students"] = students
    block["color"] = str(block.get("color") or EVENT_DEFAULT_COLOR).strip() or EVENT_DEFAULT_COLOR
    error = _normalize_event_int_fields(block)
    if error:
        return None, error

    if existing is None:
        block["id"] = str(uuid.uuid4())
        block["version"] = 1
    else:
        block["id"] = existing.get("id")
        block["created_by"] = existing.get("created_by")
        block["created_by_name"] = existing.get("created_by_name") or block["created_by_name"]
        block["teacher"] = block["created_by_name"]
        block["owner_kind"] = existing.get("owner_kind")
        block["version"] = _positive_int(existing.get("version"), default=1) + 1
    return block, None


def _can_actor_mutate_event(block, actor):
    role = (actor or {}).get("role")
    login = (actor or {}).get("login")
    if role == "admin":
        return True
    return (
        role == ROLE_EVENT_MANAGER
        and block.get("owner_kind") == EVENT_OWNER_EVENT_MANAGER
        and block.get("created_by") == login
    )


def _expected_event_version(payload):
    payload = payload or {}
    value = payload.get("expected_version", payload.get("version"))
    try:
        version = int(value)
    except (TypeError, ValueError):
        return None
    return version if version > 0 else None


def create_event(payload, actor, author):
    actor = actor or {}
    if actor.get("role") not in ("admin", ROLE_EVENT_MANAGER):
        return _event_forbidden_result()

    with schedule_mutation("event_create"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_state_for_event_mutation(state)
                event, error = _canonicalize_event_payload(payload, actor=actor, author=author)
                if error:
                    return _validation_event_result(error, state=state)

                group_blocks, _source = _read_group_occupancy_blocks_for_event_mutation()
                conflict = _find_room_time_conflict(
                    event,
                    state.get("blocks", []),
                    allowed_types={"individual", "nachhilfe", "trial", LESSON_TYPE_EVENT},
                )
                if not conflict:
                    conflict = _find_room_time_conflict(
                        event,
                        group_blocks,
                        allowed_types={"group"},
                        state_code="BASE_SCHEDULE_CORRUPT",
                    )
                if conflict:
                    return _event_room_conflict_result(conflict, state=state)

                state["blocks"].append(event)
                _write_individual(state)
                return _event_result(event, ok=True, state=state, cleanup=cleanup)


def update_event(block_id, payload, actor):
    actor = actor or {}
    if actor.get("role") not in ("admin", ROLE_EVENT_MANAGER):
        return _event_forbidden_result()

    with schedule_mutation("event_update"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_state_for_event_mutation(state)
                expected_version = _expected_event_version(payload)
                if expected_version is None:
                    return _event_version_conflict_result(state=state)

                for index, block in enumerate(state.get("blocks", [])):
                    if not isinstance(block, dict) or block.get("id") != block_id:
                        continue
                    if block.get("lesson_type") != LESSON_TYPE_EVENT:
                        return _event_not_found_result(state=state)
                    if not _can_actor_mutate_event(block, actor):
                        return _event_forbidden_result(state=state)
                    if _positive_int(block.get("version"), default=1) != expected_version:
                        return _event_version_conflict_result(state=state)

                    author = {
                        "login": block.get("created_by"),
                        "display_name": block.get("created_by_name") or block.get("teacher"),
                        "owner_kind": block.get("owner_kind"),
                    }
                    event, error = _canonicalize_event_payload(
                        payload,
                        actor=actor,
                        author=author,
                        existing=block,
                    )
                    if error:
                        return _validation_event_result(error, state=state)

                    group_blocks, _source = _read_group_occupancy_blocks_for_event_mutation()
                    conflict = _find_room_time_conflict(
                        event,
                        state.get("blocks", []),
                        exclude_id=block_id,
                        allowed_types={"individual", "nachhilfe", "trial", LESSON_TYPE_EVENT},
                    )
                    if not conflict:
                        conflict = _find_room_time_conflict(
                            event,
                            group_blocks,
                            allowed_types={"group"},
                            state_code="BASE_SCHEDULE_CORRUPT",
                        )
                    if conflict:
                        return _event_room_conflict_result(conflict, state=state)

                    state["blocks"][index] = event
                    _write_individual(state)
                    return _event_result(event, ok=True, state=state, cleanup=cleanup)

                return _event_not_found_result(state=state)


def delete_event(block_id, expected_version, actor):
    actor = actor or {}
    if actor.get("role") not in ("admin", ROLE_EVENT_MANAGER):
        return _event_forbidden_result()

    with schedule_mutation("event_delete"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_state_for_event_mutation(state)
                try:
                    expected_version = int(expected_version)
                except (TypeError, ValueError):
                    expected_version = None
                if expected_version is None or expected_version <= 0:
                    return _event_version_conflict_result(state=state)

                for index, block in enumerate(state.get("blocks", [])):
                    if not isinstance(block, dict) or block.get("id") != block_id:
                        continue
                    if block.get("lesson_type") != LESSON_TYPE_EVENT:
                        return _event_not_found_result(state=state)
                    if not _can_actor_mutate_event(block, actor):
                        return _event_forbidden_result(state=state)
                    if _positive_int(block.get("version"), default=1) != expected_version:
                        return _event_version_conflict_result(state=state)
                    deleted = dict(block)
                    del state["blocks"][index]
                    _write_individual(state)
                    return _event_result(deleted, ok=True, state=state, cleanup=cleanup)

                return _event_not_found_result(state=state)


def _clone_event_blocks(blocks):
    events = []
    for block in blocks or []:
        if isinstance(block, dict) and block.get("lesson_type") == LESSON_TYPE_EVENT:
            cloned = dict(block)
            _normalize_persisted_event_block(cloned)
            events.append(cloned)
    return events


def find_room_time_conflict_with_events(candidate_blocks, event_blocks):
    events = _clone_event_blocks(event_blocks)
    for candidate in candidate_blocks or []:
        if not isinstance(candidate, dict):
            continue
        if (candidate.get("lesson_type") or "group") != "group":
            continue
        conflict = _find_room_time_conflict(
            normalize_room_fields(candidate),
            events,
            allowed_types={LESSON_TYPE_EVENT},
        )
        if conflict:
            return {
                "candidate": {
                    "id": candidate.get("id"),
                    "lesson_type": candidate.get("lesson_type") or "group",
                    "day": candidate.get("day"),
                    "building": candidate.get("building"),
                    "room": candidate.get("room"),
                    "start_time": candidate.get("start_time"),
                    "end_time": candidate.get("end_time"),
                },
                "event": conflict,
            }
    return None


def find_saved_event_conflict_for_base_blocks(candidate_blocks):
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            cleanup = _prepare_individual_state_for_lifecycle(state)
            if cleanup["changed"]:
                _write_individual(state)
            events = _clone_event_blocks(state.get("blocks", []))
    return find_room_time_conflict_with_events(candidate_blocks, events)


def prepare_regeneration_individual_state(individual_blocks, *, revision=None):
    supplied_blocks = [dict(block) for block in (individual_blocks or []) if isinstance(block, dict)]
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            cleanup = _prepare_individual_state_for_lifecycle(state)
            events = _clone_event_blocks(state.get("blocks", []))
    combined = [*supplied_blocks, *events]
    return {
        "state": {
            "last_modified": revision if combined else None,
            "blocks": combined,
        },
        "preserved_events": events,
        "cleanup": cleanup,
    }


def write_regeneration_individual_state(state):
    with _ind_mutex:
        with _locked_individual_file():
            payload = {
                "last_modified": state.get("last_modified") if isinstance(state, dict) else None,
                "blocks": state.get("blocks", []) if isinstance(state, dict) else [],
            }
            _write_individual_payload(payload)
            return payload


def get_individual_lessons():
    with schedule_mutation("individual_state_refresh"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                state = _bootstrap_individual_from_html_if_needed(state)
                cleanup = _prepare_individual_state_for_lifecycle(state)
                if cleanup["changed"]:
                    _write_individual(state)
                    logger.info(
                        "Normalized individual state lifecycle; removed %d expired blocks",
                        cleanup["removed"],
                    )
                return state


def get_individual_revision(prune_expired=True):
    if prune_expired:
        return get_individual_lessons().get("last_modified")
    with _ind_mutex:
        with _locked_individual_file():
            return _read_individual().get("last_modified")


def add_block(block, role):
    with schedule_mutation("individual_block_add"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_individual_state_for_lifecycle(state)
                new_block = _normalize_block(block)
                error = _validate_block(new_block, role)
                if error:
                    return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                error = _validate_trial_not_expired_for_write(new_block)
                if error:
                    return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                error = _validate_saved_event_conflict_for_legacy(new_block, state)
                if error:
                    return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                new_block["id"] = str(uuid.uuid4())
                state["blocks"].append(new_block)
                return _finish_mutation(new_block, None, state, cleanup, True)


def update_block(block_id, updates, role):
    with schedule_mutation("individual_block_update"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_individual_state_for_lifecycle(state)
                for index, block in enumerate(state["blocks"]):
                    if block.get("id") != block_id:
                        continue
                    if block.get("lesson_type") == LESSON_TYPE_EVENT:
                        return _finish_mutation(None, "FORBIDDEN_EVENT_LEGACY", state, cleanup, cleanup["changed"])
                    merged = dict(block)
                    merged.update(_normalize_block(updates))
                    merged["id"] = block_id
                    error = _validate_block(merged, role)
                    if error:
                        return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                    error = _validate_trial_not_expired_for_write(merged)
                    if error:
                        return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                    error = _validate_saved_event_conflict_for_legacy(merged, state, exclude_id=block_id)
                    if error:
                        return _finish_mutation(None, error, state, cleanup, cleanup["changed"])
                    state["blocks"][index] = merged
                    return _finish_mutation(merged, None, state, cleanup, True)
                error = "EXPIRED_TRIAL_PRUNED" if block_id in cleanup.get("removed_ids", []) else "NOT_FOUND"
                return _finish_mutation(None, error, state, cleanup, cleanup["removed"] > 0)


def delete_block(block_id, role=None):
    with schedule_mutation("individual_block_delete"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_individual_state_for_lifecycle(state)
                target = next((b for b in state["blocks"] if b.get("id") == block_id), None)
                if target is None:
                    error = "EXPIRED_TRIAL_PRUNED" if block_id in cleanup.get("removed_ids", []) else None
                    return _finish_mutation(False, error, state, cleanup, cleanup["changed"])
                if target.get("lesson_type") == LESSON_TYPE_EVENT:
                    return _finish_mutation(False, "FORBIDDEN_EVENT_LEGACY", state, cleanup, cleanup["changed"])
                if role == "organizer" and target.get("lesson_type") != "trial":
                    return _finish_mutation(False, "FORBIDDEN", state, cleanup, cleanup["changed"])
                state["blocks"] = [b for b in state["blocks"] if b.get("id") != block_id]
                return _finish_mutation(True, None, state, cleanup, True)


def convert_block_to_regular(block_id, role):
    try:
        from .lesson_type_utils import infer_regular_type_from_subject
    except ImportError:
        from lesson_type_utils import infer_regular_type_from_subject

    with schedule_mutation("individual_block_convert"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_individual_state_for_lifecycle(state)
                for index, block in enumerate(state["blocks"]):
                    if block.get("id") != block_id:
                        continue
                    if block.get("lesson_type") != "trial":
                        return _finish_mutation(None, "NOT_TRIAL", state, cleanup, cleanup["changed"])
                    if role not in ("admin", "editor", "organizer"):
                        return _finish_mutation(None, "FORBIDDEN", state, cleanup, cleanup["changed"])
                    if block.get("day") in TRIAL_ONLY_DAYS:
                        return _finish_mutation(
                            None,
                            "Sunday is allowed only for trial lessons",
                            state,
                            cleanup,
                            cleanup["changed"],
                        )
                    merged = dict(block)
                    merged.pop("trial_dates", None)
                    merged["lesson_type"] = infer_regular_type_from_subject(merged.get("subject", ""))
                    state["blocks"][index] = merged
                    return _finish_mutation(merged, None, state, cleanup, True)
                error = "EXPIRED_TRIAL_PRUNED" if block_id in cleanup.get("removed_ids", []) else "NOT_FOUND"
                return _finish_mutation(None, error, state, cleanup, cleanup["changed"])


def individual_column_has_non_trial_blocks(building, day, room):
    requested = normalize_room_fields({"building": building, "room": room})
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
    return any(
        normalize_room_fields(block).get("building") == requested.get("building")
        and block.get("day") == day
        and normalize_room_fields(block).get("room") == requested.get("room")
        and block.get("lesson_type") != "trial"
        for block in state.get("blocks", [])
        if isinstance(block, dict)
    )


def individual_column_has_event_blocks(building, day, room):
    requested = normalize_room_fields({"building": building, "room": room})
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
    return any(
        normalize_room_fields(block).get("building") == requested.get("building")
        and block.get("day") == day
        and normalize_room_fields(block).get("room") == requested.get("room")
        and block.get("lesson_type") == LESSON_TYPE_EVENT
        for block in state.get("blocks", [])
        if isinstance(block, dict)
    )


def delete_column_blocks(building, day, room):
    requested = normalize_room_fields({"building": building, "room": room})
    with schedule_mutation("individual_column_delete"):
        with _ind_mutex:
            with _locked_individual_file():
                state = _read_individual()
                cleanup = _prepare_individual_state_for_lifecycle(state)
                remaining = []
                removed = 0
                for block in state["blocks"]:
                    normalized_block = normalize_room_fields(block)
                    if (
                        normalized_block.get("building") == requested.get("building")
                        and block.get("day") == day
                        and normalized_block.get("room") == requested.get("room")
                        and block.get("lesson_type") == LESSON_TYPE_EVENT
                    ):
                        return _finish_mutation(0, "COLUMN_HAS_EVENT_BLOCKS", state, cleanup, cleanup["changed"])
                    if (
                        normalized_block.get("building") == requested.get("building")
                        and block.get("day") == day
                        and normalized_block.get("room") == requested.get("room")
                    ):
                        removed += 1
                    else:
                        remaining.append(block)
                if removed:
                    state["blocks"] = remaining
                return _finish_mutation(removed, None, state, cleanup, bool(removed or cleanup["changed"]))
