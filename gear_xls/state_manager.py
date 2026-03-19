import json
import logging
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from html import unescape

from base_schedule_manager import (
    BASE_SCHEDULE_PATH,
    base_has_group_lessons_in_column,
    get_base_revision,
    get_base_schedule,
    publish_base,
)


INDIVIDUAL_LESSONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "schedule_state", "individual_lessons.json"
)
INDIVIDUAL_LOCK_PATH = INDIVIDUAL_LESSONS_PATH + ".lock"
SCHEDULE_HTML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "html_output", "schedule.html"
)
VALID_DAYS = {"Mo", "Di", "Mi", "Do", "Fr", "Sa"}
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
        if not isinstance(data, dict):
            return _empty_state()
        blocks = data.get("blocks", [])
        return {
            "last_modified": data.get("last_modified"),
            "blocks": blocks if isinstance(blocks, list) else [],
        }
    except Exception as exc:
        logger.warning("Failed to read individual lessons: %s", exc)
        return _empty_state()


def _write_individual(state):
    os.makedirs(os.path.dirname(INDIVIDUAL_LESSONS_PATH), exist_ok=True)
    payload = {
        "last_modified": datetime.utcnow().isoformat(),
        "blocks": state.get("blocks", []),
    }
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
        state["last_modified"] = payload["last_modified"]
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _pristine_individual_state(state):
    return state.get("last_modified") is None and not state.get("blocks")


def _to_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_embedded_individual_block(attrs_text, body):
    attrs = dict(re.findall(r"data-([\w-]+)=['\"]([^'\"]*)['\"]", attrs_text))
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

    if lesson_type not in ("individual", "nachhilfe"):
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


def _validate_block(block, role):
    for field in ("day", "start_time", "end_time", "lesson_type", "subject", "room", "building"):
        if not str(block.get(field, "")).strip():
            return f"{field} required"
    if block["day"] not in VALID_DAYS:
        return "Invalid day"
    if role == "editor" and block.get("lesson_type") not in ("individual", "nachhilfe"):
        return "Forbidden lesson_type"
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


def get_individual_lessons():
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            return _bootstrap_individual_from_html_if_needed(state)


def get_individual_revision():
    return get_individual_lessons().get("last_modified")


def add_block(block, role):
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            new_block = _normalize_block(block)
            error = _validate_block(new_block, role)
            if error:
                return None, error
            new_block["id"] = str(uuid.uuid4())
            state["blocks"].append(new_block)
            _write_individual(state)
            return new_block, None


def update_block(block_id, updates, role):
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            for index, block in enumerate(state["blocks"]):
                if block.get("id") != block_id:
                    continue
                merged = dict(block)
                merged.update(_normalize_block(updates))
                merged["id"] = block_id
                error = _validate_block(merged, role)
                if error:
                    return None, error
                state["blocks"][index] = merged
                _write_individual(state)
                return merged, None
            return None, "NOT_FOUND"


def delete_block(block_id):
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            remaining = [block for block in state["blocks"] if block.get("id") != block_id]
            if len(remaining) == len(state["blocks"]):
                return False
            state["blocks"] = remaining
            _write_individual(state)
            return True


def delete_column_blocks(building, day, room):
    with _ind_mutex:
        with _locked_individual_file():
            state = _read_individual()
            remaining = []
            removed = 0
            for block in state["blocks"]:
                if block.get("building") == building and block.get("day") == day and block.get("room") == room:
                    removed += 1
                else:
                    remaining.append(block)
            if removed:
                state["blocks"] = remaining
                _write_individual(state)
            return removed
