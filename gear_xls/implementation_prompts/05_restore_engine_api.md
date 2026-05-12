# Prompt 05: restore engine, safety backup, rollback, restore route

Ты работаешь в репозитории `SchedGen_PreRelease`. Это пятая сессия из серии по backup/restore веб-редактора.

Ожидается, что уже реализованы:

- backup create/list/download/upload;
- `backup_manager.py` validation;
- `restore_manager.py` status primitives;
- restore middleware;
- `/api/restore/status`.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `8.6. Project mismatch`
- `9. Domain validation before restore`
- `10. Restore mode`
- `12. Atomic restore algorithm`
- `12.5. Lock reset`
- `13.5. POST /api/backups/<backup_id>/restore`
- `15.9. lock_manager.py`
- `16. Backend tests`
- `17.4. Restore`
- `18. Acceptance criteria`

## Цель

Реализовать фактическое восстановление persisted state из stored backup:

- admin-only;
- requires active edit lock held by current admin;
- validates backup before any writes;
- creates safety backup;
- writes files through temp files + `os.replace`;
- resets edit lock;
- updates revisions;
- handles rollback/recovery.

Frontend modal не реализуй в этой сессии.

## Обязательные backend changes

1. В `gear_xls/lock_manager.py` добавить restore-specific helper, например:

   ```python
   def clear_for_restore(restored_by_login: str) -> dict:
       ...
   ```

   Expected effect:

   - `holder = None`;
   - increment `version`;
   - `last_holder` set to previous holder;
   - `released_at` set to now;
   - `released_by = restored_by_login`;
   - `release_reason = "restore_completed"`.

   Do not restore `lock.json` from backup.

2. В `gear_xls/restore_manager.py` добавить restore engine:

   - process-local restore mutex;
   - `restore_backup(backup_id, login, display_name, allow_foreign_project=False)`;
   - lower-level restore function for rollback that does not create another safety backup;
   - domain validation;
   - staged/in-memory normalized payloads;
   - temp file writes in same target directories;
   - rollback from safety backup;
   - recovery mode if rollback fails.

3. Restore high-level order:

   1. route checks role `admin`;
   2. payload `confirm === true`;
   3. active edit lock belongs to current admin;
   4. backup id strict validation and backup exists;
   5. ZIP structure/checksum/security validation;
   6. project root mismatch check; if mismatch and no `allow_foreign_project`, return `409 PROJECT_ROOT_MISMATCH` before restore mode;
   7. domain-validate state JSON, spiski and schedule HTML;
   8. acquire restore mutex;
   9. set restore mode `active=true`;
   10. create safety backup with `backup_kind='safety'`;
   11. prepare normalized payloads;
   12. write:
       - `gear_xls/schedule_state/base_schedule.json`;
       - `gear_xls/schedule_state/individual_lessons.json`;
       - allowed `spiski/*.txt`;
       - `gear_xls/html_output/schedule.html`;
   13. clear edit lock with reason `restore_completed`;
   14. set restore mode complete and increment `generation`;
   15. return success response.

4. Revision rules:

   - one `restore_revision` timestamp for this restore;
   - for base:
     - if restored base has blocks or had non-null `published_at`, set `published_at = restore_revision` and `published_by = current admin login`;
     - if restored base has no blocks and `published_at` is null, keep both null;
   - for individual:
     - always set `last_modified = restore_revision`.

5. Domain validation:

   Base:

   - object with `blocks` list;
   - each block object;
   - required non-empty string fields:
     - `building`, `day`, `room`, `subject`, `start_time`, `end_time`, `lesson_type`;
   - `lesson_type == "group"`;
   - day in `Mo`, `Di`, `Mi`, `Do`, `Fr`, `Sa`;
   - strict time `HH:MM`, end > start;
   - optional `teacher`, `students`, `color`, `room_display` strings;
   - optional `start_row >= 0`, `row_span >= 1`;
   - reject absurd text fields over 1000 chars.

   Individual:

   - object with `blocks` list;
   - each block object;
   - required non-empty `id`, `building`, `day`, `room`, `subject`, `start_time`, `end_time`, `lesson_type`;
   - unique ids;
   - lesson type in `individual`, `nachhilfe`, `trial`;
   - strict time and day checks;
   - for `trial`, valid non-empty sorted/normalized `trial_dates` matching weekday;
   - for non-trial, remove stale `trial_dates`.

   Spiski:

   - UTF-8 decodable;
   - no NUL bytes;
   - non-empty line max 200 chars;
   - preserve order or normalize line endings to `\n`.

6. Rollback:

   - if failure before target replacement: clear restore mode, keep safety backup, return error;
   - if failure after one or more replacements:
     - attempt rollback from safety backup without recursion;
     - if rollback succeeds, clear restore mode, increment generation, return `RESTORE_ROLLED_BACK`;
     - if rollback fails, set `active=true`, `recovery_required=true`, `RESTORE_PARTIAL_FAILURE`, include safety backup id, block APIs.

7. Add route:

   ```text
   POST /api/backups/<backup_id>/restore
   ```

   Payload:

   ```json
   {
     "confirm": true,
     "allow_foreign_project": false
   }
   ```

   Errors:

   - no lock: `403 NO_LOCK`;
   - not admin: `403 FORBIDDEN`;
   - restore already active: `423` or `409 RESTORE_IN_PROGRESS`;
   - invalid/missing backup: `400`/`404`;
   - project mismatch: `409 PROJECT_ROOT_MISMATCH`.

   Success response:

   ```json
   {
     "ok": true,
     "restored_from": "backup_id",
     "safety_backup": {
       "id": "...",
       "download_url": "/api/backups/<id>/download"
     },
     "base_revision": "... or null",
     "individual_revision": "...",
     "restore_generation": 13
   }
   ```

8. Ensure restore middleware allows this route only for the restore-admin/in-progress restore route and still blocks other users.

## Tests

Add/extend pytest coverage:

1. Restore requires admin.
2. Restore requires `confirm: true`.
3. Restore requires active lock held by current admin.
4. Restore rejects project mismatch without `allow_foreign_project`.
5. Restore creates safety backup.
6. Restore writes base state and revision rules.
7. Restore writes individual state and revision rules.
8. Restore restores all allowed spiski files.
9. Restore restores `schedule.html`.
10. Restore does not restore `lock.json` from backup.
11. Restore clears current lock with `release_reason: "restore_completed"`.
12. Restore increments restore generation after success.
13. Domain validation rejects invalid time format/end <= start.
14. Domain validation rejects invalid lesson types.
15. Domain validation normalizes/removes invalid stale `trial_dates` according to ТЗ.
16. Partial failure after one replacement attempts rollback.
17. Rollback success returns `RESTORE_ROLLED_BACK` and generation increments.
18. Rollback failure sets `recovery_required=true`.

## Проверки

Run:

```powershell
python -m py_compile gear_xls/restore_manager.py gear_xls/backup_manager.py gear_xls/lock_manager.py gear_xls/server_routes.py
python -m pytest tests/test_backup_restore.py
```

If tests are split, run all backup/restore tests.

## Финальный ответ

Кратко укажи:

- restore algorithm implemented;
- safety backup/rollback behavior;
- lock reset behavior;
- tests and checks run.
