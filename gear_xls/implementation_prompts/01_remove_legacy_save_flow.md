# Prompt 01: удалить старый standalone save flow

Ты работаешь в репозитории `SchedGen_PreRelease`. Это первая сессия из серии по реализации backup/restore веб-редактора.

Главный документ ТЗ: `gear_xls/WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED.md`. Перед работой прочитай разделы:

- `1.1. Важные файлы`
- `13.7. Deprecated /save_intermediate`
- `14.1. Старые controls`
- `15.1` - `15.6`
- `15.10. gear_xls/html_output/schedule.html`
- `18. Acceptance criteria`
- `20. Grep checks for final verification`

## Цель

Полностью убрать из активного UI и активного JS старый standalone workflow:

- `#saveSchedule`
- `#saveIntermediate`
- `/save_intermediate`
- `final_schedule.html`
- `intermediate_schedule.html`
- `body.static-schedule`

Эта сессия не должна реализовывать новый backup/restore UI и API. Максимум допустимо оставить место, куда позднее `backup_ui.js` динамически вставит пункты меню.

## Обязательные изменения

1. В `gear_xls/generators/html_structure_generator.py` удалить генерацию кнопок:
   - `<button id="saveIntermediate">...`
   - `<button id="saveSchedule">...`

2. В `gear_xls/html_styles.py` удалить CSS, относящийся к:
   - `#saveIntermediate`
   - `#saveSchedule`
   - `body.static-schedule`
   - mobile selectors для старых save-кнопок.

3. В `gear_xls/js_modules/save_export.js` удалить старую save-логику.
   Предпочтение: удалить модуль из inline-сборки в `html_javascript.py`.
   Допустимая альтернатива: оставить только безопасный no-op:

   ```js
   function initSaveExport() {}
   ```

   В активном коде не должно остаться:

   - bind на `#saveSchedule`;
   - bind на `#saveIntermediate`;
   - скачивание `final_schedule.html`;
   - скачивание `intermediate_schedule.html`;
   - вызов `/save_intermediate`;
   - добавление `body.static-schedule`.

4. В `gear_xls/js_modules/app_initialization.js`:
   - если `save_export.js` больше не инлайнится, обернуть вызов:

     ```js
     if (typeof initSaveExport === 'function') {
         initSaveExport();
     }
     ```

   - удалить или упростить ветки `body.static-schedule`.

5. В `gear_xls/html_javascript.py`:
   - убрать `save_export.js` из списка inline-модулей, если модуль больше не нужен;
   - либо убедиться, что он no-op и не содержит старого flow.

6. В `gear_xls/static/auth_ui.js`:
   - удалить `#saveIntermediate` и `#saveSchedule` из hide selectors / injected CSS;
   - не менять admin-only поведение `#exportToExcel`.

7. В `gear_xls/server_routes.py`:
   - удалить route `/save_intermediate` или заменить его deprecation-ответом;
   - если route оставлен, он должен возвращать JSON с `reason: "deprecated"` и статусом `410` или `400`;
   - он никогда не должен открывать Tk file dialog.

8. В `gear_xls/html_output/schedule.html`:
   - перегенерировать нормальным pipeline, если это возможно;
   - если normal generation требует недоступный Excel input, аккуратно пропатчить текущий файл;
   - итоговый файл не должен содержать старый standalone save flow.

## Важные ограничения

- Не реализуй новые backup routes.
- Не добавляй `backup_ui.js`.
- Не меняй export-to-Excel behavior, кроме удаления связей со старым save flow.
- Если в рабочем дереве есть чужие изменения, не откатывай их.

## Проверки

Запусти релевантные проверки:

```powershell
python -m py_compile gear_xls/server_routes.py gear_xls/html_javascript.py gear_xls/generators/html_structure_generator.py
node --check gear_xls/js_modules/app_initialization.js
node --check gear_xls/static/auth_ui.js
```

Если `save_export.js` оставлен:

```powershell
node --check gear_xls/js_modules/save_export.js
```

Проверь grep по активным файлам, исключая markdown-документы ТЗ и prompts:

```powershell
Get-ChildItem gear_xls -Recurse -File |
  Where-Object { $_.FullName -notmatch 'WEB_EDITOR_BACKUP_RESTORE_TZ|implementation_prompts|tests' } |
  Select-String -Pattern 'saveSchedule|saveIntermediate|/save_intermediate|final_schedule\.html|intermediate_schedule\.html|body\.static-schedule'
```

Ожидаемый результат: нет совпадений в активном UI/source/generated HTML. Совпадения допустимы только в тестах, добавленных в будущих сессиях.

## Финальный ответ

Кратко перечисли:

- какие файлы изменены;
- удален ли `/save_intermediate` или оставлен deprecated;
- удалось ли обновить `html_output/schedule.html`;
- какие проверки запускались и их результат.
