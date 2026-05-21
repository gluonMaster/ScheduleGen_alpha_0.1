# Web Editor: переход из поиска свободных аудиторий в расписание

Дата подготовки: 2026-05-21.

Этот файл фиксирует понимание задачи и технический план для новой сессии. Рабочую логику приложения на момент создания файла не менять.

## Цель

На странице `/rooms` в режиме поиска свободных аудиторий нужно сделать результаты поиска основным рабочим инструментом оператора:

1. Таблица занятости `#rooms-table-wrap` не должна показываться по умолчанию.
2. Вместо нее должна быть кнопка, например `Показать таблицу занятости аудиторий`, которая раскрывает/скрывает таблицу.
3. Каждый найденный свободный вариант аудитории должен быть интерактивной ссылкой/кнопкой.
4. По клику оператор должен попадать на `/schedule`, где уже подготовлено место для ручной вставки блока:
   - активирован режим редактирования;
   - видим только день результата, остальные дни скрыты;
   - нужная аудитория существует как колонка нужного здания и дня, при отсутствии добавлена стандартным UI-механизмом;
   - расписание прокручено к нужному времени и колонке;
   - целевая область визуально понятна оператору.
5. Если edit-lock недоступен из-за другого оператора, переходить на `/schedule` нельзя. Нужно показать понятное сообщение на `/rooms`.
6. Для `admin` в этом сообщении нужна кнопка принудительно завершить чужую сессию редактирования.

## Уточнения пользователя

- Блок создавать автоматически не нужно. Нужно только подготовить место для ручной вставки.
- Для результата вроде `0.03 - Mo: 10:00 - 13:00` на `/schedule` должен остаться видимым только `Mo`.
- Колонку аудитории предпочтительно добавлять тем же механизмом, который уже используется в UI редактора.
- Админ определяется по роли `admin` из `gear_xls/config/users.json`.
- Кнопка/механика принудительного завершения lock уже есть в проекте, ее нужно переиспользовать.

## Найденные точки входа

### `/rooms`

- `gear_xls/rooms_routes.py`
  - `ROOMS_PAGE_TEMPLATE` содержит HTML/CSS страницы.
  - Сейчас сразу рендерит:
    - `#rooms-controls`;
    - `#rooms-table-wrap`;
    - `#free-windows`;
    - скрипты `/static/auth_ui.js` и `/static/rooms_report.js`.
  - В шаблон уже инжектятся:
    - `window.CURRENT_USER`;
    - `window.USER_ROLE`;
    - `window.DISPLAY_NAME`.

- `gear_xls/static/rooms_report.js`
  - Загружает `/api/rooms/availability`.
  - `renderTable()` строит таблицу занятости и затем вызывает `renderFreeWindows()`.
  - `renderFreeWindows()` выбирает:
    - `renderAvailableRoomsReport(target)` для режима `_searchMode === "available"`;
    - `renderSingleRoomReport(target)` для режима конкретной аудитории.
  - `renderAvailableRoomsReport()` сейчас формирует элементы списка как plain text:
    - `floorSection.rooms.push({ room, lines })`;
    - затем `<li class="available-report-room"><strong>room</strong> - lines.join("; ")</li>`.
  - `dayLines` сейчас хранят строки вида `Mo: 10:00 - 13:00 (3 ч)`.
  - Для интерактивности лучше заменить `dayLines` на структурированные окна:
    - `{ building, room, day, start, end, startMin, endMin, duration }`.

### Edit-lock

- `gear_xls/server_routes.py`
  - `GET /api/lock/status` возвращает состояние lock.
  - `POST /api/lock/acquire` доступен ролям `admin`, `editor`, `organizer`.
  - `DELETE /api/lock` доступен только `admin`.
  - `GET /api/status` возвращает `lock`, `base_revision`, `individual_revision`, `restore`.

- `gear_xls/lock_manager.py`
  - `acquire_lock(login)` возвращает `{ok: true, holder, version}` или `{ok: false, holder, acquired_at, version}`.
  - `force_release(released_by_login)` снимает lock и ставит reason `force_released`.

- `gear_xls/static/lock_ui.js`
  - Уже умеет:
    - показывать состояние lock в navbar;
    - захватывать lock через внутреннюю `acquireLock()`;
    - снимать свой lock;
    - для admin показывать кнопку `Снять блокировку`;
    - вызывать `DELETE /api/lock` через внутреннюю `forceReleaseLock()`.
  - Наружу сейчас экспортируется только:
    - `window.SchedGenLockUI.clearLocalLockStateForRestore`;
    - `window.SchedGenLockUI.closeOpenDialogs`;
    - `window.SchedGenLockUI.handleSessionExpired`;
    - `window.SchedGenLockUI.refreshLockStatus`.
  - Для нового сценария есть два варианта:
    - на `/rooms` напрямую использовать fetch к `/api/lock/acquire` и `/api/lock`;
    - или расширить `SchedGenLockUI` публичными методами. Так как `/rooms` не подключает `lock_ui.js`, проще и изолированнее сделать легкий rooms-side client для этих API.

### `/schedule`

- `gear_xls/server_routes.py`
  - Route `/schedule` читает `gear_xls/html_output/schedule.html`.
  - Инжектит:
    - `window.CURRENT_USER`;
    - `window.USER_ROLE`;
    - `window.DISPLAY_NAME`;
    - `window.PUBLISHED_BASE_AVAILABLE`;
    - `/static/nav.css`;
    - `/static/auth_ui.js`;
    - `/static/base_sync_ui.js`;
    - `/static/lock_ui.js`;
    - `/js_modules/trial_ui.js`;
    - `/static/individual_ui.js`;
    - `/static/schedule_search_ui.js`;
    - `/static/backup_ui.js`.

- `gear_xls/static/auth_ui.js`
  - `SchedGenAuthUI.setEditMode(true)` включает локальный edit-mode, но корректный путь все равно должен идти через lock acquisition.
  - `isEditMode()` позволяет проверить, включен ли режим.

- `gear_xls/js_modules/core.js`
  - `window.toggleDay(btn, dayCode)` скрывает/показывает день.
  - Активная кнопка `.toggle-day-button.active[data-day="Mo"]` соответствует скрытому дню.
  - Чтобы оставить только нужный день, нужно для всех дней кроме целевого нажать/toggle активировать скрытие, а для целевого убедиться, что он не скрыт.

- `gear_xls/js_modules/column_helpers.js`
  - `window.addColumnIfMissing(day, room, building)` уже делает нужное DOM-добавление колонки.
  - Возвращает локальный `colIndex`.
  - Нормализует room через `normalizeRoomForBuilding`.
  - Обновляет `data-col` у ячеек и `data-col-index` у существующих блоков.

- `gear_xls/js_modules/menu.js`
  - Диалог добавления колонки использует тот же `addColumnIfMissing`.
  - `openAddColumnDialog(prefillBuilding, prefillDay)` есть, но для автоматической подготовки места лучше не открывать диалог, а вызвать `addColumnIfMissing()` напрямую после server-side проверки `/api/columns`.

- `gear_xls/server_routes.py`
  - `POST /api/columns` проверяет роль и edit-lock, но фактически только валидирует запрос и возвращает `{ok: true}`.
  - Поэтому правильная последовательность при автодобавлении колонки:
    1. lock уже захвачен;
    2. вызвать `POST /api/columns` с `{ building, day, room }`;
    3. при `ok` вызвать `addColumnIfMissing(day, room, building)` в DOM.

## Предлагаемая архитектура

### 1. Скрытая таблица на `/rooms`

В `ROOMS_PAGE_TEMPLATE`:

- добавить кнопку рядом с refresh/search controls:
  - `id="btn-toggle-rooms-table"`;
  - начальный текст `Показать таблицу занятости аудиторий`;
- добавить `hidden` или CSS-класс на `#rooms-table-wrap` по умолчанию;
- в `rooms_report.js` добавить wiring:
  - клик переключает видимость;
  - текст меняется на `Скрыть таблицу занятости аудиторий`;
  - `renderTable()` может продолжать строить таблицу в скрытом контейнере, чтобы не менять расчетную логику.

Важно: `showError(msg)` сейчас пишет ошибку в `#rooms-table-wrap`. После скрытия таблицы ошибки лучше выводить в отдельный статус/в `#free-windows`, чтобы пользователь их видел.

### 2. Структурировать результаты поиска свободных аудиторий

В `renderAvailableRoomsReport()`:

- вместо `dayLines.push(day + ": " + formatWindowList(free, true))` сохранить каждое окно отдельно;
- для каждого `free` окна добавить clickable item:
  - `<button type="button" class="available-room-link" data-building="..." data-room="..." data-day="..." data-start="10:00" data-end="13:00">...</button>`;
  - или `<a href="/schedule?...">...</a>` с JS-preflight на click.

Предпочтение: использовать `<button>`, потому что сначала нужно проверить и захватить lock. При успехе уже делать `window.location.href = "/schedule?...";`.

Параметры URL:

```text
/schedule?roomFocus=1&building=Villa&room=0.03&day=Mo&start=10%3A00&end=13%3A00
```

Имена можно выбрать другие, но они должны быть стабильны и явно namespaced, например:

```text
/schedule?rooms_nav=1&rooms_building=Villa&rooms_room=0.03&rooms_day=Mo&rooms_start=10%3A00&rooms_end=13%3A00
```

### 3. Lock-preflight на `/rooms`

В `rooms_report.js` добавить:

- делегированный click listener на `#free-windows`;
- `handleAvailableRoomClick(event)`;
- проверку role:
  - если `window.USER_ROLE` не `admin/editor/organizer`, показать сообщение `Для подготовки расписания нужен доступ к редактированию`.
- `fetch("/api/lock/acquire", { method: "POST", headers, body: "{}" })`;
- если `{ok: true}`:
  - перейти на `/schedule` с параметрами;
- если `{ok: false}`:
  - остаться на `/rooms`;
  - показать сообщение: `Редактирование сейчас невозможно: расписание редактирует <holder>.`;
  - если `window.USER_ROLE === "admin"`, добавить кнопку `Снять блокировку`;
  - кнопка вызывает `DELETE /api/lock`, затем можно либо повторить acquire автоматически, либо показать `Блокировка снята. Нажмите аудиторию еще раз.` Лучше повторить acquire и перейти, если force-release успешен.

Нужен отдельный видимый контейнер под сообщения, например `#rooms-navigation-status`, чтобы не смешивать с таблицей.

### 4. Подготовка `/schedule` после перехода

Лучше добавить новый статический скрипт, например:

```text
gear_xls/static/rooms_schedule_focus.js
```

Подключить его в `/schedule` после `individual_ui.js` и после inline JS приложения. В текущем порядке route уже добавляет external scripts перед `</body>`, а inline application JS уже находится внутри HTML, поэтому функции `toggleDay`, `addColumnIfMissing`, `updateActivityPositions`, `BuildingService` должны быть доступны.

Скрипт должен:

1. Прочитать query params.
2. Если нет `rooms_nav=1`, ничего не делать.
3. Дождаться готовности:
   - `window.SchedGenAuthUI`;
   - `window.SchedGenLockUI`;
   - `window.addColumnIfMissing`;
   - `window.toggleDay`;
   - `window.updateActivityPositions`;
   - `.schedule-container`.
4. Проверить edit-mode:
   - так как lock уже захвачен на `/rooms`, `lock_ui.js` при загрузке должен увидеть holder == currentUser и включить edit-mode.
   - если через короткий timeout `SchedGenAuthUI.isEditMode()` не стал true, показать сообщение и не менять DOM.
5. Оставить видимым только нужный день:
   - собрать `window.daysOrder || ["Mo","Di","Mi","Do","Fr","Sa","So"]`;
   - для каждого дня:
     - если день целевой и кнопка `.toggle-day-button.active[data-day=day]` есть, вызвать `toggleDay(button, day)` чтобы показать;
     - если день не целевой и кнопка не active, вызвать `toggleDay(button, day)` чтобы скрыть.
6. Обеспечить колонку:
   - вызвать `POST /api/columns` с building/day/room;
   - если ok, `colIndex = addColumnIfMissing(day, room, building)`;
   - если `colIndex < 0`, показать ошибку.
7. Обновить позиции:
   - `updateActivityPositions()`;
   - если есть `ScheduleCompactRows.refresh()`, вызвать ее.
8. Найти целевую ячейку:
   - вычислить `startRow = Math.floor((startMinutes - gridStart) / timeInterval)`;
   - найти container через `BuildingService.findScheduleContainerForBuilding(building)`;
   - найти `td.day-${day}[data-row="${startRow}"][data-col="${colIndex}"]`.
9. Прокрутить:
   - `targetCell.scrollIntoView({ block: "center", inline: "center" })`;
   - возможно затем небольшой `window.scrollBy(0, -120)` с учетом nav/sticky.
10. Подсветить:
   - временный CSS class на ячейки от `startRow` до `endRow`;
   - можно подсветить header аудитории.
11. Включить quick-add режим:
   - пользователь просил "режим редактирования" автоматически, не обязательно "режим добавления по клику".
   - Если нужен именно удобный ручной insert, можно также активировать `#toggle-add-mode`, но это рискованно: в quick_add_mode активное здание хранится локально и переключается по клику. Без доработки возможна путаница.
   - Более безопасно: не включать quick-add автоматически, а только подсветить место и оставить кнопку `+` доступной. Если нужно ускорить, добавить отдельную маленькую floating-подсказку `Нажмите подсвеченную ячейку в режиме добавления`.

### 5. Важный риск: gridStart не экспортирован на window

В `html_javascript.py` переменные задаются как `var gridStart`, `var timeInterval`, `var daysOrder`, а `window.daysOrder` явно выставлен. В отдельных external scripts доступ к `gridStart/timeInterval` может быть неоднозначным в зависимости от browser global binding для top-level `var`.

Если `rooms_schedule_focus.js` не видит `window.gridStart`, есть варианты:

- в inline variables добавить:
  - `window.gridStart = gridStart;`
  - `window.timeInterval = timeInterval;`
- или в новом скрипте читать bare identifiers через `typeof gridStart !== "undefined" ? gridStart : 540`.

В проекте уже есть код, который использует оба подхода. Для нового external script лучше применить оба fallback.

## Возможные тесты

### Python/шаблон

Добавить/расширить pytest в `tests/test_sunday_trial_support.py` или новый файл:

- `ROOMS_PAGE_TEMPLATE` содержит `btn-toggle-rooms-table`.
- `#rooms-table-wrap` имеет `hidden` или начальный скрывающий класс.
- `/schedule` route подключает `/static/rooms_schedule_focus.js`.

### JS/static text tests

Если в проекте нет JS runtime тестов, можно хотя бы текстово проверить:

- `rooms_report.js` содержит `available-room-link` и `data-building/data-room/data-day/data-start/data-end`.
- `rooms_report.js` вызывает `/api/lock/acquire`.
- admin path вызывает `DELETE /api/lock`.
- `rooms_schedule_focus.js` вызывает `/api/columns` и `addColumnIfMissing`.

### Ручная проверка

1. Зайти как `editor`.
2. Открыть `/rooms`.
3. Убедиться, что таблица занятости скрыта, список результатов виден после поиска.
4. Кнопка таблицы раскрывает/скрывает `#rooms-table-wrap`.
5. В режиме свободных аудиторий найти окно.
6. Кликнуть аудиторию:
   - если lock свободен, переход на `/schedule`;
   - edit-mode включен;
   - видим только день результата;
   - колонка нужной аудитории есть;
   - прокрутка стоит на нужном времени.
7. Занять lock другим пользователем.
8. Повторить клик:
   - перехода нет;
   - сообщение о недоступном редактировании видно.
9. Зайти как `admin`, повторить при чужом lock:
   - сообщение содержит кнопку принудительного снятия;
   - кнопка снимает lock и позволяет продолжить.

## Приоритет реализации

1. Скрытие таблицы и toggle-кнопка.
2. Структурирование результатов и clickable UI на `/rooms`.
3. Lock-preflight на `/rooms` с admin force-release.
4. Новый schedule focus script с day filtering, column ensuring, scroll/highlight.
5. Тесты и ручная проверка в браузере.

## Решения, которые лучше принять в реализации

- Не создавать блок автоматически.
- Не открывать форму создания блока автоматически на первом проходе: это снижает риск побочных эффектов в текущем старом inline UI. Достаточно привести оператора к подсвеченной ячейке в активном edit-mode.
- Колонку добавлять через существующий `addColumnIfMissing()`, но перед этим дергать `POST /api/columns`, чтобы соблюсти server-side role/lock contract.
- Lock захватывать до перехода с `/rooms`, чтобы не грузить `/schedule`, если редактирование занято другим оператором.
- Admin force-release на `/rooms` делать прямым вызовом `DELETE /api/lock`, потому что `lock_ui.js` на `/rooms` сейчас не подключен.
