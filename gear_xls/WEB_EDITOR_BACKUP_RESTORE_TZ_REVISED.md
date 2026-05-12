# Исправленное ТЗ: backup/restore состояния веб-редактора расписания

## 0. Назначение этого документа

Это ТЗ предназначено для реализации в отдельной Codex-сессии по приложенному проекту `gear_xls`. Документ должен быть достаточным без дополнительного контекста из текущего чата.

Главная цель: заменить устаревшее сохранение standalone HTML полноценным серверным механизмом резервного копирования и восстановления persisted-состояния веб-редактора.

Ключевые решения этого ТЗ:

- backup создается **только из persisted server state**, а не из текущего DOM браузера;
- restore требует роль `admin` и активный edit lock текущего admin;
- старые standalone HTML flows (`#saveSchedule`, `#saveIntermediate`, `/save_intermediate`, `final_schedule.html`, `intermediate_schedule.html`) должны исчезнуть из активного UI и кода;
- ZIP backup содержит state JSON, `schedule.html`, разрешенные `spiski`-файлы и `manifest.json`;
- restore валидирует ZIP до записи, создает safety backup, пишет файлы через staging/temp + `os.replace`, сбрасывает edit lock и уведомляет/блокирует старые вкладки;
- во время restore все пользователи, кроме restore-admin в служебных endpoints, блокируются через server-side restore mode и frontend overlay/polling;
- после успешного restore старые вкладки должны сделать hard reload или не иметь возможности продолжить редактирование старого DOM.

## 1. Подтвержденное текущее состояние кода

В проекте уже есть серверная multiuser-архитектура. Реализацию надо привязать к ней, а не проектировать абстрактно.

### 1.1. Важные файлы

- `gear_xls/server_routes.py`
  - Flask app, auth, routes, CSRF same-origin middleware.
  - `/schedule` читает `gear_xls/html_output/schedule.html`, inject-ит globals `window.CURRENT_USER`, `window.USER_ROLE`, `window.DISPLAY_NAME`, `window.PUBLISHED_BASE_AVAILABLE` и подключает static JS.
  - Сейчас подключаются: `/static/auth_ui.js`, `/static/base_sync_ui.js`, `/static/lock_ui.js`, `/js_modules/trial_ui.js`, `/static/individual_ui.js`, `/static/schedule_search_ui.js`.
  - Есть старый route `POST /save_intermediate`, который использует Tk file dialog и сохраняет HTML из браузера. Его надо удалить или заменить deprecation-ответом, но frontend не должен его вызывать.
- `gear_xls/generators/html_structure_generator.py`
  - `generate_control_panel()` генерирует toolbar, `#menuButton`, `#menuDropdown`, `#saveIntermediate`, `#saveSchedule`, `#exportToExcel`.
- `gear_xls/html_javascript.py`
  - Инлайнит содержимое `js_modules/*.js` внутрь `schedule.html`.
  - Сейчас включает `js_modules/save_export.js`.
- `gear_xls/html_styles.py`
  - Содержит стили `#saveIntermediate`, `#saveSchedule`, `body.static-schedule` и mobile selectors для старых save-кнопок.
- `gear_xls/js_modules/save_export.js`
  - Содержит старую логику `#saveSchedule` -> скачать `final_schedule.html`.
  - Содержит старую логику `#saveIntermediate` -> POST `/save_intermediate` или fallback download `intermediate_schedule.html`.
- `gear_xls/js_modules/app_initialization.js`
  - Сейчас вызывает `initSaveExport()` без `typeof` guard.
  - Содержит ветки `body.static-schedule`.
- `gear_xls/static/auth_ui.js`
  - Скрывает `#saveIntermediate`, `#saveSchedule`, `#exportToExcel` по ролям.
  - Экспортирует `window.SchedGenAuthUI` с `currentRole()`, `currentUser()`, `isEditMode()`, `setEditMode()`, `setNavEditorState()`.
- `gear_xls/static/lock_ui.js`
  - Управляет edit lock через `/api/lock/*`.
  - Экспортирует `window.SchedGenLockUI.closeOpenDialogs()`, `refreshLockStatus()`, `handleSessionExpired()`.
- `gear_xls/static/base_sync_ui.js`
  - Управляет публикацией группового расписания.
  - Экспортирует `window.SchedGenBaseSyncUI.hasUnpublishedGroupChanges()`, `publishScheduleForNavigation()`, `getBaseRevision()`, `applyBaseScheduleData()`.
- `gear_xls/static/individual_ui.js`
  - Синхронизирует индивидуальные/nachhilfe/trial занятия через `/api/schedule` и `/api/blocks*`.
  - Экспортирует `window.SchedGenIndividualUI` и `window.refreshIndividualLayer`.
- `gear_xls/runtime_paths.py`
  - Уже содержит path helpers: `get_schedule_state_dir()`, `get_base_schedule_path()`, `get_individual_lessons_path()`, `get_lock_json_path()`, `get_schedule_html_path()`, `get_spiski_dir()`, `get_project_root_id()`.
- `gear_xls/base_schedule_manager.py`
  - Published base/group state: `schedule_state/base_schedule.json`.
  - Current revision: `published_at`.
  - Existing writes use `datetime.utcnow().isoformat()` and `os.replace`.
- `gear_xls/state_manager.py`
  - Individual/nachhilfe/trial state: `schedule_state/individual_lessons.json`.
  - Current revision: `last_modified`.
  - Existing writes use file locks and `os.replace`.
- `gear_xls/lock_manager.py`
  - Runtime edit lock: `schedule_state/lock.json`.
  - Must not be included in backup as content state.
- `spiski/` at project root, resolved by `runtime_paths.get_spiski_dir()`.
  - Current known files through `server_routes.SPISKI_FILE_MAP`:
    - `disciplins.txt`
    - `groups.txt`
    - `teachers.txt`
    - `kabinets_Villa.txt`
    - `kabinets_Kolibri.txt`

### 1.2. Existing auth/CSRF behavior

Current CSRF protection is **same-origin Origin check** in `server_routes.csrf_same_origin_check()` for `POST`, `PUT`, `DELETE`, `PATCH`. There is no general synchronizer-token CSRF layer for JSON APIs. Do not introduce a separate token requirement only for backup routes unless the whole app is migrated consistently.

Backup/restore API must use the existing same-origin protection and must be called with same-origin `fetch`. Mutating routes with foreign `Origin` must continue to return `403` with code `CSRF_FAILED`.

### 1.3. Existing roles

Roles used by current code:

- `admin`
- `editor`
- `organizer`
- `viewer`

Backup and restore are available only to `admin`.

## 2. Scope

### 2.1. Входит в задачу

- Удалить/деактивировать старую кнопку и логику `#saveSchedule`.
- Удалить/деактивировать старую standalone-логику `#saveIntermediate`.
- Добавить server backup subsystem.
- Добавить restore subsystem.
- Добавить server-side restore mode.
- Добавить UI в меню для admin:
  - `Создать резервную копию`
  - `Восстановить из резервной копии`
- Создавать и хранить `.zip` backups на сервере.
- Давать admin скачать `.zip`.
- Восстанавливать из server backup.
- Валидировать и сохранять uploaded `.zip`, затем восстанавливать через тот же restore flow.
- Включать в backup persisted state, `schedule.html` и разрешенные `spiski`-файлы.
- Не включать runtime lock, restore status, logs, exports, source Excel/XLSM.
- Блокировать активные вкладки/сессии во время restore через polling/API/middleware.
- Сбрасывать runtime edit lock после restore.
- Обновлять state revisions после restore.
- Добавить backend tests и manual/frontend regression checklist.
- Перегенерировать или вручную очистить `gear_xls/html_output/schedule.html`, чтобы в готовом файле не осталось старого standalone save flow.

### 2.2. Не входит в задачу

- Восстановление старого workflow standalone HTML.
- Backup текущего DOM browser dirty-state.
- Websocket/SSE realtime notifications.
- Backup исходных Excel/XLSM.
- Backup logs, `excel_exports`, PDFs, config/users, passwords, secret key.
- Изменение Excel export logic, кроме того, что export должен не выполняться во время restore.
- Полноценная миграция между разными schema versions. Для неизвестных/будущих версий restore запрещен.

## 3. Источник истины backup-а

Backup сохраняет только persisted server state.

В backup включаются:

```text
gear_xls/html_output/schedule.html
gear_xls/schedule_state/base_schedule.json
gear_xls/schedule_state/individual_lessons.json
spiski/disciplins.txt
spiski/groups.txt
spiski/teachers.txt
spiski/kabinets_Villa.txt
spiski/kabinets_Kolibri.txt
manifest.json
```

Если один из разрешенных `spiski`-файлов отсутствует в текущем проекте, backup должен включить его как пустой файл, чтобы restore был полным снимком известных списков.

Если `base_schedule.json` или `individual_lessons.json` отсутствует, backup должен включить безопасное пустое состояние:

```json
{"published_at": null, "published_by": null, "blocks": []}
```

```json
{"last_modified": null, "blocks": []}
```

Если state JSON существует, но не читается как UTF-8/JSON или не является ожидаемым object-state, backup должен завершиться ошибкой с понятным сообщением. Нельзя silently подменять поврежденный existing state на пустой state.

`schedule.html` обязателен. Если его нет, ручной backup через UI должен завершиться ошибкой с понятным сообщением: расписание еще не создано.

Не включать:

- `gear_xls/schedule_state/lock.json`
- `gear_xls/schedule_state/*.lock`
- `gear_xls/schedule_state/restore_status.json`
- `gear_xls/backups/**`
- `logs/**`, `runtime/**`
- `gear_xls/excel_exports/**`
- `gear_xls/pdfs/**`
- `xlsx_initial/**`, исходные Excel/XLSM
- `gear_xls/config/users.json`, `secret_key.txt`

## 4. Dirty local state

Backup не включает неопубликованные изменения группового расписания из DOM.

Перед созданием backup frontend должен вызвать:

```js
window.SchedGenBaseSyncUI.hasUnpublishedGroupChanges()
```

Если есть dirty group/base changes, показать предупреждение:

```text
Есть неопубликованные изменения группового расписания. Резервная копия сохранит только опубликованное серверное состояние. Сначала опубликуйте расписание или продолжите без этих изменений.
```

Дать три действия:

1. `Опубликовать и создать backup`
   - вызвать `window.SchedGenBaseSyncUI.publishScheduleForNavigation()`;
   - если publish вернул `true`, создать backup;
   - если publish неуспешен, backup не создавать.
2. `Создать backup без неопубликованных изменений`
   - создать backup persisted state без DOM changes.
3. `Отмена`.

Для индивидуальных/nachhilfe/trial занятий отдельный DOM-снимок не нужен: они уже должны сохраняться через server API при изменении.

Перед restore frontend должен предупредить, что любые текущие local dirty changes будут потеряны. Автоматически публиковать перед restore нельзя.

## 5. ZIP backup format

### 5.1. Filename

Формат server filename:

```text
schedgen_backup_YYYYMMDD_HHMMSS_<short-id>.zip
```

Где `<short-id>` — 8 hex chars из `uuid.uuid4().hex[:8]` или аналогичный cryptographically safe/random id.

Для uploaded backup имя файла пользователя не использовать как server filename. Uploaded ZIP после валидации сохранять под новым безопасным server filename указанного формата. Исходное имя можно сохранить только как plain text field `uploaded_original_filename` в manifest/metadata, с escaping в UI.

`backup_id` в API — filename без `.zip`. Любой `backup_id`, не соответствующий regex ниже, должен отвергаться до доступа к файловой системе:

```regex
^schedgen_backup_\d{8}_\d{6}_[0-9a-f]{8}$
```

### 5.2. Archive structure

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

Не хранить абсолютные пути и project-root-relative пути внутри ZIP.

### 5.3. `manifest.json`

Пример:

```json
{
  "schema": "schedgen.web_editor_backup",
  "schema_version": 1,
  "backup_kind": "manual",
  "created_at": "2026-05-11T14:30:00Z",
  "created_by": "admin_login",
  "created_by_display_name": "Admin",
  "comment": "optional user comment",
  "project_root_id": "0123456789abcdef",
  "app": "Kolibri SchedGen",
  "source": "web_editor_persisted_state",
  "dirty_dom_included": false,
  "base_revision": "2026-05-01T19:51:03.123456",
  "individual_revision": "2026-05-01T19:49:42.123456",
  "includes": {
    "schedule_html": true,
    "base_schedule": true,
    "individual_lessons": true,
    "spiski": true,
    "lock_state": false,
    "restore_status": false,
    "source_excel": false
  },
  "spiski_files": [
    "disciplins.txt",
    "groups.txt",
    "teachers.txt",
    "kabinets_Villa.txt",
    "kabinets_Kolibri.txt"
  ],
  "files": [
    {
      "path": "state/base_schedule.json",
      "sha256": "...",
      "size": 41051
    }
  ]
}
```

Allowed `backup_kind` values:

- `manual` — admin created from UI/API;
- `safety` — automatically created immediately before restore;
- `uploaded` — uploaded by admin and stored after validation.

`created_at` in manifest and restore status should be UTC with `Z` suffix. Existing state revisions in `base_schedule.json.published_at` and `individual_lessons.json.last_modified` may keep the project’s current format `datetime.utcnow().isoformat()` without `Z`; do not break existing revision comparisons.

### 5.4. Comment validation

`comment`:

- optional;
- max length 500 characters after trim;
- stored as plain text;
- never rendered as raw HTML;
- if too long, API returns `400` with code `COMMENT_TOO_LONG`.

## 6. Server storage

Add new runtime data directory:

```text
gear_xls/backups/
```

Add to `.gitignore` at project root if not already ignored:

```text
gear_xls/backups/
gear_xls/schedule_state/restore_status.json
```

If `.gitignore` does not exist in the repository, create it.

Add path helpers to `gear_xls/runtime_paths.py`:

```python
def get_backup_dir(project_root: str | None = None) -> str:
    return os.path.join(get_gear_xls_dir(project_root), "backups")


def get_restore_status_path(project_root: str | None = None) -> str:
    return os.path.join(get_schedule_state_dir(project_root), "restore_status.json")
```

`gear_xls/backups/` must be created lazily by backup/list/upload/restore code.

## 7. Backend modules

Add:

```text
gear_xls/backup_manager.py
gear_xls/restore_manager.py
```

Можно объединить backend в один файл только если код остается читаемым. Предпочтительно два файла.

### 7.1. `backup_manager.py`

Responsibilities:

- constants: schema, version, filename regex, allowed archive paths, allowed spiski filenames, size limits;
- `create_backup(created_by, created_by_display_name, comment='', backup_kind='manual', ...)`;
- `list_backups()`;
- `get_backup_path(backup_id)` with strict id validation;
- `read_manifest_from_zip(path)`;
- `validate_backup_zip(path, *, deep=True)`;
- checksum calculation;
- safe ZIP entry validation;
- storing uploaded ZIP after validation under safe generated filename;
- no dependency on browser DOM.

### 7.2. `restore_manager.py`

Responsibilities:

- restore mode state read/write;
- stale restore detection;
- restore mutex/process-local lock to prevent concurrent restore in same process;
- `restore_backup(backup_id, login, display_name, allow_foreign_project=False)`;
- safety backup creation;
- domain validation of parsed state;
- staged writes and rollback;
- reset edit lock after successful restore;
- update restore generation after successful restore;
- recovery-required mode if partial restore and rollback both fail.

## 8. ZIP validation and security

Validation must happen before any extraction/write to target project paths.

Use Python `zipfile` and inspect `ZipInfo`; do not trust MIME type or user filename.

### 8.1. Hard limits

Use constants in `backup_manager.py`:

```python
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ZIP_FILES = 30
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_SINGLE_FILE_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_SCHEDULE_HTML_BYTES = 25 * 1024 * 1024
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_SPISKI_FILE_BYTES = 1 * 1024 * 1024
```

Exact values can be lowered if current project files are much smaller, but they must be explicit and tested.

### 8.2. Reject ZIP when

- not a ZIP by content;
- empty ZIP;
- encrypted entry (`ZipInfo.flag_bits & 0x1`);
- duplicate entry names;
- more than `MAX_ZIP_FILES` entries;
- cumulative uncompressed size exceeds `MAX_UNCOMPRESSED_BYTES`;
- any single file exceeds its specific limit;
- path contains backslash `\`;
- path is absolute;
- path contains `..` segments;
- path contains Windows drive prefix like `C:`;
- entry is symlink or hardlink according to `ZipInfo.external_attr`/Unix file type bits;
- directory entries are present outside expected structure;
- unexpected file path exists;
- required file missing;
- `manifest.json` invalid JSON;
- unknown `schema` or `schema_version`;
- checksum mismatch;
- state JSON invalid;
- schedule HTML invalid by section 8.5;
- `spiski` contains files outside allowed whitelist.

### 8.3. Required archive paths

Required exactly:

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

Extra files are rejected for schema version 1.

### 8.4. Manifest checksum validation

For every entry in `manifest.files`:

- `path` must be one of expected file paths except `manifest.json`;
- `sha256` must match actual bytes;
- `size` must match actual uncompressed size.

Every expected non-manifest file must have exactly one entry in `manifest.files`.

### 8.5. `schedule.html` validation

For `html/schedule.html`:

- decode as UTF-8;
- non-empty;
- contains `<html` and at least one `schedule-container` marker (`class="...schedule-container..."` in HTML or `.schedule-container` in generated CSS/JS);
- contains `#menuDropdown` or `id="menuDropdown"`;
- must **not** contain active old standalone save artifacts:
  - `id="saveSchedule"` or `id='saveSchedule'`;
  - `id="saveIntermediate"` or `id='saveIntermediate'`;
  - `/save_intermediate`;
  - `final_schedule.html`;
  - `intermediate_schedule.html`;
  - `body.static-schedule` or `static-schedule` logic from old final-save flow.

This intentionally rejects old standalone or pre-migration schedule HTML. Backup from old standalone HTML is out of scope.

### 8.6. Project mismatch

If `manifest.project_root_id != get_project_root_id()`, upload/list may still show the backup, but restore must require explicit additional confirmation.

API behavior:

- first restore attempt without `allow_foreign_project=true` returns `409`:

```json
{
  "ok": false,
  "code": "PROJECT_ROOT_MISMATCH",
  "error": "Backup was created for another project root",
  "backup_project_root_id": "...",
  "current_project_root_id": "..."
}
```

- UI then shows a second warning and sends `allow_foreign_project: true` only after admin confirmation.

Unknown/future `schema_version` is not a project mismatch and must be rejected with `400`/`422` code `UNSUPPORTED_BACKUP_SCHEMA_VERSION`.

## 9. Domain validation before restore

Domain validation is required after ZIP/checksum validation and before writing any project file.

### 9.1. Time validation

Use strict time format:

```regex
^(?:[01]\d|2[0-3]):[0-5]\d$
```

`end_time` must be greater than `start_time` in minutes.

### 9.2. `base_schedule.json`

Valid object:

```json
{
  "published_at": "... or null",
  "published_by": "... or null",
  "blocks": []
}
```

Validation:

- top-level JSON is object;
- `blocks` is list;
- each block is object;
- required non-empty string fields:
  - `building`
  - `day`
  - `room`
  - `subject`
  - `start_time`
  - `end_time`
  - `lesson_type`
- `lesson_type` must be exactly `group`;
- `day` must be one of `Mo`, `Di`, `Mi`, `Do`, `Fr`, `Sa`;
- time format strict and `end_time > start_time`;
- optional `teacher`, `students`, `color`, `room_display` are strings if present;
- optional `start_row` int >= 0;
- optional `row_span` int >= 1;
- reject blocks with absurd text fields over 1000 chars.

If base has blocks but `published_at` is null, restore must set `published_at` to the new restore revision. If base has no blocks and `published_at` is null, keep `published_at: null` to preserve “no published base” state.

### 9.3. `individual_lessons.json`

Valid object:

```json
{
  "last_modified": "... or null",
  "blocks": []
}
```

Validation:

- top-level JSON is object;
- `blocks` is list;
- each block is object;
- required non-empty string fields:
  - `id`
  - `building`
  - `day`
  - `room`
  - `subject`
  - `start_time`
  - `end_time`
  - `lesson_type`
- `id` values must be unique;
- `lesson_type` must be one of `individual`, `nachhilfe`, `trial`;
- `day` must be one of `Mo`, `Di`, `Mi`, `Do`, `Fr`, `Sa`;
- time format strict and `end_time > start_time`;
- optional `teacher`, `students`, `color`, `room_display` are strings if present;
- optional `start_row` int >= 0;
- optional `row_span` int >= 1;
- for `trial`:
  - `trial_dates` must be a non-empty list;
  - each date must be valid `YYYY-MM-DD`;
  - each date weekday must match block `day`, using the same mapping as `state_manager._DAY_TO_WEEKDAY`;
  - duplicate dates should be normalized out or rejected; prefer normalize/sort if already valid.
- for non-trial blocks:
  - remove `trial_dates` during normalization before writing, or reject if keeping it would create stale data. Prefer remove, matching current `state_manager._validate_block()` behavior.

Do not rely only on current private `_validate_block()`, because it does not fully validate time format/end > start. Reuse constants/helper logic where possible, but add missing restore validation explicitly.

### 9.4. `spiski` files

For each allowed `spiski/*.txt`:

- UTF-8 decodable;
- text file only;
- each non-empty line max 200 chars;
- no NUL bytes;
- no HTML/script special handling needed at storage level, but UI must render escaped;
- preserve file content order from backup, or normalize by stripping trailing spaces and ending with a single newline. Prefer preserve except trimming `\r\n` to `\n`.

## 10. Restore mode

Add file:

```text
gear_xls/schedule_state/restore_status.json
```

This is runtime state and must not be included in backup.

Schema:

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

Behavior:

- Before restore writes begin, set `active=true`, `started_at`, `started_by`, `message`.
- During normal successful restore, set `active=false`, increment `generation`, set `last_completed_at`, `last_completed_by`, `last_restored_from`, `recovery_required=false`.
- If validation/pre-write failure happens, set `active=false` and do not increment generation.
- If partial write happened and auto-rollback succeeded, set `active=false`, increment generation, and return an error describing that rollback was applied.
- If partial write happened and auto-rollback failed, set:
  - `active=true`
  - `recovery_required=true`
  - `recovery_message` with clear admin-facing text
  - `safety_backup_id`
  - keep mutating APIs blocked until admin recovery.

Stale restore mode:

- Define `RESTORE_STALE_AFTER_SECONDS = 600`.
- If `active=true` older than threshold and `recovery_required=false`, admin may clear stale mode via explicit endpoint/action.
- Do not auto-clear `recovery_required=true`.

Add admin endpoint for stale/recovery clear:

```text
POST /api/restore/status/clear
```

Payload:

```json
{"confirm": true}
```

Rules:

- role `admin` only;
- may clear stale non-recovery restore mode;
- may clear recovery mode only with explicit confirm and after UI warning that state may be inconsistent;
- log the action.

## 11. Server middleware during restore

Add `before_request` middleware in `server_routes.py` after auth/session helpers are available.

When restore status is active:

### 11.1. Always allow

- `GET /api/restore/status`
- `GET /api/status`
- static assets: `/static/*`, `/js_modules/*`
- `/login`, `/logout`, `/health`
- `GET /api/backups` for admin, if useful for recovery UI
- `GET /api/backups/<id>/download` for admin, if useful for safety backup download
- the in-progress restore route for the restore-admin only:
  - `POST /api/backups/<id>/restore`

### 11.2. Block for everyone else

Mutating and schedule-sensitive routes must return JSON:

```json
{
  "ok": false,
  "error": "Restore in progress",
  "code": "RESTORE_IN_PROGRESS",
  "message": "Администратор выполняет восстановление базы расписания. Работа временно заблокирована. Вы сможете зайти после завершения восстановления.",
  "restore_generation": 12
}
```

Status code: `423 Locked` preferred. `409 Conflict` acceptable if easier, but use one code consistently and test it.

Block at least:

- `/api/lock/status`
- `/api/lock/acquire`
- `/api/lock/release`
- `/api/lock/heartbeat`
- `DELETE /api/lock`
- `/api/schedule`
- `/api/individual_lessons`
- `/api/schedule/publish`
- `/api/blocks*`
- `/api/columns`
- `/api/spiski/*`, including `/api/spiski/add`
- `/api/backups` creation/upload while restore active
- `/export_to_excel`

For HTML `/schedule` during active restore:

- do not serve the editable schedule page to any user while restore is active;
- for restore-admin/admin, return a minimal restore status/recovery page; for non-admin users, return a blocking page/message;
- the page text must include:

```text
Администратор выполняет восстановление базы расписания. Работа временно заблокирована. Вы сможете зайти после завершения восстановления.
```

If recovery mode is active, `/schedule` should show admin recovery warning for admin and blocking message for non-admin.

### 11.3. `/api/status` changes

Current `/api/status` returns lock and revisions. Extend it with restore fields:

```json
{
  "lock": {...},
  "base_revision": "...",
  "individual_revision": "...",
  "base_updated": false,
  "restore": {
    "active": false,
    "generation": 12,
    "last_completed_at": "...",
    "recovery_required": false,
    "message": null
  }
}
```

## 12. Atomic restore algorithm

Restore must be as atomic as practical across multiple files.

### 12.1. High-level order

1. Route checks role `admin`.
2. Route checks payload `confirm === true`.
3. Route checks active edit lock belongs to current admin.
4. Validate `backup_id` and backup exists.
5. Validate ZIP structure/checksums/security.
6. Validate project root id; if mismatch and no `allow_foreign_project`, return `409` before restore mode.
7. Domain-validate state JSON and schedule HTML.
8. Acquire process-local restore mutex.
9. Set restore mode `active=true`.
10. Create safety backup of current state with `backup_kind='safety'`.
11. Prepare normalized payloads in memory/staging:
    - base JSON with restore revision rules;
    - individual JSON with `last_modified` set to restore revision;
    - schedule HTML bytes;
    - spiski text bytes.
12. Write files through temp files in same target directories, then `os.replace`:
    - `gear_xls/schedule_state/base_schedule.json`
    - `gear_xls/schedule_state/individual_lessons.json`
    - allowed `spiski/*.txt`
    - `gear_xls/html_output/schedule.html`
13. Reset edit lock to unlocked state with reason `restore_completed`.
14. Set restore mode complete: `active=false`, increment `generation`, set completion metadata.
15. Return JSON success with safety backup link and new revisions.

### 12.2. Restore revision rules

Use one `restore_revision` timestamp for base and individual where applicable.

For `base_schedule.json`:

- if restored base has blocks or had non-null `published_at`, set:
  - `published_at = restore_revision`
  - `published_by = current admin login`
- if restored base has no blocks and `published_at` is null, preserve:
  - `published_at = null`
  - `published_by = null`

For `individual_lessons.json`:

- always set `last_modified = restore_revision`.

Response must include:

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

### 12.3. Rollback rules

If error occurs before any target file replacement:

- do not modify state;
- clear restore mode;
- keep safety backup;
- return error.

If error occurs after one or more replacements:

1. Attempt automatic rollback from safety backup using a lower-level restore function that does **not** create another safety backup and does not recurse indefinitely.
2. If rollback succeeds:
   - clear restore mode;
   - increment generation because state changed back;
   - return error with code `RESTORE_ROLLED_BACK` and safety backup id.
3. If rollback fails:
   - leave restore mode active with `recovery_required=true`;
   - block all schedule editing/export APIs;
   - return critical error with code `RESTORE_PARTIAL_FAILURE` and safety backup id;
   - log full traceback.

### 12.4. File locking

Current base/individual managers have private lock helpers. Implementation may either:

- add public replace helpers to `base_schedule_manager.py` and `state_manager.py`, or
- implement restore-specific file locks in `restore_manager.py`.

Do not write JSON without temp file + `os.replace`.

For Windows compatibility, do not rely on atomic directory replace for `spiski`. Write each allowed text file via temp file + `os.replace`; rollback handles cross-file atomicity.

### 12.5. Lock reset

Add a function to `lock_manager.py`, for example:

```python
def clear_for_restore(restored_by_login: str) -> dict:
    ...
```

Expected effect:

- `holder = None`
- increment `version`
- `last_holder` set to previous holder
- `released_at` set to now
- `released_by = restored_by_login`
- `release_reason = "restore_completed"`

Do not restore `lock.json` from backup.

## 13. API

All backup/restore API routes require login. Backup/restore mutation routes require role `admin`.

Add backup routes to `JSON_AUTH_PATHS` or make `login_required` return JSON for `/api/backups*` and `/api/restore*` consistently.

### 13.1. `GET /api/backups`

Role: `admin`.

Returns server backups sorted newest first:

```json
{
  "ok": true,
  "backups": [
    {
      "id": "schedgen_backup_20260511_143000_ab12cd34",
      "filename": "schedgen_backup_20260511_143000_ab12cd34.zip",
      "backup_kind": "manual",
      "created_at": "...",
      "created_by": "...",
      "created_by_display_name": "...",
      "comment": "...",
      "base_revision": "...",
      "individual_revision": "...",
      "project_root_id": "...",
      "project_root_matches": true,
      "size": 123456,
      "valid": true,
      "invalid_reason": null,
      "download_url": "/api/backups/<id>/download"
    }
  ]
}
```

If a ZIP in `gear_xls/backups/` is damaged/invalid, show it as `valid:false` with `invalid_reason`, but do not allow restore.

### 13.2. `POST /api/backups`

Role: `admin`.

Payload:

```json
{
  "comment": "optional",
  "download": false
}
```

No edit lock required for MVP because backup is persisted state only.

If restore mode is active, return `RESTORE_IN_PROGRESS`.

Response:

```json
{
  "ok": true,
  "backup": {
    "id": "...",
    "filename": "...zip",
    "backup_kind": "manual",
    "download_url": "/api/backups/<id>/download"
  }
}
```

If `download=true`, frontend opens `download_url` after successful response.

### 13.3. `GET /api/backups/<backup_id>/download`

Role: `admin`.

- Validate `backup_id` regex.
- Return ZIP as attachment.
- If file missing after list, return `404` code `BACKUP_NOT_FOUND`.

### 13.4. `POST /api/backups/upload`

Role: `admin`.

Multipart form field:

```text
file
```

Behavior:

1. Check upload size.
2. Validate ZIP deeply.
3. Store under new safe server filename in `gear_xls/backups/`.
4. Mark/list as `backup_kind='uploaded'`. If original manifest says another kind, do not trust it blindly for UI; either override in stored manifest or return metadata separately.
5. Return stored backup object.

Response:

```json
{
  "ok": true,
  "backup": {
    "id": "...",
    "filename": "...zip",
    "backup_kind": "uploaded",
    "project_root_matches": false,
    "download_url": "/api/backups/<id>/download"
  },
  "warnings": ["PROJECT_ROOT_MISMATCH"]
}
```

Upload does not restore automatically.

### 13.5. `POST /api/backups/<backup_id>/restore`

Role: `admin`.

Requires active edit lock held by current admin.

Payload:

```json
{
  "confirm": true,
  "allow_foreign_project": false
}
```

Errors:

- no lock: `403`, code `NO_LOCK`;
- not admin: `403`, code `FORBIDDEN`;
- restore already active: `423` or `409`, code `RESTORE_IN_PROGRESS`;
- invalid/missing backup: `400`/`404`;
- project mismatch without allow: `409`, code `PROJECT_ROOT_MISMATCH`.

Success response: see section 12.2.

After success, frontend must hard reload `/schedule`.

### 13.6. `GET /api/restore/status`

Roles: all authenticated users.

Response:

```json
{
  "ok": true,
  "restore_in_progress": false,
  "active": false,
  "started_at": null,
  "started_by": null,
  "message": null,
  "generation": 13,
  "last_completed_at": "...",
  "recovery_required": false,
  "recovery_message": null
}
```

Unauthenticated request should return JSON `401` for API calls.

### 13.7. Deprecated `/save_intermediate`

Frontend must not call `/save_intermediate`.

Backend options:

Preferred: remove route.

Acceptable for one release: keep route but return:

```json
{
  "success": false,
  "reason": "deprecated",
  "message": "Use /api/backups instead"
}
```

with status `410 Gone` or `400`. It must not open Tk file dialog.

## 14. Frontend UX

### 14.1. Старые controls

Remove from active generated UI:

- `#saveSchedule`
- `#saveIntermediate`

Remove old standalone handlers from active JS.

`#exportToExcel` remains admin-only as before.

### 14.2. Menu UI

Preferred and required for this implementation: add backup/restore actions to `#menuDropdown` for admin.

Menu items:

```text
Создать резервную копию
Восстановить из резервной копии
```

Implementation may either:

- generate menu item placeholders in `html_structure_generator.py`, and bind them in `backup_ui.js`; or
- dynamically insert menu items from `backup_ui.js` when `window.USER_ROLE === 'admin'`.

Because existing `schedule.html` has inline JS and old HTML, final deliverable must also ensure `html_output/schedule.html` contains these menu items or can receive them dynamically and contains no old save controls.

For non-admin roles, backup/restore items must not be visible and API must reject access.

### 14.3. `backup_ui.js`

Add:

```text
gear_xls/static/backup_ui.js
```

Connect in `/schedule` after existing auth/lock/base/individual scripts, preferably after `schedule_search_ui.js`:

```html
<script src="/static/backup_ui.js"></script>
```

`backup_ui.js` must:

- initialize only when `window.SchedGenAuthUI` exists;
- check `window.USER_ROLE === 'admin'` for admin UI;
- add/bind menu items;
- show modal for create backup:
  - optional comment;
  - checkbox `Скачать ZIP после создания`;
  - dirty base warning flow from section 4;
- call `POST /api/backups`;
- open `download_url` if requested;
- show restore modal:
  - list server backups;
  - show date, author, comment, kind, size, revisions, valid/invalid;
  - upload ZIP file;
  - warning that current state will be replaced;
  - checkbox `Я понимаю, что текущее состояние будет заменено`;
  - restore button disabled until valid backup selected and checkbox checked;
- require active edit mode before restore:
  - check `window.SchedGenAuthUI.isEditMode()`;
  - if false, show message `Для восстановления сначала нажмите «Начать редактирование».`;
- handle project-root mismatch with second confirm;
- show full-screen overlay during restore;
- on success: show message, then hard reload `window.location.href = '/schedule'` or `window.location.reload()`;
- poll `/api/restore/status` for all authenticated users;
- show blocking overlay when `restore_in_progress=true`;
- detect `generation` changes and hard reload old pages after completed restore;
- escape all user-controlled text.

### 14.4. Restore overlay text

Use exact user-facing message:

```text
Администратор выполняет восстановление базы расписания. Работа временно заблокирована. Вы сможете зайти после завершения восстановления.
```

Behavior for non-restore users when active:

- close open dialogs via `window.SchedGenLockUI.closeOpenDialogs()` if available;
- disable pointer events/edit controls;
- set local edit mode false through `window.SchedGenAuthUI.setEditMode(false)` if available;
- show fullscreen overlay;
- do not allow publish/edit/export actions.

### 14.5. Updating `lock_ui.js` for restore errors

Existing `lock_ui.js` does not handle `RESTORE_IN_PROGRESS`. Update its API handling so when any lock/status request receives JSON code `RESTORE_IN_PROGRESS`, it:

- closes dialogs;
- stops heartbeat/polling or at least clears local `lockVersion` and edit mode;
- invokes `window.SchedGenBackupUI.handleRestoreInProgress(data)` if available;
- does not keep trying to edit with old lock.

Expose a helper if useful:

```js
window.SchedGenLockUI.clearLocalLockStateForRestore = function () { ... }
```

### 14.6. No websocket guarantee

Without websocket/SSE, immediate closing of all tabs is not guaranteed. Required guarantee:

- all mutating/schedule-sensitive API calls are blocked server-side during active restore;
- active tabs discover restore through polling or failed API call;
- after restore completion, tabs with old `generation` hard reload before further editing;
- stale edit locks are reset and old lock holders cannot mutate state.

## 15. Required changes in existing files

### 15.1. `gear_xls/generators/html_structure_generator.py`

- Remove buttons:
  - `<button id="saveIntermediate">...`
  - `<button id="saveSchedule">...`
- Add backup/restore menu placeholders or let `backup_ui.js` insert them dynamically.
- Keep `#exportToExcel`.
- Keep hidden `#csrf_token` only if other code still uses it for export; do not add backup dependency on it.

### 15.2. `gear_xls/html_styles.py`

Remove old CSS selectors:

- `#saveIntermediate`
- `#saveSchedule`
- `body.static-schedule`
- mobile selectors referencing old save buttons.

Add styles for backup modal/restore overlay if not implemented fully in `backup_ui.js` via injected style.

### 15.3. `gear_xls/js_modules/save_export.js`

Preferred: remove all old save logic and either delete this module from `html_javascript.py` or leave only a no-op:

```js
function initSaveExport() {}
```

There must be no code that:

- binds `#saveSchedule`;
- binds `#saveIntermediate`;
- downloads `final_schedule.html`;
- downloads `intermediate_schedule.html`;
- calls `/save_intermediate`;
- adds `body.static-schedule`.

### 15.4. `gear_xls/js_modules/app_initialization.js`

- If `save_export.js` is removed from inline modules, guard the call:

```js
if (typeof initSaveExport === 'function') {
    initSaveExport();
}
```

- Remove or simplify `body.static-schedule` branches because static final-save flow is gone.
- Ensure app initialization still works when `initSaveExport` no longer exists.

### 15.5. `gear_xls/html_javascript.py`

- If `save_export.js` is no longer needed, remove `save_export` from `base_module_names` and from template injection.
- If kept as no-op, ensure it contains no old flow.

### 15.6. `gear_xls/static/auth_ui.js`

- Remove `#saveIntermediate` and `#saveSchedule` from `HIDE_SELECTORS` and injected CSS.
- Add selectors for backup/restore menu items only if they are generated statically. If inserted dynamically by `backup_ui.js`, keep visibility logic inside `backup_ui.js`.
- Keep `#exportToExcel` admin-only behavior unchanged.

### 15.7. `gear_xls/server_routes.py`

- Import `backup_manager` and `restore_manager`.
- Add routes from section 13.
- Extend `JSON_AUTH_PATHS` for `/api/backups`, `/api/restore/status`, and prefix handling for `/api/backups/` and `/api/restore/`.
- Add restore middleware from section 11.
- Extend `/api/status` with restore status.
- Connect `/static/backup_ui.js` in `/schedule`.
- Remove or deprecate `/save_intermediate`; it must not open Tk.
- Do not add CORS wildcard for backup routes.

### 15.8. `gear_xls/runtime_paths.py`

Add:

- `get_backup_dir()`
- `get_restore_status_path()`

### 15.9. `gear_xls/lock_manager.py`

Add restore-specific lock clear helper.

### 15.10. `gear_xls/html_output/schedule.html`

Because this file contains inline JS modules from the old architecture, updating source modules is not enough.

Final file must not contain:

```text
saveSchedule
saveIntermediate
/save_intermediate
final_schedule.html
intermediate_schedule.html
body.static-schedule
```

Regenerate through the normal HTML pipeline if possible. If normal regeneration requires unavailable Excel input in the Codex environment, patch `html_output/schedule.html` consistently so shipped/current server HTML no longer has old save controls and old inline handlers.

## 16. Backend tests

The archive currently does not include a test suite. Add pytest tests.

If pytest is not available in dependencies, add a development/test dependency. Acceptable options:

- add `pytest>=8.0` to `requirements.txt`; or
- add a small `requirements-dev.txt` with `pytest>=8.0` and document it.

Recommended test file:

```text
tests/test_backup_restore.py
```

Use temporary project root fixtures. Because `runtime_paths.assert_valid_project_layout()` expects root layout, fixture must create minimal required dirs/files:

```text
<tmp>/gear_xls/server_routes.py or copied package under test as appropriate
<tmp>/xlsx_initial/
<tmp>/visualiser/
<tmp>/gui.py
```

Set `SCHEDGEN_PROJECT_ROOT` before importing modules under test when needed.

Minimum backend tests:

1. `create_backup` creates ZIP with expected paths and manifest.
2. Manifest checksums and sizes match actual ZIP entries.
3. Missing `schedule.html` causes clear backup error.
4. Missing state JSON is backed up as empty default state.
5. Missing allowed `spiski` file is backed up as empty file.
6. `list_backups` returns valid metadata and marks corrupted ZIP as invalid.
7. Download validates `backup_id` and rejects path traversal ids.
8. Upload rejects non-ZIP.
9. Upload rejects path traversal ZIP entry.
10. Upload rejects symlink ZIP entry.
11. Upload rejects duplicate ZIP entries.
12. Upload rejects checksum mismatch.
13. Upload rejects unknown schema/schema_version.
14. Upload rejects extra unexpected file.
15. Upload rejects old `schedule.html` containing `saveSchedule` or `/save_intermediate`.
16. Restore requires role `admin`.
17. Restore requires active lock held by current admin.
18. Restore rejects project mismatch without `allow_foreign_project`.
19. Restore creates safety backup.
20. Restore writes base and individual state and updates revisions according to section 12.2.
21. Restore does not restore `lock.json` from backup and clears current lock with reason `restore_completed`.
22. Restore restores all allowed `spiski` files.
23. Restore restores `schedule.html`.
24. Restore middleware blocks mutating APIs for other users while active.
25. Restore mode `generation` increments after success.
26. Stale restore mode can be cleared by admin.
27. Partial failure path attempts rollback. This can be tested by monkeypatching one write to fail after a previous write.
28. Rollback failure sets `recovery_required=true`.

Manual/frontend regression checklist:

- admin sees backup/restore menu items;
- editor/organizer/viewer do not see backup/restore items;
- `#saveSchedule` no longer appears;
- `#saveIntermediate` no longer appears;
- old standalone save flow cannot be triggered;
- dirty base warning appears before backup;
- `Опубликовать и создать backup` calls publish first;
- backup with download downloads `.zip`;
- restore without edit lock is blocked with clear message;
- restore from server backup works and hard reloads `/schedule`;
- uploaded backup validate-store-restore flow works;
- project mismatch asks second confirmation;
- another open user tab receives restore overlay and cannot edit/export;
- after restore, stale tab reloads or cannot acquire/edit against old DOM;
- export to Excel still works when no restore active;
- publish base schedule still works;
- individual lesson CRUD still works;
- edit lock acquire/release/heartbeat still works after restore;
- login/logout unaffected.

## 17. Edge cases to handle

### 17.1. Backup creation

- `gear_xls/backups/` missing;
- no write permission;
- disk full;
- `schedule.html` missing;
- state JSON missing;
- state JSON invalid at backup time;
- `spiski` files missing;
- comment too long;
- comment contains HTML/script;
- backup requested while restore active;
- two admins create backup at the same time;
- filename collision.

### 17.2. Server backup list/download

- damaged ZIP in backup dir;
- ZIP with invalid manifest;
- backup deleted between list and restore/download;
- unsafe `backup_id`;
- `project_root_id` mismatch;
- safety backups shown with `backup_kind='safety'`.

### 17.3. Upload

- no file field;
- empty file;
- non-ZIP;
- encrypted ZIP;
- ZIP bomb size indicators;
- too many files;
- absolute path entry;
- `../` path traversal;
- backslash path traversal;
- Windows drive prefix;
- symlink/hardlink entry;
- duplicate entries;
- missing manifest;
- unknown schema;
- checksum mismatch;
- invalid JSON;
- invalid domain state;
- old schedule HTML with standalone save artifacts;
- source project mismatch.

### 17.4. Restore

- non-admin restore attempt;
- admin restore without active lock;
- lock held by another user;
- restore already active;
- selected backup deleted after list;
- selected backup corrupted after list;
- active users continue sending API requests;
- restore-admin loses browser session during restore;
- server process crashes during restore;
- domain JSON valid syntactically but invalid semantically;
- schedule HTML missing/invalid;
- Windows file locking prevents `os.replace`;
- disk full during write;
- partial write failure;
- rollback failure;
- stale restore mode after crash;
- recovery mode after failed rollback;
- old tabs with stale DOM after successful restore.

## 18. Acceptance criteria

Implementation is accepted when all are true:

- `#saveSchedule` absent from generated/current UI and active handlers.
- `#saveIntermediate` absent from generated/current UI and active handlers.
- No active code calls `/save_intermediate`.
- `/save_intermediate`, if still present, returns deprecation and never opens Tk dialog.
- `html_output/schedule.html` no longer contains old standalone save artifacts listed in section 15.10.
- Admin can create server backup.
- Admin can download backup ZIP.
- Backup ZIP contains exactly schema v1 expected files and valid manifest checksums.
- Backup includes persisted base, individual, schedule HTML, and allowed `spiski` files.
- Backup excludes lock, restore status, logs, exports, source Excel/XLSM, config secrets/users.
- Admin can restore from server backup.
- Admin can upload ZIP, validate/store it, and restore from stored uploaded backup.
- Restore requires active edit lock of current admin.
- Restore creates safety backup before target writes.
- Restore updates revisions according to section 12.2.
- Restore clears runtime edit lock with restore reason.
- Restore blocks mutating/schedule-sensitive APIs for others while active.
- Active/stale tabs see restore overlay and cannot continue editing old state.
- After successful restore, `/schedule` shows restored state after hard reload.
- Dangerous/invalid ZIP files are rejected.
- Project mismatch requires second confirmation.
- Partial failure attempts rollback; rollback failure leaves recovery mode active.
- Backend tests pass.
- Existing publish, individual CRUD, export, login/logout, lock acquire/release still work.

## 19. Recommended implementation order

1. Add path helpers in `runtime_paths.py` and `.gitignore` entries.
2. Implement `backup_manager.py` constants, ZIP writer, manifest/checksum helpers.
3. Implement backup validation, including schedule HTML legacy-artifact rejection.
4. Add `POST /api/backups`, `GET /api/backups`, download route.
5. Add tests for create/list/download/invalid ZIP.
6. Remove/deprecate old `/save_intermediate` backend behavior.
7. Remove old save buttons/handlers/styles from generator/source JS; guard/remove `initSaveExport`; update `auth_ui.js`.
8. Ensure `html_output/schedule.html` has no old standalone artifacts.
9. Implement restore status manager and `/api/restore/status`.
10. Add restore middleware and extend `/api/status`.
11. Implement `restore_manager.py` validation, safety backup, staged writes, lock clear, generation update.
12. Add server backup restore route and tests.
13. Add upload route and tests.
14. Add `static/backup_ui.js` and connect it in `/schedule`.
15. Update `lock_ui.js` to react to `RESTORE_IN_PROGRESS`.
16. Run backend tests and manual regression checklist.

## 20. Grep checks for final verification

Run from repo root:

```bash
rg -n "saveSchedule|saveIntermediate|/save_intermediate|final_schedule\.html|intermediate_schedule\.html|body\.static-schedule" gear_xls
```

Expected:

- no matches in active source/generated UI;
- acceptable only in comments/tests that explicitly assert old artifacts are rejected.

Also verify backup routes:

```bash
rg -n "api/backups|api/restore/status|backup_ui|restore_status|get_backup_dir|get_restore_status_path" gear_xls
```

Expected:

- new backend routes/helpers present;
- `/static/backup_ui.js` connected in `/schedule`.
