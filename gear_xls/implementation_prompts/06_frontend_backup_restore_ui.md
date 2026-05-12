# Prompt 06: frontend backup/restore UI and polling overlay

Ты работаешь в репозитории `SchedGen_PreRelease`. Это шестая сессия из серии по backup/restore веб-редактора.

Ожидается, что backend уже реализует:

- `GET /api/backups`;
- `POST /api/backups`;
- `GET /api/backups/<backup_id>/download`;
- `POST /api/backups/upload`;
- `POST /api/backups/<backup_id>/restore`;
- `GET /api/restore/status`;
- restore middleware and `/api/status.restore`.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `4. Dirty local state`
- `11. Server middleware during restore`
- `13. API`
- `14. Frontend UX`
- `14.5. Updating lock_ui.js for restore errors`
- `15.7. server_routes.py`
- `18. Acceptance criteria`

## Цель

Добавить frontend UI для backup/restore в веб-редакторе и обеспечить, что активные/старые вкладки реагируют на restore mode.

## Обязательные изменения

1. Создать:

   ```text
   gear_xls/static/backup_ui.js
   ```

2. Подключить его в `/schedule` в `gear_xls/server_routes.py` после существующих scripts, предпочтительно после:

   ```html
   <script src="/static/schedule_search_ui.js"></script>
   ```

3. `backup_ui.js` initialization:

   - init only when `window.SchedGenAuthUI` exists;
   - admin UI only when `window.USER_ROLE === "admin"`;
   - non-admin must not see backup/restore menu items;
   - API security remains server-side too.

4. Menu:

   - dynamically insert into `#menuDropdown` or bind generated placeholders:

     ```text
     Создать резервную копию
     Восстановить из резервной копии
     ```

   - do not reintroduce old `#saveSchedule` / `#saveIntermediate`.

5. Create backup modal:

   - optional comment;
   - checkbox `Скачать ZIP после создания`;
   - before backup call `window.SchedGenBaseSyncUI.hasUnpublishedGroupChanges()`;
   - if dirty base changes exist, show warning:

     ```text
     Есть неопубликованные изменения группового расписания. Резервная копия сохранит только опубликованное серверное состояние. Сначала опубликуйте расписание или продолжите без этих изменений.
     ```

   - actions:
     - `Опубликовать и создать backup`: call `window.SchedGenBaseSyncUI.publishScheduleForNavigation()`, backup only if it returns `true`;
     - `Создать backup без неопубликованных изменений`;
     - `Отмена`.

   - call `POST /api/backups`;
   - open `download_url` if requested.

6. Restore modal:

   - list server backups from `GET /api/backups`;
   - show date, author, comment, kind, size, revisions, valid/invalid;
   - upload ZIP file through `POST /api/backups/upload`;
   - uploaded backup appears/selects after successful upload;
   - warning that current state will be replaced;
   - checkbox:

     ```text
     Я понимаю, что текущее состояние будет заменено
     ```

   - restore button disabled until a valid backup is selected and checkbox checked;
   - require active edit mode before restore:
     - check `window.SchedGenAuthUI.isEditMode()`;
     - if false, show:

       ```text
       Для восстановления сначала нажмите «Начать редактирование».
       ```

   - call `POST /api/backups/<backup_id>/restore` with `confirm: true`;
   - handle `PROJECT_ROOT_MISMATCH` by showing second confirmation, then retry with `allow_foreign_project: true`;
   - show fullscreen overlay while restore is running;
   - on success, show message then hard reload `/schedule`.

7. Restore polling/overlay:

   - poll `/api/restore/status` for all authenticated users;
   - show blocking overlay when `restore_in_progress` or `active` is true;
   - detect `generation` changes after restore and hard reload stale pages before further editing;
   - close open dialogs via `window.SchedGenLockUI.closeOpenDialogs()` if available;
   - disable pointer events/edit controls;
   - call `window.SchedGenAuthUI.setEditMode(false)` if available.

   Overlay text:

   ```text
   Администратор выполняет восстановление базы расписания. Работа временно заблокирована. Вы сможете зайти после завершения восстановления.
   ```

8. Update `gear_xls/static/lock_ui.js`:

   - when any lock/status request receives JSON code `RESTORE_IN_PROGRESS`:
     - close dialogs;
     - stop heartbeat/polling or at least clear local lock state;
     - set edit mode false;
     - call `window.SchedGenBackupUI.handleRestoreInProgress(data)` if available;
     - do not keep trying to edit with old lock.

   Useful exported helper:

   ```js
   window.SchedGenLockUI.clearLocalLockStateForRestore = function () { ... }
   ```

9. Escape all user-controlled text:

   - backup comments;
   - filenames;
   - author/display name;
   - validation messages where appropriate.

10. Keep frontend independent from CSRF token field. Backup JSON/multipart requests should use same-origin `fetch`.

## Style/UX constraints

- Do not add visible explanatory tutorial text beyond necessary labels/errors.
- Modal controls should be compact and operational.
- Avoid page-wide layout shifts.
- Do not add marketing-like UI.

## Checks

Run syntax checks:

```powershell
node --check gear_xls/static/backup_ui.js
node --check gear_xls/static/lock_ui.js
python -m py_compile gear_xls/server_routes.py
```

Run backend tests to ensure API still works:

```powershell
python -m pytest tests/test_backup_restore.py
```

Manual/browser checklist if a dev server is available:

- admin sees backup/restore menu items;
- editor/organizer/viewer do not see backup/restore menu items;
- dirty base warning appears before backup;
- backup with download opens/downloads ZIP;
- restore without edit mode is blocked with clear message;
- restore project mismatch asks second confirmation;
- active non-restore tab shows overlay and cannot edit/export;
- after restore success, page hard reloads.

## Финальный ответ

Кратко укажи:

- frontend files changed;
- menu/modal behavior;
- restore overlay behavior;
- checks run and any manual checks not run.
