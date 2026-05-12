# Prompt 02: server backup core, list, create, download

Ты работаешь в репозитории `SchedGen_PreRelease`. Это вторая сессия из серии по backup/restore веб-редактора.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `3. Источник истины backup-а`
- `5. ZIP backup format`
- `6. Server storage`
- `7.1. backup_manager.py`
- `8. ZIP validation and security`
- `8.5. schedule.html validation`
- `13.1` - `13.3`
- `16. Backend tests`
- `17.1`, `17.2`
- `18. Acceptance criteria`

Сессия 01 должна была удалить старый standalone save flow. Если в активном `html_output/schedule.html` все еще есть `saveSchedule`, `saveIntermediate`, `/save_intermediate`, `final_schedule.html`, `intermediate_schedule.html` или `body.static-schedule`, не возвращай старую логику. Либо исправь это локально, либо явно зафиксируй blocker.

## Цель

Реализовать серверное создание, хранение, listing и download ZIP backup-ов persisted state веб-редактора.

В этой сессии не реализуй restore engine, upload UI и frontend modal.

## Обязательные изменения

1. В `gear_xls/runtime_paths.py` добавить:

   ```python
   def get_backup_dir(project_root: str | None = None) -> str:
       return os.path.join(get_gear_xls_dir(project_root), "backups")
   ```

   Если удобно сразу добавить `get_restore_status_path()`, это допустимо, но restore status не реализуй в этой сессии.

2. В `.gitignore` добавить:

   ```text
   gear_xls/backups/
   gear_xls/schedule_state/restore_status.json
   ```

3. Создать `gear_xls/backup_manager.py`.

   Минимальные responsibilities:

   - constants:
     - schema: `schedgen.web_editor_backup`;
     - schema version: `1`;
     - backup filename regex;
     - expected archive paths;
     - allowed spiski filenames;
     - explicit size limits from ТЗ;
   - `create_backup(created_by, created_by_display_name, comment='', backup_kind='manual', ...)`;
   - `list_backups()`;
   - `get_backup_path(backup_id)` with strict id validation before filesystem access;
   - `read_manifest_from_zip(path)`;
   - `validate_backup_zip(path, *, deep=True)`;
   - checksum and size validation;
   - safe ZIP entry validation;
   - schedule HTML legacy-artifact rejection;
   - no dependency on browser DOM.

4. Backup must include exactly:

   ```text
   manifest.json
   state/base_schedule.json
   state/individual_lessons.json
   html/schedule.html
   spiski/disciplins.txt
   spiski/groups.txt
   spiski/teachers.txt
   spiski/kabinets_Villa.txt
   spiski/kabinets_Kolibri.txt
   ```

5. Source-of-truth rules:

   - use persisted server files only;
   - missing `spiski/*.txt` becomes empty file in ZIP;
   - missing state JSON becomes safe empty default state;
   - existing but invalid state JSON must fail backup creation, not be silently replaced;
   - missing `schedule.html` must fail backup creation with clear error;
   - do not include lock, restore status, backups, logs, exports, PDFs, source Excel/XLSM, users or secrets.

6. Manifest:

   - `created_at` UTC with `Z`;
   - `dirty_dom_included: false`;
   - `backup_kind` initially supports at least `manual` and `safety`;
   - `files` contains every non-manifest expected path exactly once with `sha256` and `size`.

7. Comment validation:

   - trim;
   - max 500 chars;
   - store/render as plain text;
   - too long returns API code `COMMENT_TOO_LONG`.

8. In `gear_xls/server_routes.py` add API routes:

   - `GET /api/backups`
   - `POST /api/backups`
   - `GET /api/backups/<backup_id>/download`

   Requirements:

   - login required;
   - role `admin`;
   - backup mutation uses existing same-origin Origin CSRF middleware;
   - no wildcard CORS for backup routes;
   - add backup API paths/prefixes to JSON auth handling so unauthenticated API calls get JSON `401`;
   - damaged ZIPs in backup dir appear in list as `valid:false` with `invalid_reason`;
   - invalid `backup_id` rejected before filesystem access.

9. If `/save_intermediate` still exists from older code, ensure it is removed or returns deprecated JSON and never opens Tk.

## Tests

Add pytest tests, preferably in `tests/test_backup_restore.py` or a focused backup test file.

Minimum tests for this session:

1. `create_backup` creates ZIP with expected paths and manifest.
2. Manifest checksums and sizes match actual ZIP entries.
3. Missing `schedule.html` causes clear backup error.
4. Missing state JSON is backed up as empty default state.
5. Existing invalid state JSON fails backup creation.
6. Missing allowed `spiski` file is backed up as empty file.
7. `list_backups` returns valid metadata and marks corrupted ZIP as invalid.
8. Download validates `backup_id` and rejects traversal/unsafe ids.
9. Validation rejects:
   - non-ZIP;
   - path traversal ZIP entry;
   - duplicate ZIP entries;
   - checksum mismatch;
   - unknown schema/schema_version;
   - extra unexpected file;
   - old `schedule.html` containing `saveSchedule` or `/save_intermediate`.

Use temporary project root fixtures. Remember `runtime_paths.assert_valid_project_layout()` expects minimal root layout:

```text
<tmp>/gear_xls/server_routes.py or package under test as appropriate
<tmp>/xlsx_initial/
<tmp>/visualiser/
<tmp>/gui.py
```

Set `SCHEDGEN_PROJECT_ROOT` before importing modules if the module under test resolves paths at import time.

## Проверки

Run:

```powershell
python -m py_compile gear_xls/runtime_paths.py gear_xls/backup_manager.py gear_xls/server_routes.py
python -m pytest tests/test_backup_restore.py
```

If tests are split across files, run the relevant pytest subset.

## Финальный ответ

Кратко укажи:

- добавленные API endpoints;
- формат/место хранения backup;
- какие tests добавлены;
- какие проверки запускались.
