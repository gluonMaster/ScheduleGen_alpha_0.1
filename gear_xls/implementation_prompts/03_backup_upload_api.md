# Prompt 03: upload ZIP backup API

Ты работаешь в репозитории `SchedGen_PreRelease`. Это третья сессия из серии по backup/restore веб-редактора.

Ожидается, что после предыдущей сессии уже есть:

- `gear_xls/backup_manager.py`;
- `gear_xls/backups/` в `.gitignore`;
- `GET /api/backups`;
- `POST /api/backups`;
- `GET /api/backups/<backup_id>/download`;
- backend tests для create/list/download/validation.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `5.1. Filename`
- `5.3. manifest.json`
- `8. ZIP validation and security`
- `8.6. Project mismatch`
- `13.4. POST /api/backups/upload`
- `16. Backend tests`
- `17.3. Upload`

## Цель

Добавить server-side upload ZIP backup flow:

1. admin загружает `.zip`;
2. сервер глубоко валидирует архив;
3. сервер сохраняет его под безопасным новым именем в `gear_xls/backups/`;
4. uploaded backup появляется в `GET /api/backups`;
5. restore в будущей сессии будет работать с uploaded backup через тот же stored backup flow.

Frontend в этой сессии не реализуй.

## Обязательные требования

1. Добавить в `backup_manager.py` upload/store helper, например:

   ```python
   def store_uploaded_backup(file_stream, original_filename, uploaded_by, uploaded_by_display_name) -> dict:
       ...
   ```

   Конкретная сигнатура может отличаться, но responsibilities должны быть покрыты.

2. Uploaded filename:

   - не использовать filename пользователя как server filename;
   - новый server filename должен соответствовать:

     ```regex
     ^schedgen_backup_\d{8}_\d{6}_[0-9a-f]{8}\.zip$
     ```

   - исходное имя можно хранить только как escaped/plain metadata field `uploaded_original_filename`.

3. Upload size:

   - использовать explicit `MAX_UPLOAD_BYTES`;
   - reject empty/missing file;
   - reject over-limit upload before storing final ZIP.

4. ZIP validation:

   - use existing `validate_backup_zip(..., deep=True)`;
   - reject all security cases from section 8:
     - non-ZIP;
     - encrypted entries;
     - duplicate entry names;
     - too many files;
     - ZIP bomb size indicators;
     - absolute paths;
     - `../`;
     - backslashes;
     - Windows drive prefixes;
     - symlink/hardlink entries;
     - unexpected paths;
     - missing required files;
     - invalid manifest;
     - unknown schema/version;
     - checksum mismatch;
     - invalid schedule HTML;
     - spiski outside whitelist.

5. Manifest/metadata:

   - list API must show uploaded backup as `backup_kind: "uploaded"`;
   - do not blindly trust original manifest `backup_kind`;
   - acceptable approaches:
     - rewrite manifest in stored ZIP and recalculate manifest-only archive metadata while preserving non-manifest file checksums;
     - or keep ZIP bytes unchanged and store trusted server metadata sidecar.
   - Choose the simpler robust approach and cover with tests.

6. Add route in `gear_xls/server_routes.py`:

   ```text
   POST /api/backups/upload
   ```

   Requirements:

   - login required;
   - role `admin`;
   - multipart form field `file`;
   - same-origin CSRF middleware applies;
   - no CORS wildcard;
   - response:

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

   - upload does not restore automatically.

7. Project mismatch:

   - upload/list may show backup from another project root;
   - include `project_root_matches`;
   - if mismatch, include warning `PROJECT_ROOT_MISMATCH`;
   - do not reject solely because of project mismatch. Restore confirmation will be implemented later.

## Tests

Extend existing pytest coverage.

Minimum tests for this session:

1. Upload rejects missing `file`.
2. Upload rejects empty file.
3. Upload rejects non-ZIP.
4. Upload rejects path traversal entry.
5. Upload rejects backslash path entry.
6. Upload rejects absolute path entry.
7. Upload rejects Windows drive prefix.
8. Upload rejects symlink/hardlink entry.
9. Upload rejects duplicate entries.
10. Upload rejects checksum mismatch.
11. Upload rejects unknown schema/schema_version.
12. Upload rejects extra unexpected file.
13. Upload rejects old `schedule.html` with standalone save artifacts.
14. Valid upload is stored under generated safe filename.
15. Valid upload appears in `GET /api/backups` as `backup_kind: "uploaded"`.
16. Project mismatch upload succeeds with warning and `project_root_matches: false`.

## Проверки

Run:

```powershell
python -m py_compile gear_xls/backup_manager.py gear_xls/server_routes.py
python -m pytest tests/test_backup_restore.py
```

If tests are split, run all backup/upload tests.

## Финальный ответ

Кратко укажи:

- как stored uploaded backup получает trusted metadata;
- какие validation cases покрыты tests;
- какие проверки запускались.
