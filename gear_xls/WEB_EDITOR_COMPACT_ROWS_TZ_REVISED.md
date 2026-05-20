# Исправленное ТЗ: умное автоскрытие пустых строк сверху и снизу таблицы расписания

## 0. Назначение документа

Это ТЗ предназначено для реализации в отдельной Codex-сессии по приложенному проекту `gear_xls` после уже выполненной переработки сохранения по ТЗ `WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED`.

Документ должен быть достаточным без дополнительного контекста из текущего чата.

Главная цель: сделать таблицы веб-редактора расписания компактнее по вертикали за счет клиентского автоскрытия пустых временных строк **только сверху и снизу** каждой таблицы здания.

Ключевые зафиксированные решения этой версии:

- старую standalone-логику сохранения через `save_export.js`, `document.documentElement.outerHTML`, `#saveSchedule`, `#saveIntermediate`, `/save_intermediate`, `final_schedule.html`, `intermediate_schedule.html` не учитывать и не возвращать;
- backup/restore уже является отдельной server-side логикой и работает с persisted server state, а не с текущим DOM браузера;
- compact rows не должен менять backup/restore, серверные API, JSON state, Excel-экспорт и данные занятий;
- автоскрытие работает в обычном режиме просмотра для всех ролей;
- при активном поиске, активном edit mode или активном add-mode автоскрытие отключается, все временные строки раскрываются;
- во время drag/drop и vertical resize compact-диапазон не пересчитывается на лету; пересчет допускается только после завершения действия;
- после применения compact-диапазона контейнер таблицы нужно прокручивать к началу видимого диапазона;
- сообщения о пустой выборке или скрытых всех днях показываются всем ролям;
- при сомнительных координатах видимого блока используется fail-open: таблица соответствующего здания раскрывается полностью, чтобы не скрыть занятие случайно.

## 1. Цель

Сделать веб-таблицу расписания более компактной по вертикали: автоматически скрывать пустые временные строки **до первого видимого занятия** и **после последнего видимого занятия** в каждой таблице здания.

Улучшение должно быть чисто клиентским и временным:

- не менять `base_schedule.json`;
- не менять `individual_lessons.json`;
- не менять серверные API;
- не менять persisted server state;
- не менять Excel-экспорт как источник данных;
- не менять алгоритмы генерации расписания;
- не сохранять состояние compact rows в backup;
- не записывать настройки в `localStorage`, cookies или server state.

Допускается менять клиентский JS/CSS, порядок подключения JS-модулей и текущий сгенерированный `gear_xls/html_output/schedule.html`, если это требуется для подключения нового модуля.

## 2. Актуальный контекст проекта после backup/restore

После реализации `WEB_EDITOR_BACKUP_RESTORE_TZ_REVISED` в проекте не следует ожидать старую standalone-логику сохранения HTML.

В актуальном проекте должны быть или могут быть:

- `gear_xls/backup_manager.py`;
- `gear_xls/restore_manager.py`;
- `gear_xls/static/backup_ui.js`;
- server-side backup/restore routes;
- server-side restore mode;
- `gear_xls/html_output/schedule.html` как persisted/generated HTML, включаемый в backup.

В этой задаче **не нужно**:

- добавлять `save_export.js`;
- восстанавливать `initSaveExport()`;
- возвращать кнопки `#saveSchedule` или `#saveIntermediate`;
- добавлять подготовку compact rows перед `document.documentElement.outerHTML`;
- менять ZIP backup format;
- менять restore flow;
- менять backup validation;
- менять restore overlay.

Совместимость с backup/restore требуется только в таком смысле:

- compact rows не должен записывать временные классы/сообщения в persisted server state;
- backup должен продолжать сохранять серверный `html_output/schedule.html`, а не runtime DOM открытой вкладки;
- после restore и hard reload страницы compact rows должен корректно инициализироваться заново;
- временные DOM-классы compact rows не должны мешать `backup_ui.js`, `lock_ui.js`, `base_sync_ui.js`, `individual_ui.js`, `schedule_search_ui.js`.

## 3. Текущая структура расписания

Проект генерирует HTML-расписание с отдельной таблицей для каждого здания, например:

```html
<h2>Здание: Villa</h2>
<div class="schedule-container" data-building="Villa">
  <table class="schedule-grid">...</table>
  <div class="activity-block" ...></div>
</div>

<h2>Здание: Kolibri</h2>
<div class="schedule-container" data-building="Kolibri">...</div>
```

Ключевые существующие сущности:

- строки таблицы находятся в `.schedule-grid tbody tr`;
- каждая строка содержит ячейки `td[data-row]`;
- значение `data-row` — индекс временной строки;
- временная сетка задается глобальными JS-переменными `gridStart` и `timeInterval`, которые эмитируются в `html_javascript.py`;
- блоки занятий имеют класс `.activity-block` и runtime-атрибуты:
  - `data-day`, например `Mo`, `Di`;
  - `data-building`, например `Villa`, `Kolibri`;
  - `data-start-row`;
  - `data-row-span`;
  - `data-lesson-type`;
  - `data-col-index`;
- позиционирование блоков выполняет глобальная функция `window.updateActivityPositions()` из `js_modules/position.js`;
- видимость дней переключается кнопками `.toggle-day-button` и функцией `window.toggleDay(btn, dayCode)` из `js_modules/core.js`;
- важная особенность текущей логики: у `.toggle-day-button.active` день считается **скрытым**, а не выбранным;
- фильтр типов занятий находится в `js_modules/lesson_type_filter.js`;
- скрытые фильтром блоки получают класс `.lesson-type-filter-hidden`, при этом CSS скрывает их через `visibility: hidden`, а не через `display: none`;
- режим быстрого добавления включается кнопкой `#toggle-add-mode`; при включении кнопка получает класс `.active`;
- общий режим редактирования управляется frontend/auth-lock логикой; при наличии `window.SchedGenAuthUI.isEditMode()` его нужно использовать для определения edit mode;
- поиск по расписанию находится в `static/schedule_search_ui.js` и уже умеет скрывать строки/колонки собственными классами; новое автоскрытие строк не должно конкурировать с поиском.

## 4. Основное поведение

### 4.1. Расчет выполняется независимо для каждого здания

Для каждого `.schedule-container[data-building]` диапазон видимых временных строк рассчитывается отдельно.

Пример: если в `Villa` видимые занятия начинаются в 14:30, а в `Kolibri` — в 09:00, таблицы должны иметь разные вертикальные compact-диапазоны.

### 4.2. Учитываются только видимые дни

Расчет должен учитывать только дни, которые сейчас отображаются после переключателей `+/- Mo`, `+/- Di` и т.д.

День считать скрытым, если выполняется хотя бы одно условие:

- существует кнопка `.toggle-day-button.active[data-day="<day>"]`;
- в соответствующей таблице все заголовки дня `th.day-<day>` фактически скрыты через `display: none`;
- в соответствующей таблице все ячейки дня `td.day-<day>` фактически скрыты через `display: none`.

День считать видимым, если он не скрыт указанными механизмами.

В текущей логике день скрывается/отображается целиком. Частичное скрытие отдельных колонок одного дня не является целевым сценарием этой задачи. Если из-за будущих изменений окажется, что часть колонок дня видима, а часть скрыта, считать день видимым, если в контейнере есть хотя бы один видимый заголовок или ячейка этого дня.

### 4.3. Учитываются фильтры типов занятий

При расчете compact-диапазона учитывать только блоки занятий, которые не скрыты текущим фильтром типов занятий.

Блоки с классом `.lesson-type-filter-hidden` не должны влиять на расчет верхней и нижней границы.

Пример: если включен фильтр “только индивидуальные”, групповые занятия не должны удерживать таблицу раскрытой по вертикали.

### 4.4. Учитываются только `.activity-block`

Для расчета занятости использовать только блоки занятий `.activity-block`.

Не анализировать:

- содержимое ячеек таблицы;
- текстовые метки времени;
- служебные элементы;
- кнопки добавления/удаления колонок;
- подсветку ячеек;
- декоративные элементы;
- элементы backup/restore UI;
- search overlay;
- lock/edit overlay.

### 4.5. Скрываются только пустые строки сверху и снизу

Нельзя скрывать пустые промежутки внутри диапазона между первым и последним видимым занятием.

Пример: если в здании есть видимые занятия `09:00–11:00` и `17:00–18:00`, таблица должна показывать весь диапазон от начала первого занятия до конца последнего занятия с учетом отступов. Промежуток `11:00–17:00` должен остаться видимым.

## 5. Алгоритм расчета диапазона

### 5.1. Базовые определения

Для каждого здания собрать все “учитываемые блоки”.

Блок учитывается, если:

1. он находится внутри текущего `.schedule-container`;
2. его `data-day` относится к видимому дню;
3. он не имеет класса `.lesson-type-filter-hidden`;
4. он не скрыт напрямую через `display: none` из-за скрытого дня;
5. он имеет валидные координаты строк.

Координаты строк:

```js
startRow = parseInt(block.getAttribute('data-start-row'), 10);
rowSpan = parseInt(block.getAttribute('data-row-span'), 10);
endRow = startRow + rowSpan;
```

`endRow` — это первая строка после занятого интервала.

### 5.2. Карта строк таблицы

Для каждой таблицы построить `rowMap`:

- пройти по `.schedule-grid tbody tr`;
- для каждой строки найти первый `td[data-row]`;
- прочитать `rowIndex = parseInt(td.getAttribute('data-row'), 10)`;
- сохранить соответствие `rowIndex -> tr`.

`maxRow` — максимальный существующий `rowIndex` в `rowMap`.

Если `rowMap` пустой или `maxRow` не определен, для этого контейнера использовать fail-open: удалить compact-классы, скрыть note, вызвать позиционирование.

### 5.3. Валидные координаты блока

Координаты блока считаются валидными, если:

- `startRow` — конечное число;
- `rowSpan` — конечное число;
- `startRow >= 0`;
- `rowSpan > 0`;
- `endRow > startRow`;
- `startRow <= maxRow`;
- `endRow <= maxRow + 1`.

`endRow === maxRow + 1` допустим: это означает, что блок заканчивается сразу после последней строки сетки.

Если у блока отсутствуют `data-start-row` или `data-row-span`, можно использовать существующие fallback-функции из `position.js`, если они доступны. Если координаты все равно не удалось определить, используется fail-open для этого здания.

### 5.4. Блок за пределами сетки

Этот пункт относится к обычному режиму просмотра после загрузки/restore/sync или к любому случаю поврежденных runtime-атрибутов, а не к активному edit mode. В edit mode compact rows отключен и строки раскрыты.

Если видимый и учитываемый блок имеет координаты за пределами сетки:

- `startRow < 0`;
- `startRow > maxRow`;
- `rowSpan <= 0`;
- `endRow > maxRow + 1`;
- координаты не являются числами;
- невозможно надежно определить `startRow` или `rowSpan`,

то для соответствующего здания нужно применить fail-open: показать все строки, скрыть compact-note, вывести `console.warn` с указанием блока и причины.

Не нужно пытаться “умно” зажимать такие блоки в границы таблицы, кроме случая `endRow === maxRow + 1`, который считается валидным. Безопасность отображения важнее compact-эффекта.

### 5.5. Отступы

Использовать константу:

```js
COMPACT_ROW_PADDING = 3;
```

Это означает три пустые временные строки до первого занятия и три пустые строки после последнего занятия, если такие строки существуют в сетке.

Верхняя граница:

```js
firstVisibleRow = Math.max(0, minStartRow - COMPACT_ROW_PADDING);
```

Нижняя граница:

```js
lastVisibleRow = Math.min(maxRow, maxEndRow + COMPACT_ROW_PADDING - 1);
```

Здесь `maxEndRow` — максимальный `startRow + rowSpan` среди учитываемых блоков. Так как `maxEndRow` является первой строкой после последнего занятого интервала, `+ COMPACT_ROW_PADDING - 1` оставляет ровно три пустые строки после блока.

Пример при `timeInterval = 5`:

- первое занятие начинается в 14:30;
- `COMPACT_ROW_PADDING = 3`;
- таблица начинается с 14:15.

Пример для нижней границы:

- последнее занятие заканчивается в 18:00;
- при `timeInterval = 5` остаются видимыми три пустые строки после занятия: 18:00, 18:05, 18:10;
- длинный пустой хвост до 20:00 скрывается.

### 5.6. Строки для скрытия

Для каждой строки таблицы определить ее `rowIndex` через `td[data-row]` внутри этой строки.

Скрывать строку, если:

```js
rowIndex < firstVisibleRow || rowIndex > lastVisibleRow
```

Не скрывать `thead`; заголовок таблицы должен оставаться видимым.

Не скрывать/показывать отдельные ячейки дней напрямую. Новая логика должна управлять только строками `tbody tr` через собственный CSS-класс.

## 6. Поведение при отсутствии учитываемых занятий

Если для здания нет ни одного учитываемого блока, таблицу нельзя скрывать полностью.

В этом случае нужно показывать минимальный диапазон строк и комментарий.

### 6.1. Минимальный диапазон

Использовать константу:

```js
COMPACT_EMPTY_MINUTES = 60;
```

Если нет учитываемых блоков, показывать первые строки сетки от `gridStart` примерно на один час:

```js
emptyRowsToShow = Math.max(1, Math.ceil(COMPACT_EMPTY_MINUTES / timeInterval));
firstVisibleRow = 0;
lastVisibleRow = Math.min(maxRow, emptyRowsToShow - 1);
```

Если фактическая сетка короче одного часа, показывать всю доступную сетку.

### 6.2. Сообщение

Для здания без учитываемых занятий показывать отдельное ненавязчивое сообщение около соответствующей таблицы.

Предпочтительное размещение:

- сразу перед соответствующим `.schedule-container`;
- после заголовка `h2` здания, если он находится непосредственно перед контейнером;
- один note-элемент на один `.schedule-container`.

Текст для обычного отсутствия занятий:

```text
Нет занятий для выбранных дней и текущего фильтра в здании Villa.
```

Если скрыты все дни:

```text
Все дни скрыты для здания Villa.
```

Требования к сообщению:

- показывается всем ролям: `viewer`, `organizer`, `editor`, `admin`;
- появляется только когда compact rows активен;
- не появляется при активном поиске;
- не появляется при активном edit mode;
- не появляется при активном add-mode;
- обновляется при переключении дней и фильтров;
- имеет `aria-live="polite"`;
- не дублируется при повторных `refresh()`;
- не сохраняется как server state;
- не отправляется на сервер;
- скрывается, а не обязательно удаляется, когда сообщение больше не нужно.

## 7. Условия временного отключения autocompact

Новое автоскрытие должно учитывать приоритеты состояний.

### 7.1. Активный поиск

Если поиск по расписанию активен, compact rows полностью отключается.

Активность поиска определять через существующий API, если он доступен:

```js
window.ScheduleSearch &&
typeof window.ScheduleSearch.isActive === 'function' &&
window.ScheduleSearch.isActive()
```

При активном поиске:

- удалить все классы `.schedgen-compact-hidden-row`;
- скрыть compact-note сообщения;
- не применять compact-диапазон;
- дать `static/schedule_search_ui.js` самостоятельно управлять видимостью строк/колонок;
- после снятия поиска снова пересчитать compact-диапазоны;
- не добавлять классы, конкурирующие с `.schedgen-search-*`.

### 7.2. Активный edit mode

Если пользователь перешел в режим редактирования, все временные строки должны быть раскрыты.

Edit mode определять через существующий API, если он доступен:

```js
window.SchedGenAuthUI &&
typeof window.SchedGenAuthUI.isEditMode === 'function' &&
window.SchedGenAuthUI.isEditMode()
```

При активном edit mode:

- удалить compact-классы со строк;
- скрыть compact-note сообщения;
- не применять compact-диапазон;
- оставить скрытыми дни, которые пользователь скрыл кнопками `+/- Mo`, `+/- Di`;
- не раскрывать скрытые колонки/дни;
- не менять серверное состояние;
- не отправлять события на сервер;
- не влиять на другие браузеры/машины пользователей.

При выходе из edit mode compact-диапазон должен быть пересчитан заново, если поиск не активен.

### 7.3. Активный add-mode `#toggle-add-mode`

Если оператор включил режим быстрого добавления через кнопку `#toggle-add-mode`, все временные строки должны быть раскрыты.

Активность add-mode определять локально по кнопке:

```js
document.getElementById('toggle-add-mode')?.classList.contains('active')
```

При активном add-mode применяются те же правила, что и при edit mode: compact-классы снимаются, сообщения скрываются, скрытые дни остаются скрытыми.

При выключении add-mode compact-диапазон должен пересчитаться заново, если поиск и edit mode не активны.

### 7.4. Drag/drop и vertical resize

Во время активного drag/drop или vertical resize нельзя пересчитывать compact-диапазон на каждом движении мыши.

Требования:

- при старте drag/drop или resize не должно происходить схлопывания/разворачивания строк под курсором;
- изменения `data-start-row`, `data-row-span`, `data-day`, `data-col-index` во время движения мыши не должны немедленно вызывать compact-refresh;
- `MutationObserver` должен откладывать refresh, пока идет взаимодействие;
- финальный `ScheduleCompactRows.refresh()` выполняется только после drop/mouseup;
- если после завершения действия edit mode или add-mode все еще активен, `refresh()` должен вести себя как `clear()`, то есть строки остаются раскрытыми;
- если compact снова активен, пересчет выполняется один раз после завершения действия.

Рекомендуемый API для интеграции:

```js
window.ScheduleCompactRows.pauseForInteraction('drag');
window.ScheduleCompactRows.resumeAfterInteraction('drag', { refresh: true });

window.ScheduleCompactRows.pauseForInteraction('resize');
window.ScheduleCompactRows.resumeAfterInteraction('resize', { refresh: true });
```

Если реализатор выберет другой API, он должен обеспечить тот же результат: никаких compact-пересчетов во время движения, один безопасный пересчет после завершения.

### 7.5. Приоритеты состояний

Приоритеты:

1. активный поиск — compact rows отключен;
2. активный edit mode — compact rows отключен;
3. активный add-mode — compact rows отключен;
4. активный drag/drop или resize — compact-refresh откладывается до завершения;
5. обычный режим — compact rows включен.

Если несколько состояний активны одновременно, выигрывает более высокий приоритет. Например, при активном поиске и edit mode строки раскрыты, а поиск не получает конкурирующих compact-классов.

## 8. Прокрутка после применения compact-диапазона

После успешного применения compact-диапазона в обычном режиме нужно прокрутить соответствующий контейнер к началу видимого диапазона.

Требования:

- после скрытия верхних строк `container.scrollTop` должен быть установлен в `0`, если `.schedule-container` является scroll-контейнером;
- если скролл находится не на самом `.schedule-container`, а на вложенном/родительском элементе, использовать фактический scroll-контейнер текущей таблицы;
- не прокручивать всю страницу без необходимости;
- не дергать прокрутку при активном поиске, edit mode или add-mode;
- не дергать прокрутку при fail-open, если compact-диапазон не применен;
- прокрутку выполнять после применения классов строк и перед/после `updateActivityPositions()` так, чтобы итоговые позиции блоков были корректными;
- при повторном `refresh()` без изменения диапазона не нужно постоянно сбрасывать scrollTop, чтобы не раздражать пользователя.

Рекомендуемая стратегия:

- хранить на контейнере последний примененный диапазон, например `data-compact-first-row` и `data-compact-last-row` или внутренний `WeakMap`;
- сбрасывать scrollTop только если диапазон изменился или compact включился после disabled-состояния.

## 9. Fail-open поведение и edge cases

Безопасность отображения важнее компактности.

### 9.1. Невалидные координаты видимого блока

Если в здании есть блок, который должен учитываться по дню и фильтру, но его координаты строк не удалось определить или они невалидны, для этого здания нужно временно отключить compact rows и показать полную таблицу.

Нужно вывести `console.warn` с указанием:

- здания;
- дня;
- блока;
- причины fail-open.

Нельзя скрывать строки в контейнере, если есть риск скрыть видимое занятие из-за битых `data-start-row`/`data-row-span`.

### 9.2. Все дни скрыты

Если пользователь скрыл все дни:

- таблица не должна полностью исчезать;
- показывается минимальный диапазон строк;
- показывается сообщение `Все дни скрыты для здания ...`;
- кнопки дней остаются доступными, чтобы пользователь мог снова раскрыть день.

### 9.3. В одном здании занятий нет, в другом есть

Каждое здание обрабатывается независимо.

Если в `Villa` нет учитываемых занятий, а в `Kolibri` есть, `Villa` показывает минимальный диапазон и сообщение, а `Kolibri` показывает рассчитанный compact-диапазон.

### 9.4. Внутренние пустоты не скрывать

Даже если между занятиями большой перерыв, строки внутри рассчитанного диапазона остаются видимыми.

### 9.5. Роли пользователей

Compact rows работает для всех ролей в обычном режиме просмотра:

- `viewer`;
- `organizer`;
- `editor`;
- `admin`.

Если у роли нет кнопки `#toggle-add-mode`, состояние add-mode считается выключенным. Если роль не может войти в edit mode, edit mode считается выключенным.

### 9.6. Локальность состояния

Включение edit mode или add-mode одним пользователем в одном браузере не должно раскрывать строки у других пользователей и не должно записываться на сервер.

### 9.7. Excel-экспорт

Excel-экспорт должен оставаться полным и не зависеть от визуально скрытых строк.

Новая логика не должна:

- удалять строки из DOM;
- удалять или скрывать `.activity-block`;
- менять `data-start-row`, `data-row-span`, `data-day`, `data-building`, `data-col-index`;
- менять `collectScheduleData()` так, чтобы экспорт стал зависеть от compact-отображения;
- добавлять server-side фильтрацию строк.

Допустимо оставить compact CSS-классы на строках во время Excel-экспорта, если это не влияет на собираемые данные. Если при тестировании выяснится, что какой-либо экспортный сценарий зависит от геометрии строк, перед экспортом нужно временно вызвать `ScheduleCompactRows.clear({ updatePositions: true })`, выполнить экспорт и затем восстановить compact-режим через `ScheduleCompactRows.refresh()`.

### 9.8. Backup/restore

Compact rows не должен менять backup/restore.

Требования совместимости:

- backup создается из persisted server state, а не из текущего DOM браузера;
- compact classes и compact notes не должны попадать в backup как runtime-состояние;
- restore после hard reload должен приводить к обычной инициализации compact rows;
- если restore mode active и frontend показывает overlay, compact rows не должен мешать overlay;
- никаких новых backup/restore endpoints для compact rows не требуется.

## 10. Новый JS-модуль

Добавить новый модуль:

```text
gear_xls/js_modules/compact_rows.js
```

Модуль должен экспортировать глобальный объект:

```js
window.ScheduleCompactRows = {
  init: initCompactRows,
  refresh: refreshCompactRows,
  clear: clearCompactRows,
  isSuspended: isCompactRowsSuspended,
  pauseForInteraction: pauseForInteraction,
  resumeAfterInteraction: resumeAfterInteraction
};
```

Также экспортировать глобальную функцию для совместимости с текущим стилем проекта:

```js
window.initCompactRows = initCompactRows;
```

`prepareForSerialization()` в этой версии не требуется, потому что старый standalone save flow удален. Не добавлять новую зависимость от `save_export.js`.

## 11. CSS-классы

Модуль должен использовать собственные классы, не пересекающиеся с поиском:

```css
.schedgen-compact-hidden-row {
  display: none !important;
}

.schedgen-compact-empty-note {
  margin: 8px 0;
  padding: 8px 10px;
  font-size: 13px;
  border-radius: 6px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  color: #5d4a00;
}

.schedgen-compact-empty-note.is-hidden {
  display: none !important;
}
```

CSS можно внедрить через `compact_rows.js` один раз, чтобы функциональность работала и в сгенерированном `schedule.html`, и в веб-версии `/schedule`.

Не использовать классы поиска `.schedgen-search-*`.

## 12. Подключение модуля

### 12.1. `gear_xls/html_javascript.py`

Добавить `compact_rows` в список JS-модулей и обязательно вставить его содержимое в итоговый inline JS.

Недостаточно только добавить имя в список: нужно также добавить соответствующий `{js_modules.get('compact_rows', '')}` в шаблон формирования `full_js`.

Рекомендуемый порядок:

- после `position`, потому что нужен `updateActivityPositions()` и возможные fallback-функции;
- после `lesson_type_filter`, потому что нужно учитывать `.lesson-type-filter-hidden`;
- до `app_initialization`, чтобы `initializeApplication()` мог вызвать `initCompactRows()`.

Практически в текущей структуре:

```python
add_blocks_module_names = [
    ...
    'lesson_type_filter',
    'compact_rows',
    'block_content_sync',
    ...
    'app_initialization'
]
```

И в `full_js` рядом с подключением `lesson_type_filter`:

```python
{js_modules.get('lesson_type_filter', '')}

{js_modules.get('compact_rows', '')}

{js_modules.get('block_content_sync', '')}
```

### 12.2. `gear_xls/js_modules/app_initialization.js`

Вызвать compact init после инициализации фильтра типов занятий:

```js
if (typeof initLessonTypeFilter === 'function') {
    initLessonTypeFilter();
}
if (typeof initCompactRows === 'function') {
    initCompactRows();
}
```

После первичной инициализации должен произойти первичный расчет compact-диапазонов и позиционирование блоков.

Если `initCompactRows()` сам вызывает `updateActivityPositions()`, существующий финальный `updateActivityPositions()` в `initializeApplication()` можно оставить, но лучше избежать лишнего двойного позиционирования, если это просто сделать безопасно.

`initCompactRows()` должен быть идемпотентным: повторный вызов не должен создавать второй observer, вторые стили и дубли note-элементов.

## 13. Точки обновления

Compact-диапазон должен пересчитываться после событий, которые меняют видимость, набор учитываемых блоков или их координаты.

Обязательные точки:

1. переключение дня в `window.toggleDay(btn, dayCode)`;
2. применение фильтра типов занятий в `applyLessonTypeFilter(filterValue)`;
3. вход/выход из edit mode в `static/auth_ui.js` или в том месте, где вызывается `window.SchedGenAuthUI.setEditMode(...)`;
4. включение/выключение `#toggle-add-mode`;
5. добавление блока;
6. удаление блока;
7. завершение drag/drop блока;
8. завершение vertical resize блока;
9. изменение времени/длительности блока через editing UI;
10. обновление индивидуальных занятий из `static/individual_ui.js`;
11. обновление базового расписания из `static/base_sync_ui.js`;
12. активация/деактивация поиска в `static/schedule_search_ui.js`;
13. hard reload после restore, через обычную инициализацию страницы.

Рекомендуется сочетать явные вызовы `ScheduleCompactRows.refresh()` в уже существующих местах с `MutationObserver`, который подстрахует динамические изменения `.activity-block`.

## 14. Изменения в существующих файлах

### 14.1. `js_modules/core.js`

После изменения видимости дня вызвать compact refresh.

Рекомендуемая логика:

```js
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function') {
    window.ScheduleCompactRows.refresh();
} else if (typeof window.updateActivityPositions === 'function') {
    window.updateActivityPositions();
}
```

Если оставить существующий `updateActivityPositions()` перед `refresh()`, это допустимо, но приведет к лишнему позиционированию. Предпочтительно, чтобы `refresh()` сам вызывал `updateActivityPositions()` после изменения строк.

### 14.2. `js_modules/lesson_type_filter.js`

В конце `applyLessonTypeFilter(filterValue)` после добавления/удаления `.lesson-type-filter-hidden` вызвать:

```js
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function') {
    window.ScheduleCompactRows.refresh();
} else if (typeof window.updateActivityPositions === 'function') {
    window.updateActivityPositions();
}
```

Так как `initLessonTypeFilter()` может применить фильтр до `initCompactRows()`, вызов должен быть безопасным: если `ScheduleCompactRows` еще не существует, fallback — обычное позиционирование.

### 14.3. `js_modules/quick_add_mode.js`

После изменения класса `.active` у `#toggle-add-mode` вызвать `ScheduleCompactRows.refresh()`.

Сам `compact_rows.js` также должен уметь обнаружить состояние кнопки по DOM, чтобы не зависеть от локальной переменной add-mode.

### 14.4. `static/auth_ui.js`

После входа в edit mode и после выхода из edit mode уведомлять compact rows.

Рекомендуемый вызов:

```js
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function') {
    window.ScheduleCompactRows.refresh();
}
```

При входе в edit mode `refresh()` должен раскрыть строки через `clear()`. При выходе из edit mode `refresh()` должен пересчитать compact-диапазон, если поиск и add-mode не активны.

### 14.5. Drag/drop modules

В местах старта drag/drop вызвать pause, в местах завершения drop вызвать resume с refresh.

Рекомендуемо:

```js
window.ScheduleCompactRows?.pauseForInteraction?.('drag');
```

После финального drop, после записи `data-day`, `data-col-index`, `data-start-row` и после sync текста/конфликтов:

```js
window.ScheduleCompactRows?.resumeAfterInteraction?.('drag', { refresh: true });
```

Если optional chaining нежелателен из-за поддержки старых браузеров, использовать обычные guards.

Не пересчитывать compact rows внутри mousemove/dragover.

### 14.6. `js_modules/block_resize.js`

Во время resize можно продолжать вызывать `updateActivityPositions()` для текущего блока, но нельзя пересчитывать compact-диапазон до mouseup.

На старте resize:

```js
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.pauseForInteraction === 'function') {
    window.ScheduleCompactRows.pauseForInteraction('resize');
}
```

В `handleResizeMouseUp`, после финального обновления `data-row-span`, sync текста и конфликтов:

```js
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.resumeAfterInteraction === 'function') {
    window.ScheduleCompactRows.resumeAfterInteraction('resize', { refresh: true });
} else if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function') {
    window.ScheduleCompactRows.refresh();
}
```

### 14.7. `static/schedule_search_ui.js`

Нужно уведомлять compact rows при изменении активности поиска.

Предпочтительно вызывать refresh только при переходах:

- `inactive -> active`;
- `active -> inactive`.

Например в месте, где обновляется `data-search-active` или body-класс поиска:

```js
if (active !== previousActive && window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function') {
    window.ScheduleCompactRows.refresh();
}
```

При `ScheduleSearch.isActive() === true` метод `ScheduleCompactRows.refresh()` должен вести себя как `clear()`.

### 14.8. `static/base_sync_ui.js`

После применения server base schedule data, добавления/удаления групповых блоков и reapply фильтра вызвать compact refresh.

Важно: если код уже вызывает `reapplyLessonTypeFilter()`, а `applyLessonTypeFilter()` уже вызывает compact refresh, не нужно делать два refresh подряд. Можно использовать debounce внутри `compact_rows.js`, чтобы лишние вызовы схлопывались.

### 14.9. `static/individual_ui.js`

После применения индивидуального слоя, добавления/удаления individual/nachhilfe/trial блоков и reapply фильтра вызвать compact refresh.

Если `notifySearchScheduleMutation()` уже вызывается, это не заменяет compact refresh, потому что поиск и compact rows имеют разные задачи.

### 14.10. `js_modules/export_to_excel.js`

Не менять сбор данных экспорта под compact rows.

Если тесты покажут, что экспорт зависит от геометрии видимых строк, использовать временную очистку compact rows вокруг операции экспорта:

```js
var compactWasPresent = window.ScheduleCompactRows && typeof window.ScheduleCompactRows.refresh === 'function';
if (window.ScheduleCompactRows && typeof window.ScheduleCompactRows.clear === 'function') {
    window.ScheduleCompactRows.clear({ updatePositions: true });
}
try {
    // existing export flow
} finally {
    if (compactWasPresent) {
        window.ScheduleCompactRows.refresh();
    }
}
```

Но это нужно только если реально обнаружится проблема. По умолчанию export должен продолжать читать `.activity-block` и их data-атрибуты.

## 15. MutationObserver

В `compact_rows.js` можно создать `MutationObserver`, который наблюдает за изменениями внутри `.schedule-container` или `document.body`.

Отслеживать:

- добавление/удаление `.activity-block`;
- изменения атрибутов `.activity-block`:
  - `data-day`;
  - `data-building`;
  - `data-start-row`;
  - `data-row-span`;
  - `data-lesson-type`;
  - `data-col-index`;
  - `style`, только если это нужно для обнаружения скрытия дня через `display:none`.

Не наблюдать глобально за `class` всех элементов, чтобы собственное добавление `.schedgen-compact-hidden-row` не вызывало циклы. Изменения `.lesson-type-filter-hidden` лучше покрыть явным вызовом из `applyLessonTypeFilter()`.

Observer должен:

- использовать debounce через `requestAnimationFrame`;
- не запускать refresh во время `pauseForInteraction()`;
- ставить флаг pending refresh, если изменения пришли во время drag/resize;
- выполнять один refresh после `resumeAfterInteraction(..., { refresh: true })`;
- не реагировать на собственные compact-note изменения.

## 16. Детали реализации `compact_rows.js`

### 16.1. Suspended state

```js
function isCompactRowsSuspended() {
  return isSearchActive() || isEditModeActive() || isAddModeActive();
}
```

### 16.2. Псевдокод refresh

```js
function refreshCompactRows(options) {
  options = options || {};

  if (interactionPauseCount > 0 && !options.force) {
    pendingRefresh = true;
    return;
  }

  clearCompactRows({ updatePositions: false, keepNotes: false });

  if (isCompactRowsSuspended()) {
    hideAllEmptyNotes();
    updatePositionsSoon();
    return;
  }

  document.querySelectorAll('.schedule-container[data-building]').forEach(function(container) {
    applyCompactRowsToContainer(container);
  });

  updatePositionsSoon();
}
```

### 16.3. Применение к контейнеру

```js
function applyCompactRowsToContainer(container) {
  var table = container.querySelector('.schedule-grid');
  var rowMap = collectRowMap(table);
  var maxRow = getMaxRow(rowMap);
  var visibleDays = collectVisibleDays(container);

  if (!table || !rowMap.size || maxRow == null) {
    failOpenContainer(container, 'No row map');
    return;
  }

  if (!visibleDays.length) {
    applyEmptyRange(container, rowMap, maxRow, 'Все дни скрыты для здания ' + getBuildingName(container) + '.');
    return;
  }

  var result = collectConsideredBlocks(container, visibleDays, maxRow);

  if (result.hasInvalidVisibleBlock) {
    failOpenContainer(container, result.reason || 'Invalid visible block coordinates');
    return;
  }

  if (!result.blocks.length) {
    applyEmptyRange(container, rowMap, maxRow, 'Нет занятий для выбранных дней и текущего фильтра в здании ' + getBuildingName(container) + '.');
    return;
  }

  var minStartRow = Math.min.apply(null, result.blocks.map(function(b) { return b.startRow; }));
  var maxEndRow = Math.max.apply(null, result.blocks.map(function(b) { return b.endRow; }));

  var firstVisibleRow = Math.max(0, minStartRow - COMPACT_ROW_PADDING);
  var lastVisibleRow = Math.min(maxRow, maxEndRow + COMPACT_ROW_PADDING - 1);

  applyRange(container, rowMap, firstVisibleRow, lastVisibleRow);
  hideEmptyNote(container);
  scrollContainerToCompactStartIfRangeChanged(container, firstVisibleRow, lastVisibleRow);
}
```

### 16.4. Очистка

`clearCompactRows()` должен удалять `.schedgen-compact-hidden-row` со всех строк и скрывать служебные сообщения.

Не должен трогать:

- `.schedgen-search-hidden-row`;
- `.lesson-type-filter-hidden`;
- inline `style.display` у дней;
- `.activity-block`;
- данные расписания;
- backup/restore UI;
- lock/edit UI.

### 16.5. Позиционирование

После любого изменения видимости строк нужно вызвать `window.updateActivityPositions()`.

Рекомендуемо делать это через debounce:

```js
function updatePositionsSoon() {
  if (positionRaf) return;
  positionRaf = requestAnimationFrame(function() {
    positionRaf = 0;
    if (typeof window.updateActivityPositions === 'function') {
      window.updateActivityPositions();
    }
  });
}
```

## 17. Нефункциональные требования

1. Производительность: пересчет должен быть быстрым даже при большом количестве строк и блоков. Использовать один проход по строкам и блокам на контейнер, без тяжелых вложенных DOM-запросов в циклах по каждой ячейке.
2. Идемпотентность: повторный вызов `refresh()` без изменений не должен менять результат и не должен накапливать классы/сообщения.
3. Отсутствие гонок: собственные изменения классов строк не должны приводить к бесконечному циклу `MutationObserver`.
4. Совместимость: код должен работать, если `window.ScheduleSearch` отсутствует, если `window.SchedGenAuthUI` отсутствует, если `#toggle-add-mode` отсутствует, если есть только одно здание, если у здания нет блоков.
5. Клиентская локальность: никаких запросов на сервер, никаких записей в storage, cookies или JSON-файлы.
6. Доступность: сообщения о пустых выборках должны быть читаемыми и не должны ломать клавиатурную навигацию.
7. Визуальная стабильность: не удалять строки из DOM, только управлять CSS-классом `display:none`.
8. Безопасность отображения: при неуверенности показывать больше строк, а не меньше.
9. Совместимость с backup/restore: не возвращать старые standalone save flows.

## 18. Критерии приемки

### 18.1. Один видимый день, позднее начало

Дано:

- виден только `Mo`;
- в `Villa` первое видимое занятие начинается в 14:30;
- до 14:30 в `Villa` нет видимых занятий.

Ожидаемо:

- таблица `Villa` начинается с 14:15 при `timeInterval = 5`;
- строки до 14:15 скрыты классом `.schedgen-compact-hidden-row`;
- блоки занятий позиционируются корректно;
- `Kolibri` рассчитывается независимо.

### 18.2. Несколько видимых дней

Дано:

- видны `Mo` и `Di`;
- в `Mo` первое занятие в `Villa` начинается в 14:30;
- в `Di` первое занятие в `Villa` начинается в 13:00.

Ожидаемо:

- базовая верхняя граница выбирается по `Di` — 13:00;
- с учетом трех строк отступа при `timeInterval = 5` таблица начинается с 12:45.

### 18.3. Нижняя граница

Дано:

- последнее видимое занятие в здании заканчивается в 18:00;
- после 18:00 до конца сетки занятий нет.

Ожидаемо:

- длинный хвост до конца сетки скрыт;
- при `timeInterval = 5` остаются три пустые строки после занятия: 18:00, 18:05, 18:10;
- внутренние пустые промежутки между занятиями не скрываются.

### 18.4. Фильтр типов занятий

Дано:

- включен фильтр “только индивидуальные”;
- групповые занятия начинаются в 09:00;
- индивидуальные занятия начинаются в 13:00.

Ожидаемо:

- расчет верхней границы идет по индивидуальным занятиям;
- групповые блоки с `.lesson-type-filter-hidden` не удерживают таблицу раскрытой.

### 18.5. Search active

Дано:

- compact rows активен;
- пользователь вводит запрос в поиск расписания.

Ожидаемо:

- классы compact rows снимаются;
- compact-note сообщения скрываются;
- строками управляет только поиск;
- после очистки поиска compact rows снова применяется.

### 18.6. Edit mode active

Дано:

- compact rows скрыл верхние/нижние строки;
- пользователь входит в edit mode через существующую lock/auth UI.

Ожидаемо:

- все временные строки немедленно становятся видимыми;
- скрытые дни остаются скрытыми;
- compact-note сообщения скрываются;
- при выходе из edit mode compact-диапазон пересчитывается заново;
- это не влияет на другие браузеры/пользователей.

### 18.7. Add-mode active

Дано:

- compact rows скрыл верхние/нижние строки;
- оператор нажимает `#toggle-add-mode`.

Ожидаемо:

- все временные строки немедленно становятся видимыми;
- скрытые дни остаются скрытыми;
- при повторном нажатии `#toggle-add-mode` compact-диапазон пересчитывается заново, если edit mode не активен;
- это не влияет на другие браузеры/пользователей.

### 18.8. Drag/drop и resize

Дано:

- пользователь перетаскивает или растягивает блок;
- во время действия меняются координаты блока.

Ожидаемо:

- строки не схлопываются и не раскрываются под курсором во время движения;
- compact-refresh выполняется только после завершения drop/mouseup;
- если edit mode все еще активен, строки остаются раскрытыми;
- после выхода из edit mode compact-диапазон применяется корректно.

### 18.9. Нет занятий

Дано:

- для `Villa` нет учитываемых занятий в выбранных днях и текущем фильтре.

Ожидаемо:

- таблица `Villa` не исчезает полностью;
- показывается минимальный диапазон около одного часа от начала сетки;
- отображается сообщение `Нет занятий для выбранных дней и текущего фильтра в здании Villa.`;
- сообщение видно всем ролям;
- при search/edit/add-mode сообщение скрывается и строки раскрываются.

### 18.10. Все дни скрыты

Дано:

- пользователь скрыл все дни.

Ожидаемо:

- таблицы не ломаются;
- показывается минимальный диапазон строк;
- отображается сообщение `Все дни скрыты для здания ...`;
- кнопки дней остаются доступны для обратного раскрытия.

### 18.11. Невалидный блок

Дано:

- в видимом дне есть `.activity-block` без валидных `data-start-row`/`data-row-span`;
- fallback не смог определить координаты.

Ожидаемо:

- для этого здания показывается полная таблица;
- compact-note скрыт;
- в консоли есть предупреждение;
- занятие не скрывается случайно.

### 18.12. Блок выходит за пределы сетки

Дано:

- в обычном режиме просмотра есть видимый блок с `endRow > maxRow + 1` или `startRow > maxRow`.

Ожидаемо:

- для этого здания используется fail-open;
- все строки здания видимы;
- в консоли есть предупреждение;
- не применяется сомнительное зажатие координат.

### 18.13. Прокрутка

Дано:

- compact rows применил новый диапазон;
- до первого видимого занятия были скрыты верхние строки.

Ожидаемо:

- scroll-контейнер таблицы прокручен к началу видимого диапазона;
- при повторном refresh без изменения диапазона прокрутка не сбрасывается постоянно.

### 18.14. Excel export

Ожидаемо:

- Excel-экспорт содержит полное расписание;
- экспорт не зависит от визуально скрытых строк;
- `.activity-block` и их data-атрибуты не меняются compact rows.

### 18.15. Backup/restore

Ожидаемо:

- compact rows не меняет backup/restore API;
- старые `save_export.js`/`outerHTML` требования не возвращаются;
- после restore и hard reload compact rows работает как при обычной загрузке;
- backup ZIP не зависит от runtime compact-состояния текущей вкладки.

## 19. Что не входит в задачу

Не нужно:

- скрывать пустые промежутки внутри дня между занятиями;
- менять серверные API;
- менять формат `base_schedule.json` или `individual_lessons.json`;
- менять backup ZIP format;
- менять restore flow;
- менять алгоритмы генерации расписания;
- возвращать standalone HTML save flow;
- добавлять `save_export.js`;
- добавлять `prepareForSerialization()` ради старого `outerHTML`;
- менять Excel-экспорт, кроме возможной безопасной временной очистки compact rows, если тесты покажут необходимость;
- сохранять пользовательскую настройку compact rows;
- добавлять серверную настройку включения/выключения compact rows;
- менять семантику кнопок дней;
- раскрывать скрытые дни при search/edit/add-mode;
- отправлять compact-события на сервер.

## 20. Рекомендуемый порядок реализации

1. Добавить `gear_xls/js_modules/compact_rows.js` с базовым API, CSS injection, `refresh()`, `clear()`, suspended-state logic.
2. Подключить `compact_rows` в `html_javascript.py`: добавить в список модулей и в фактическую inline-вставку `full_js`.
3. Добавить вызов `initCompactRows()` в `app_initialization.js` после `initLessonTypeFilter()`.
4. Реализовать расчет `rowMap`, visible days, considered blocks, padding, empty range, fail-open.
5. Реализовать compact-note элементы рядом с каждым `.schedule-container`.
6. Реализовать scroll-to-start при изменении compact-диапазона.
7. Добавить явные refresh-вызовы в `core.js`, `lesson_type_filter.js`, `quick_add_mode.js`, `auth_ui.js`, `schedule_search_ui.js`, `base_sync_ui.js`, `individual_ui.js`.
8. Добавить pause/resume для drag/drop и vertical resize; убедиться, что refresh не идет во время mousemove.
9. Добавить `MutationObserver` как страховку для добавления/удаления/изменения `.activity-block`.
10. Проверить Excel export; при необходимости временно очищать compact rows вокруг export.
11. Перегенерировать или вручную обновить `gear_xls/html_output/schedule.html`, если проект требует актуального generated HTML в поставке.
12. Пройти manual regression checklist.

## 21. Grep/ручные проверки после реализации

Проверить наличие нового модуля и подключения:

```bash
rg -n "compact_rows|ScheduleCompactRows|initCompactRows" gear_xls
```

Ожидаемо:

- есть `gear_xls/js_modules/compact_rows.js`;
- есть подключение в `html_javascript.py`;
- есть вызов в `app_initialization.js`;
- есть refresh-интеграции в нужных frontend-модулях.

Проверить, что старый save flow не возвращен:

```bash
rg -n "save_export|saveSchedule|saveIntermediate|/save_intermediate|final_schedule\.html|intermediate_schedule\.html|document\.documentElement\.outerHTML" gear_xls
```

Ожидаемо:

- нет новых активных зависимостей compact rows от старого save flow;
- допустимы только тесты/комментарии backup/restore, если они уже были в проекте для проверки удаления старых артефактов.

Проверить, что compact rows не пишет на сервер:

```bash
rg -n "ScheduleCompactRows.*fetch|fetch\(.*compact|localStorage.*compact|sessionStorage.*compact" gear_xls
```

Ожидаемо:

- нет сетевых запросов или storage-записей, связанных с compact rows.

## 22. Итоговое ожидаемое состояние

После реализации веб-расписание автоматически становится компактнее по вертикали в обычном режиме просмотра:

- пустые строки до первого видимого занятия скрываются;
- пустые строки после последнего видимого занятия скрываются;
- расчет выполняется отдельно для каждого здания;
- расчет учитывает видимые дни и фильтры занятий;
- внутренние пустые промежутки не скрываются;
- поиск, edit mode и add-mode временно отключают compact rows;
- drag/drop и resize не вызывают пересчеты во время движения;
- после применения диапазона контейнер прокручивается к началу видимой области;
- таблица не исчезает полностью при отсутствии занятий;
- сообщения о пустой выборке видны всем ролям;
- Excel-экспорт, backup/restore и server state остаются корректными и полными.
