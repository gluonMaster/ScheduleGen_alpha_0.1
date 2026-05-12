# Prompt 07: final integration, generated schedule, regression hardening

Ты работаешь в репозитории `SchedGen_PreRelease`. Это финальная сессия из серии по backup/restore веб-редактора.

Ожидается, что предыдущие сессии уже реализовали:

- removal of old standalone save flow;
- backup create/list/download API;
- upload API;
- restore status/middleware;
- restore engine/route;
- frontend `backup_ui.js`;
- lock UI handling for restore.

Перед началом прочитай `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`, особенно разделы:

- `18. Acceptance criteria`
- `19. Recommended implementation order`
- `20. Grep checks for final verification`

## Цель

Провести финальную интеграцию и hardening:

- устранить расхождения между source modules and generated `html_output/schedule.html`;
- довести tests до passing;
- проверить acceptance criteria;
- исправить интеграционные баги, найденные проверками.

Не добавляй новые крупные features сверх ТЗ. Фокус на завершении и стабилизации.

## Обязательная последовательность

1. Посмотреть текущее состояние:

   ```powershell
   git status --short
   ```

   Не откатывай чужие изменения.

2. Проверить, что старые artifacts отсутствуют в active source/generated UI:

   ```powershell
   Get-ChildItem gear_xls -Recurse -File |
     Where-Object { $_.FullName -notmatch 'WEB_EDITOR_BACKUP_RESTORE_TZ|implementation_prompts' } |
     Select-String -Pattern 'saveSchedule|saveIntermediate|/save_intermediate|final_schedule\.html|intermediate_schedule\.html|body\.static-schedule'
   ```

   Ожидаемый результат:

   - нет совпадений в active source/generated UI;
   - допустимы только tests/comments, которые явно проверяют rejected legacy artifacts.

3. Проверить, что новые backend/frontend hooks есть:

   ```powershell
   Get-ChildItem gear_xls -Recurse -File |
     Where-Object { $_.FullName -notmatch 'WEB_EDITOR_BACKUP_RESTORE_TZ|implementation_prompts' } |
     Select-String -Pattern 'api/backups|api/restore/status|backup_ui|restore_status|get_backup_dir|get_restore_status_path'
   ```

4. Убедиться, что `gear_xls/html_output/schedule.html`:

   - содержит current scripts/includes needed by server route;
   - не содержит old standalone save artifacts;
   - совместим с `server_routes.py` injection logic;
   - содержит или получает динамически backup/restore menu items.

   Если normal regeneration возможна, используй normal pipeline. Если нет, patch generated file consistently.

5. Запустить syntax checks:

   ```powershell
   python -m py_compile gear_xls/runtime_paths.py gear_xls/backup_manager.py gear_xls/restore_manager.py gear_xls/lock_manager.py gear_xls/server_routes.py gear_xls/html_javascript.py gear_xls/generators/html_structure_generator.py
   node --check gear_xls/static/backup_ui.js
   node --check gear_xls/static/lock_ui.js
   node --check gear_xls/static/auth_ui.js
   node --check gear_xls/js_modules/app_initialization.js
   ```

   Add other touched JS files as needed.

6. Run backend tests:

   ```powershell
   python -m pytest
   ```

   If pytest is not installed and dependency was not added yet, add the agreed test dependency from ТЗ (`requirements-dev.txt` or `requirements.txt`) and document it.

7. If browser/dev server validation is feasible:

   - start local app using existing project workflow;
   - open `/schedule`;
   - check admin backup/restore menu;
   - check non-admin visibility if test users exist;
   - create backup;
   - download backup;
   - upload valid backup;
   - restore with active admin lock;
   - verify hard reload and restored state;
   - verify another tab/user gets restore overlay or server-side block.

   If browser validation is not feasible, state exactly why.

## Acceptance checklist

Verify and fix if needed:

- `#saveSchedule` absent from generated/current UI and active handlers.
- `#saveIntermediate` absent from generated/current UI and active handlers.
- No active code calls `/save_intermediate`.
- `/save_intermediate`, if still present, returns deprecation and never opens Tk dialog.
- `html_output/schedule.html` no longer contains old standalone save artifacts.
- Admin can create server backup.
- Admin can download backup ZIP.
- Backup ZIP contains exactly schema v1 expected files and valid manifest checksums.
- Backup includes persisted base, individual, schedule HTML, and allowed `spiski` files.
- Backup excludes lock, restore status, logs, exports, source Excel/XLSM, config secrets/users.
- Admin can restore from server backup.
- Admin can upload ZIP, validate/store it, and restore from stored uploaded backup.
- Restore requires active edit lock of current admin.
- Restore creates safety backup before target writes.
- Restore updates revisions according to ТЗ section 12.2.
- Restore clears runtime edit lock with restore reason.
- Restore blocks mutating/schedule-sensitive APIs for others while active.
- Active/stale tabs see restore overlay and cannot continue editing old state.
- After successful restore, `/schedule` shows restored state after hard reload.
- Dangerous/invalid ZIP files are rejected.
- Project mismatch requires second confirmation.
- Partial failure attempts rollback; rollback failure leaves recovery mode active.
- Existing publish, individual CRUD, export, login/logout, lock acquire/release still work.

## Финальный ответ

Кратко укажи:

- итоговый статус acceptance checklist;
- tests/checks run;
- any remaining risks or checks that could not be run;
- list of files changed in this final hardening session.
