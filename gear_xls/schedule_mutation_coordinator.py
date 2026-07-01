from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager

from gear_xls.runtime_paths import get_schedule_mutation_lock_path


SCHEDULE_MUTATION_LOCK_PATH = get_schedule_mutation_lock_path()
DEFAULT_COORDINATOR_TIMEOUT_SECONDS = 2.0
DEFAULT_COORDINATOR_RETRY_SECONDS = 0.025

logger = logging.getLogger(__name__)
_process_mutex = threading.RLock()
_local = threading.local()


class ScheduleMutationBusy(RuntimeError):
    code = "SCHEDULE_MUTATION_BUSY"
    status_code = 423

    def __init__(self, message: str = "Schedule mutation is busy"):
        super().__init__(message)
        self.message = message

    def to_payload(self) -> dict:
        return {"ok": False, "error": self.message, "code": self.code}


def _ensure_lock_file(fp) -> None:
    fp.seek(0)
    if os.path.getsize(fp.name) == 0:
        fp.write(b"0")
        fp.flush()
        fp.seek(0)


def _try_acquire_file_lock(fp) -> str | None:
    try:
        import msvcrt

        _ensure_lock_file(fp)
        fp.seek(0)
        msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
        return "msvcrt"
    except ImportError:
        try:
            import fcntl
        except ImportError as exc:
            raise RuntimeError("Cannot acquire schedule mutation lock") from exc
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return "fcntl"
        except OSError:
            return None
    except OSError:
        return None


def _release_file_lock(fp, backend: str | None) -> None:
    if backend == "msvcrt":
        try:
            import msvcrt

            fp.seek(0)
            msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception as exc:
            logger.warning("Failed to release schedule mutation lock: %s", exc)
    elif backend == "fcntl":
        try:
            import fcntl

            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logger.warning("Failed to release schedule mutation lock: %s", exc)


def _acquire_process_mutex(timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        if _process_mutex.acquire(blocking=False):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(DEFAULT_COORDINATOR_RETRY_SECONDS, max(0.0, deadline - time.monotonic())))


@contextmanager
def schedule_mutation(
    reason: str | None = None,
    *,
    timeout_seconds: float = DEFAULT_COORDINATOR_TIMEOUT_SECONDS,
    retry_seconds: float = DEFAULT_COORDINATOR_RETRY_SECONDS,
):
    depth = int(getattr(_local, "depth", 0) or 0)
    if depth > 0:
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth -= 1
        return

    if not _acquire_process_mutex(timeout_seconds):
        raise ScheduleMutationBusy()

    os.makedirs(os.path.dirname(SCHEDULE_MUTATION_LOCK_PATH), exist_ok=True)
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    lock_fp = None
    backend = None
    try:
        lock_fp = open(SCHEDULE_MUTATION_LOCK_PATH, "a+b")
        while True:
            backend = _try_acquire_file_lock(lock_fp)
            if backend:
                break
            if time.monotonic() >= deadline:
                raise ScheduleMutationBusy()
            time.sleep(min(retry_seconds, max(0.0, deadline - time.monotonic())))

        _local.depth = 1
        _local.reason = reason
        try:
            yield
        finally:
            _local.depth = 0
            _local.reason = None
    finally:
        if lock_fp is not None:
            _release_file_lock(lock_fp, backend)
            lock_fp.close()
        _process_mutex.release()
