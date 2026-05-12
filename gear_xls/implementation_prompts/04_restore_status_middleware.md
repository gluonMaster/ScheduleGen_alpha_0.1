# Prompt 04: restore status и server middleware

Ты работаешь в репозитории `SchedGen_PreRelease`. Это четвертая сессия из серии по backup/restore веб-редактора.

Ожидается, что backup create/list/download/upload уже реализованы. Restore engine еще не реализован.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `10. Restore mode`
- `11. Server middleware during restore`
- `13.6. GET /api/restore/status`
- `15.7. server_routes.py`
- `15.8. runtime_paths.py`
- `16. Backend tests`
- `17.4. Restore`

## Цель

Добавить server-side restore mode state и middleware, который блокирует schedule-sensitive APIs во время restore/recovery.

В этой сессии не реализуй фактическую замену файлов из backup. Нужны только status/state/middleware primitives, которыми воспользуется следующая сессия.

## Обязательные изменения

1. В `gear_xls/runtime_paths.py` добавить, если еще нет:

   ```python
   def get_restore_status_path(project_root: str | None = None) -> str:
       return os.path.join(get_schedule_state_dir(project_root), "restore_status.json")
   ```

2. Убедиться, что `.gitignore` содержит:

   ```text
   gear_xls/schedule_state/restore_status.json
   ```

3. Создать или расширить `gear_xls/restore_manager.py` status-only функциональностью:

   - read/write restore status JSON через temp file + `os.replace`;
   - default status:

     ```json
     {
       "active": false,
       "started_at": null,
       "started_by": null,
       "message": null,
       "generation": 0,
       "last_completed_at": null,
       "last_completed_by": null,
       "last_restored_from": null,
       "recovery_required": false,
       "recovery_message": null,
       "safety_backup_id": null
     }
     ```

   - UTC timestamps with `Z`;
   - process-local mutex for status writes;
   - stale detection with `RESTORE_STALE_AFTER_SECONDS = 600`;
   - helpers such as:
     - `get_restore_status()`;
     - `is_restore_active()`;
     - `begin_restore(...)`;
     - `complete_restore(...)`;
     - `fail_restore_prewrite(...)`;
     - `mark_recovery_required(...)`;
     - `clear_restore_status(confirm=True, ...)`.

4. Add API routes in `gear_xls/server_routes.py`:

   - `GET /api/restore/status` for all authenticated users;
   - `POST /api/restore/status/clear` for admin.

   Clear endpoint requirements:

   - role `admin`;
   - payload `{"confirm": true}`;
   - may clear stale non-recovery mode;
   - may clear recovery mode only after explicit confirm;
   - log action.

5. Extend JSON auth handling:

   - `/api/restore/status`;
   - `/api/restore/status/clear`;
   - `/api/restore/*` prefix, if implemented via prefix helper.

6. Extend `GET /api/status` with:

   ```json
   "restore": {
     "active": false,
     "generation": 12,
     "last_completed_at": "...",
     "recovery_required": false,
     "message": null
   }
   ```

7. Add `before_request` middleware in `server_routes.py`.

   When restore status is active or `recovery_required=true`, allow:

   - `GET /api/restore/status`;
   - `GET /api/status`;
   - static assets: `/static/*`, `/js_modules/*`;
   - `/login`, `/logout`, `/health`;
   - `GET /api/backups` for admin;
   - `GET /api/backups/<id>/download` for admin;
   - future in-progress restore route for restore-admin only, if route exists.

   Block with JSON `RESTORE_IN_PROGRESS` and consistent status (`423` preferred) at least:

   - `/api/lock/status`;
   - `/api/lock/acquire`;
   - `/api/lock/release`;
   - `/api/lock/heartbeat`;
   - `DELETE /api/lock`;
   - `/api/schedule`;
   - `/api/individual_lessons`;
   - `/api/schedule/publish`;
   - `/api/blocks*`;
   - `/api/columns`;
   - `/api/spiski/*`, including `/api/spiski/add`;
   - backup creation/upload while restore active;
   - `/export_to_excel`.

   For HTML `/schedule` while active:

   - do not serve editable schedule to anyone;
   - admin gets minimal status/recovery page;
   - non-admin gets blocking page;
   - page text includes:

     ```text
     Администратор выполняет восстановление базы расписания. Работа временно заблокирована. Вы сможете зайти после завершения восстановления.
     ```

8. Keep same-origin CSRF behavior unchanged.

## Tests

Add/extend pytest coverage:

1. Default restore status is returned when file is missing.
2. Status writes are persisted and read back.
3. `/api/restore/status` requires login and returns JSON.
4. `/api/restore/status/clear` requires admin and confirm.
5. Active restore mode blocks each mutating/schedule-sensitive endpoint family.
6. Active restore mode still allows `/api/restore/status` and `/api/status`.
7. Active restore mode does not serve editable `/schedule`.
8. Stale non-recovery mode can be cleared by admin.
9. Recovery mode cannot be silently auto-cleared.
10. `/api/status` includes restore fields.

## Проверки

Run:

```powershell
python -m py_compile gear_xls/runtime_paths.py gear_xls/restore_manager.py gear_xls/server_routes.py
python -m pytest tests/test_backup_restore.py
```

If tests are split, run all restore-status/middleware tests.

## Финальный ответ

Кратко укажи:

- где хранится restore status;
- какие routes добавлены;
- какие endpoints блокируются middleware;
- какие проверки запускались.
