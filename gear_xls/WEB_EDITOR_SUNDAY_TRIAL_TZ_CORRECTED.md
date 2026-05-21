# Исправленное ТЗ: воскресенье для trial-занятий в веб-редакторе

## Цель

Добавить поддержку воскресенья (`So`) в веб-редактор расписания для создания, редактирования, перемещения и изменения размера trial-занятий.

При этом:

- `So` является рабочим днем только для web-editor trial-данных;
- регулярные/non-trial занятия на `So` запрещены;
- воскресные trial-занятия должны сохраняться как рабочие данные и попадать в web-export Excel;
- воскресенье и любые воскресные занятия не должны отображаться в финальных печатных/публичных PDF/HTML-визуализациях.

## Критические уточнения после проверки кода

Исходный подход с добавлением `So` в общую сетку web-editor корректен, но простое добавление `So` в единый `VALID_DAYS` опасно.

В коде есть несколько разных контуров данных:

1. **Web-editor grid / DOM** — генерируемая таблица дней и колонок.
2. **Individual/trial state** — `/api/blocks`, `individual_lessons.json`, `state_manager.py`.
3. **Base/group state** — публикация базового расписания через `/api/schedule/publish`, `base_schedule_manager.py`.
4. **Backup/restore** — отдельная валидация `base_schedule.json` и `individual_lessons.json` в `backup_manager.py`.
5. **Excel web-export** — прямой DOM -> `/export_to_excel` -> `excel_exporter.py`.
6. **Final visualizers** — `visualiser/*` и `visualiserTV/*`.

Поэтому нужно разделить наборы дней:

- `WEB_EDITOR_DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]`;
- `PUBLIC_SCHEDULE_DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]`;
- `TRIAL_ONLY_DAYS = {"So"}`;
- `DAY_TO_WEEKDAY = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}`.

`So` нельзя добавлять безусловно во все валидаторы как обычный день публичного расписания.

## Рекомендуемый подход

Добавить `So` как поддерживаемый день web-editor на уровне общей модели дней, а не создавать отдельную role-specific сетку только для `organizer`.

Причины:

- текущая сетка дней генерируется заранее в HTML и используется всеми ролями;
- создание колонок, drag/drop, compact rows, поиск, сохранение individual/trial-блоков и backup/restore завязаны на единый DOM/день;
- отдельная UI-сетка для одной роли добавит больше условной логики и риск рассинхронизации DOM/состояния.

Бизнес-ограничение должно жить в валидации и UX-защите:

- `So` разрешен для `trial`;
- `So` запрещен для `group`, `individual`, `nachhilfe` и любых других non-trial типов;
- server-side валидация обязательна, client-side ограничения нужны только для раннего UX и защиты прямого web-export из DOM.

## Требования

### 1. Web-editor day model

В web-editor день `So` должен быть доступен в:

- таблице расписания;
- кнопках скрытия/показа дней;
- диалоге добавления колонки;
- диалоге создания занятия;
- drag/drop и resize существующих trial-блоков;
- восстановлении/отрисовке сохраненных trial-блоков из `individual_lessons.json`.

Затрагиваемые файлы:

- `gear_xls/schedule_structure.py`;
- `gear_xls/generators/html_coordinator.py`;
- `gear_xls/generators/html_structure_generator.py`;
- `gear_xls/html_javascript.py` — проверить передачу `daysOrder`;
- `gear_xls/js_modules/menu.js`;
- `gear_xls/js_modules/column_helpers.js`;
- `gear_xls/js_modules/block_creation_dialog.js` — проверить, что день берется из `daysOrder`, а не из скрытого hardcode;
- `gear_xls/js_modules/core.js` — проверить hide/show day;
- `gear_xls/static/individual_ui.js`;
- `gear_xls/static/base_sync_ui.js`.

Желательно вынести дни в одну Python-константу, например `gear_xls/day_constants.py`, и использовать ее в генераторах. Для JS нужно эмитить тот же список в `window.daysOrder`. В JS fallback-и должны соответствовать новому списку.

### 2. Server-side validation для individual/trial blocks

В `gear_xls/state_manager.py`:

1. Разрешить `So` как день web-editor state.
2. Для `lesson_type == "trial"` валидировать `trial_dates` по `DAY_TO_WEEKDAY`, включая `So -> 6`.
3. Для `lesson_type != "trial"` и `day == "So"` возвращать ошибку, например `Sunday is allowed only for trial lessons`.
4. Не полагаться только на роль `organizer`: запрет non-trial на `So` должен действовать для `admin`, `editor`, `organizer` и прямых API-запросов.
5. `convert_block_to_regular()` должен явно запрещать конвертацию trial-блока на `So` в регулярный блок. Сейчас этот путь может обходить обычную `_validate_block`, поэтому его нужно закрыть отдельно.

Ожидаемое поведение:

- valid trial on `So` + воскресная дата принимается;
- trial on `So` + дата не воскресенье отклоняется;
- `individual`, `nachhilfe`, `group` на `So` отклоняются;
- conversion trial -> regular на `So` отклоняется.

### 3. Server-side validation для base/group publication

Критично: публикация базового расписания идет отдельным контуром через `/api/schedule/publish` и `gear_xls/base_schedule_manager.py`, а не через `_validate_block()` в `state_manager.py`.

Нужно добавить валидацию в `gear_xls/base_schedule_manager.py`:

- base/group blocks могут иметь только дни из `PUBLIC_SCHEDULE_DAYS` (`Mo`-`Sa`);
- `group` block на `So` должен отклоняться с понятной ошибкой;
- блоки с неизвестным днем также должны отклоняться;
- не нужно молча фильтровать `So` при публикации, иначе админ может не заметить потерю данных.

В `gear_xls/server_routes.py` нужно обработать ошибку публикации и вернуть стабильный код, например:

- HTTP `400`;
- `code: "INVALID_BASE_DAY"` или `"SUNDAY_REGULAR_FORBIDDEN"`;
- человекочитаемое сообщение.

### 4. Backup/restore

В `gear_xls/backup_manager.py` нельзя просто заменить общий `VALID_DAYS` на `Mo`-`So` для всех типов состояния.

Нужно разделить правила:

- `validate_base_state()`:
  - `base_schedule.json` принимает только `group`;
  - день должен быть только из `PUBLIC_SCHEDULE_DAYS` (`Mo`-`Sa`);
  - `So` в base/group backup должен отклоняться.

- `validate_individual_state()`:
  - день может быть из `WEB_EDITOR_DAYS` (`Mo`-`So`);
  - если `day == "So"`, `lesson_type` обязан быть `trial`;
  - для `trial` обязательно валидировать `trial_dates` и weekday map, включая `So -> 6`;
  - individual/nachhilfe на `So` должны отклоняться.

Backup с trial-блоком на `So` должен создаваться и восстанавливаться. Backup с base/group `So` или individual non-trial `So` должен отклоняться при upload/restore validation.

### 5. Client-side UX guards

Server-side правила являются источником истины, но web-export в Excel собирает данные напрямую из DOM, поэтому client-side защита также нужна.

В `gear_xls/static/individual_ui.js` и связанных create/edit handlers:

- при создании занятия на `So` разрешать только `lesson_type == "trial"`;
- при редактировании блока не позволять менять trial на non-trial на `So`;
- при drag/drop trial-блока на `So` сохранять только при валидных Sunday `trial_dates`; при серверной ошибке откатывать DOM или явно сообщать пользователю;
- для admin/group legacy path важно поставить проверку `day == "So" && lesson_type != "trial"` до ветки, которая возвращает управление старой DOM-логике для `group`.

В `gear_xls/js_modules/trial_ui.js`:

- кнопку `Сделать регулярным занятием` не показывать для trial-блоков на `So`, либо показывать disabled с объяснением;
- сервер все равно должен отклонять этот action.

### 6. Excel web-export

Воскресные trial-блоки должны сохраняться в Excel как рабочие данные.

Затрагиваемые файлы:

- `gear_xls/js_modules/export_to_excel.js`;
- `gear_xls/excel_exporter.py`;
- `gear_xls/server_routes.py` route `/export_to_excel`.

Требования:

1. `collectScheduleData()` должен собирать trial-блоки на `So` и сохранять:
   - `day = "So"`;
   - `lesson_type = "trial"`;
   - `trial_dates_json`.
2. Client-side перед отправкой на `/export_to_excel` должен отклонять non-trial блоки на `So`, если они по ошибке оказались в DOM.
3. Server-side export validation должен повторять это правило: `So` допустим только для `trial`. Прямой POST на `/export_to_excel` не должен позволять выгрузить regular/group `So`.
4. Серверный Excel exporter не должен фильтровать или удалять `So` trial rows.
5. Если `lesson_type` отсутствует, считать блок non-trial/group по текущей логике и отклонять `So`.

### 7. Final visualization / public output

Финальные PDF/HTML не должны показывать `So` и воскресные занятия.

Затрагиваемые файлы:

- `visualiser/data_processor.py`;
- `visualiser/schedule_visualizer_enhanced.py`;
- `visualiser/enhanced_export_manager_html.py` — проверить, что получает уже отфильтрованные дни;
- `visualiser/teacher_exporter.py`;
- `visualiser/group_exporter.py`;
- `visualiserTV/data_processor.py`;
- `visualiserTV/schedule_visualizer_enhanced.py`;
- `visualiserTV/enhanced_layout_manager.py`;
- `visualiserTV/enhanced_export_manager_html.py`;
- `visualiserTV/teacher_exporter.py`;
- `visualiserTV/group_exporter.py`.

Рекомендуемый вариант:

- добавить явный helper, например `filter_final_visualization_days(df)`, который оставляет только `PUBLIC_SCHEDULE_DAYS`;
- применять его перед `process_schedule_data()` во всех final visualization entrypoints;
- либо встроить фильтр в `process_schedule_data()`, если этот метод используется только для финальной визуализации.

Важно для TV-ветки: `visualiserTV/enhanced_layout_manager.py` уже группирует выходные как `['Sa', 'So']`; без фильтра `So` будет отрисован. Поэтому фильтр должен применяться до создания layout manager.

`gear_xls/pdf_generator.py` уже использует список `Mo`-`Sa`; нужно проверить регрессионным тестом, что `So` там не появляется.

### 8. Права ролей

Не менять `users.json`, модель пользователей и список ролей.

Сохранить текущую бизнес-логику:

- `organizer` создает/редактирует/удаляет только `trial`;
- `organizer` может добавлять колонку на `So` для trial;
- `admin`/`editor` не могут создавать non-trial на `So`, даже если в обычные дни имеют больше прав;
- публикация base/group на `So` запрещена.

## Acceptance criteria

1. В web-editor отображается день `So` в таблице и toggle-кнопках.
2. В диалоге добавления колонки можно выбрать `So`.
3. В диалоге создания занятия можно создать trial на `So`.
4. Organizer может создать trial-занятие на `So` с датой, которая реально является воскресеньем.
5. Сервер принимает валидный trial-блок на `So`.
6. Сервер отклоняет trial-блок на `So`, если хотя бы одна `trial_dates` дата не воскресенье.
7. Сервер отклоняет `individual`, `nachhilfe`, `group` и любой другой non-trial блок на `So`.
8. Конвертация trial -> regular для блока на `So` отклоняется.
9. Admin/editor UI не создает regular/group DOM-блок на `So`; если такой блок появился из legacy/ручного пути, export/publish отклоняют его.
10. `/api/schedule/publish` отклоняет group/base block на `So`.
11. Backup с individual trial-блоком на `So` создается и восстанавливается.
12. Backup/restore отклоняет base/group `So` и individual non-trial `So`.
13. Web-export Excel содержит строку с `day = So` для Sunday trial-блока.
14. Web-export Excel отклоняет или блокирует non-trial `So`.
15. Финальные PDF/HTML основного визуализатора не содержат `So`, `Sonntag` и воскресные занятия.
16. Финальные PDF/HTML TV-визуализатора не содержат `So`, `Sonntag` и воскресные занятия.
17. Teacher/group PDF exports не содержат `So`, если они строятся из Excel, где есть Sunday trial rows.
18. Существующие дни `Mo`-`Sa` работают без изменений.

## Минимальные автоматические проверки

### `state_manager.py`

- `_validate_block()` принимает trial `So` с Sunday date.
- `_validate_block()` отклоняет trial `So` с non-Sunday date.
- `_validate_block()` отклоняет non-trial `So` для `admin`, `editor`, `organizer`.
- `convert_block_to_regular()` отклоняет trial-блок на `So`.

### `base_schedule_manager.py` / `/api/schedule/publish`

- publish group block на `Mo` проходит.
- publish group block на `So` отклоняется.
- API возвращает стабильный validation code.

### `backup_manager.py`

- `validate_individual_state()` принимает trial `So` с Sunday date.
- `validate_individual_state()` отклоняет trial `So` с non-Sunday date.
- `validate_individual_state()` отклоняет individual/nachhilfe `So`.
- `validate_base_state()` отклоняет group `So`.

### Excel export

- DOM/export payload с trial `So` создает Excel row с `day = So`.
- DOM/export payload с group/non-trial `So` отклоняется до создания Excel.

### Final visualizers

- `visualiser` получает DataFrame с `Mo` и `So`, но после final-filter отрисовывает только `Mo`.
- `visualiserTV` получает DataFrame с `Sa` и `So`, но после final-filter отрисовывает только `Sa`.
- HTML export не содержит `Sonntag`.
- Teacher/group export не содержит Sunday rows.

## Ручные сценарии

1. Войти как `organizer`.
2. Захватить lock.
3. Добавить колонку на `So`.
4. Создать trial-занятие на воскресную дату.
5. Попробовать указать дату понедельника для `So` trial — получить ошибку.
6. Перетащить/изменить размер valid `So` trial-блока — сохранить без ошибки.
7. Обновить страницу и убедиться, что блок сохранился.
8. Попробовать `Сделать регулярным занятием` для `So` trial — кнопки нет/disabled или сервер отклоняет.
9. Войти как `admin`.
10. Попробовать создать regular/group на `So` — UI должен запретить, publish/export не должны принять такой блок.
11. Экспортировать в Excel и проверить наличие Sunday trial row.
12. Построить final PDF/HTML через основной визуализатор и проверить отсутствие `So`/`Sonntag`.
13. Если используется TV-ветка, построить TV PDF/HTML и проверить отсутствие `So`/`Sonntag`.
14. Проверить, что `Mo`-`Sa` сценарии создания, редактирования, публикации, backup/restore и export не изменились.

## Ограничения

- Не менять модель пользователей и роли в `users.json`.
- Не добавлять отдельную роль или отдельный режим `Sunday`.
- Не показывать воскресенье в финальных печатных/публичных версиях расписания.
- Не удалять Sunday trial из web-export Excel.
- Не использовать один общий `VALID_DAYS = Mo..So` для base/public и individual/trial контуров.
- Не решать запрет regular `So` только в UI: server-side validation обязательна.

## Оценка трудоемкости

С учетом дополнительных контуров `base_schedule_manager`, `/api/schedule/publish`, convert-to-regular и Excel export validation оценка выше исходной:

- реализация без полного набора тестов: примерно 0.75-1 рабочий день;
- реализация с unit/integration проверками и ручной проверкой web/export/visualizer/TV: примерно 1-1.5 рабочих дня.

Вариант “показывать `So` только organizer в UI” по-прежнему не рекомендуется для первого шага: он добавит role-specific DOM/состояние и повысит риск рассинхронизации.
