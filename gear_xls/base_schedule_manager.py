import json
import logging
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime


BASE_SCHEDULE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "schedule_state", "base_schedule.json"
)
BASE_LOCK_PATH = BASE_SCHEDULE_PATH + ".lock"
_base_mutex = threading.Lock()
logger = logging.getLogger(__name__)


def _empty_base():
    return {"published_at": None, "published_by": None, "blocks": []}


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
        logger.warning("Failed to release base schedule lock: %s", exc)


@contextmanager
def _locked_base_file():
    os.makedirs(os.path.dirname(BASE_LOCK_PATH), exist_ok=True)
    with open(BASE_LOCK_PATH, "a+b") as lock_fp:
        backend = _acquire_file_lock(lock_fp)
        try:
            yield
        finally:
            _release_file_lock(lock_fp, backend)


def _read_base():
    if not os.path.exists(BASE_SCHEDULE_PATH):
        return _empty_base()
    try:
        with open(BASE_SCHEDULE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_base()
        blocks = data.get("blocks", [])
        return {
            "published_at": data.get("published_at"),
            "published_by": data.get("published_by"),
            "blocks": blocks if isinstance(blocks, list) else [],
        }
    except Exception as exc:
        logger.warning("Failed to read base schedule: %s", exc)
        return _empty_base()


def _write_base(state):
    os.makedirs(os.path.dirname(BASE_SCHEDULE_PATH), exist_ok=True)
    payload = {
        "published_at": state.get("published_at"),
        "published_by": state.get("published_by"),
        "blocks": state.get("blocks", []),
    }
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=os.path.dirname(BASE_SCHEDULE_PATH),
            delete=False,
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, BASE_SCHEDULE_PATH)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def get_base_schedule():
    return _read_base()


def get_base_revision():
    return get_base_schedule().get("published_at")


def publish_base(blocks, published_by):
    with _base_mutex:
        with _locked_base_file():
            _read_base()
            filtered_blocks = [
                block
                for block in (blocks or [])
                if isinstance(block, dict) and block.get("lesson_type") == "group"
            ]
            state = {
                "published_at": datetime.utcnow().isoformat(),
                "published_by": published_by,
                "blocks": filtered_blocks,
            }
            _write_base(state)
            return state


def base_has_group_lessons_in_column(building, day, room):
    blocks = get_base_schedule().get("blocks", [])
    return any(
        block.get("building") == building
        and block.get("day") == day
        and block.get("room") == room
        and block.get("lesson_type") == "group"
        for block in blocks
        if isinstance(block, dict)
    )
