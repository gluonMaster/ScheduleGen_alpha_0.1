# SchedGen PreRelease - Project Structure Map

> Auto-generated: 2026-02-17

## Overview

**SchedGen** - редактор/генератор школьного расписания на базе constraint programming (Google OR-Tools CP-SAT).

Система решает задачу оптимального распределения занятий по дням, временным слотам и аудиториям с учётом ограничений (преподаватели, группы, помещения, связанные цепочки уроков, временные окна). Результат визуализируется в виде интерактивного HTML-приложения с drag-and-drop, PDF и Excel.

**Стек:** Python 3, OR-Tools, pandas, openpyxl, Tkinter, Flask, ReportLab, pdfkit, matplotlib

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          gui.py (Tkinter)                           │
│                     ApplicationInterface                            │
│  Кнопки: Оптимизация | Веб-приложение | Визуализация | Настройки    │
└────────┬──────────────────┬──────────────────┬──────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   ┌───────────┐    ┌──────────────┐   ┌──────────────────┐
   │ main_sch  │    │  gear_xls/   │   │  visualiser/     │
   │ (solver)  │    │  (web-app)   │   │  visualiserTV/   │
   └─────┬─────┘    └──────┬───────┘   │  (PDF export)    │
         │                 │           └──────────────────┘
         ▼                 ▼
   ┌───────────┐    ┌──────────────┐
   │ Excel out │    │ HTML + Flask │
   │ (results) │    │ (editor)     │
   └───────────┘    └──────────────┘
```

---

## Root-Level Modules

### Entry Points

| File              | Lines | Purpose                                                                                         |
| ----------------- | ----- | ----------------------------------------------------------------------------------------------- |
| `gui.py`          | 99    | **Главная точка входа.** Tkinter GUI, оркестрирует все операции через gui_services              |
| `main_sch.py`     | 175   | **CLI-точка входа оптимизатора.** Загрузка Excel -> модель CP-SAT -> решение -> экспорт в Excel |
| `config.json`     | 5     | Конфигурация (путь копирования в OneDrive, флаг auto_copy)                                      |
| `start_flask.bat` | -     | Запуск Flask-сервера для gear_xls                                                               |

### Solver Core (CP-SAT Optimization)

| File                               | Lines | Purpose                                                                                                                                                                                      |
| ---------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `reader.py`                        | 392   | **Чтение входных данных.** Парсит Excel (лист "Plannung"), создаёт объекты `ScheduleClass` с информацией о предмете, преподавателе, группах, аудиториях, временных окнах, связанных цепочках |
| `scheduler_base.py`                | 253   | **Ядро оптимизатора.** Класс `ScheduleOptimizer` — строит CP-SAT модель, создаёт переменные, добавляет ограничения, запускает решатель с лимитом времени                                     |
| `model_variables.py`               | 160   | Создание переменных модели: день, временной слот, аудитория (фиксированные и гибкие)                                                                                                         |
| `constraints.py`                   | 12    | Агрегатор — реэкспорт из linked/resource/time_conflict constraints                                                                                                                           |
| `linked_constraints.py`            | 96    | Ограничения для цепочек связанных уроков (последовательность на одном дне)                                                                                                                   |
| `resource_constraints.py`          | 194   | Ограничения ресурсов: запрет одновременного использования преподавателя/аудитории/группы                                                                                                     |
| `time_conflict_constraints.py`     | 306   | Сложные временные ограничения: фиксированное время, временные окна, их комбинации                                                                                                            |
| `time_constraint_utils.py`         | 159   | Утилиты для создания булевых переменных конфликтов и моделирования перекрытий                                                                                                                |
| `timewindow_adapter.py`            | 946   | **Самый большой модуль.** Продвинутая обработка временных окон: анализ связанных классов, поиск свободных слотов, целевая функция для окон                                                   |
| `objective.py`                     | 174   | Целевая функция: минимизация смены аудиторий и "окон" у преподавателей                                                                                                                       |
| `sequential_scheduling.py`         | 290   | Анализ возможности последовательного размещения классов (back-to-back)                                                                                                                       |
| `sequential_scheduling_checker.py` | 224   | Продвинутая верификация последовательного планирования, кэширование проверок                                                                                                                 |
| `conflict_detector.py`             | 217   | Пре-оптимизационный детектор конфликтов (преподаватели/аудитории/группы)                                                                                                                     |
| `time_utils.py`                    | 16    | `time_to_minutes()` / `minutes_to_time()` — конвертация времени                                                                                                                              |
| `output_utils.py`                  | 112   | Экспорт решения в Excel (листы по преподавателям/группам/аудиториям)                                                                                                                         |

### Legacy Visualization (matplotlib)

| File                     | Lines | Purpose                                                                    |
| ------------------------ | ----- | -------------------------------------------------------------------------- |
| `schedule_visualizer.py` | 188   | PDF-визуализация через matplotlib (цветные блоки расписания)               |
| `visualisation.py`       | 459   | Расширенная визуализация: виды по дню/преподавателю/группе/аудитории (PNG) |

### Testing

| File                 | Lines | Purpose                                                                        |
| -------------------- | ----- | ------------------------------------------------------------------------------ |
| `test_timewindow.py` | 244   | Диагностика временных окон, анализ возможностей последовательного планирования |

### Data

| Directory        | Contents                                                                        |
| ---------------- | ------------------------------------------------------------------------------- |
| `xlsx_initial/`  | Шаблоны: `schedule_planning.xlsx` (планирование), `newpref.xlsx` (предпочтения) |
| `excel_exports/` | Выходные Excel-файлы с решением                                                 |

---

## gui_services/ — Сервисы GUI

Пакет сервисов для Tkinter-интерфейса. Чистое разделение: gui.py — компоновщик, сервисы — исполнители.

| File                 | Lines | Purpose                                                                                                                                                     |
| -------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`        | 18    | Экспорт: UIBuilder, FileManager, ProcessManager, AppActions, Logger                                                                                         |
| `ui_builder.py`      | 124   | **Фабрика UI-компонентов.** Статические методы для создания окон, фреймов, кнопок (1/2/3 в ряд), лога, статусбара                                           |
| `app_actions.py`     | 651   | **Центральный контроллер.** Бизнес-логика: запуск оптимизатора, gear_xls, Flask, визуализатора; работа с Excel/XLSM/VBA макросами; управление конфигурацией |
| `file_manager.py`    | 74    | Кроссплатформенные файловые операции: открытие файлов, диалоги выбора, проверка существования                                                               |
| `process_manager.py` | 166   | Управление подпроцессами: запуск команд, терминалов, отслеживание состояния (Win/Mac/Linux)                                                                 |
| `logger.py`          | 28    | Логирование в текстовый виджет с таймштампами + обновление статусбара                                                                                       |

**Data Flow:** `Button Click -> AppActions.method() -> ProcessManager/FileManager -> Logger -> UI Update`

---

## gear_xls/ — Интерактивный HTML-редактор расписания

Конвертирует Excel-файл с результатами оптимизации в интерактивное веб-приложение с drag-and-drop редактированием, экспортом в Excel/PDF.

**Версия:** 1.1.0 | **~4500 строк Python + 21 JS-модуль**

### Data Flow

```
Excel File (Schedule sheet)
    │
    ▼
excel_parser.py ──► activities dict {id: {day, time, teacher, subject, room, building}}
    │
    ▼
schedule_structure.py ──► buildings dict {building: {day: [intervals], _grid, _rooms, _max_cols}}
    │
    ▼
HTMLCoordinator (generators/)
    ├── HTMLStructureGenerator (head, panels, containers)
    ├── HTMLTableGenerator (grid with time labels)
    └── HTMLBlockGenerator (positioned activity blocks)
    │
    + html_styles.py (CSS)
    + html_javascript.py (загрузка JS-модулей)
    │
    ▼
schedule.html (interactive web app)
    │
    ├──► Flask Server (server_routes.py) ──► Excel Export (excel_exporter.py)
    ├──► PDF Generation (pdf_generator.py via pdfkit/wkhtmltopdf)
    └──► Browser: drag-drop, create/edit/delete blocks, save, export
```

### Core Files

| File                    | Lines | Purpose                                                                            |
| ----------------------- | ----- | ---------------------------------------------------------------------------------- |
| `main.py`               | 250   | **Точка входа.** Tkinter GUI: выбор файла, валидация, запуск pipeline, старт Flask |
| `excel_parser.py`       | 189   | Парсинг Excel: извлечение предметов, групп, преподавателей, аудиторий, времени     |
| `schedule_structure.py` | 169   | Построение иерархической структуры building -> day -> room -> grid position        |
| `html_generator.py`     | 313   | Фасад HTML-генерации (обратная совместимость, делегирует в generators/)            |
| `html_styles.py`        | 205   | CSS: sticky headers, flexbox, responsive layout, цветовые схемы кнопок             |
| `html_javascript.py`    | 185   | Оркестрация загрузки 21 JS-модуля + инъекция глобальных переменных                 |
| `pdf_generator.py`      | 212   | PDF через pdfkit: A2 landscape, статичные таблицы по зданиям                       |
| `excel_exporter.py`     | 284   | Создание Excel из данных HTML-редактора (POST -> Flask -> openpyxl)                |
| `server_routes.py`      | 120   | Flask-сервер: POST /export-to-excel, CORS, CSRF-токен                              |
| `integration.py`        | 285   | Высокоуровневая интеграция: setup, pipeline, Flask-запуск, автооткрытие браузера   |
| `time_utils.py`         | 56    | Конвертация времени (отдельный модуль для избежания циклических импортов)          |
| `utils.py`              | 301   | Утилиты: сортировка аудиторий по этажам, обёртки цветов, валидация                 |
| `convert_to_xlsm.py`    | 167   | Конвертация XLSX -> XLSM с VBA-макросами (COM/win32com)                            |

### generators/ — Рефакторенная HTML-генерация

| File                          | Lines | Purpose                                                             |
| ----------------------------- | ----- | ------------------------------------------------------------------- |
| `__init__.py`                 | 121   | Пакет с lazy-loading и обратной совместимостью                      |
| `html_coordinator.py`         | 274   | Оркестратор: собирает полный HTML из трёх генераторов               |
| `html_structure_generator.py` | 206   | Структура документа: head, meta, control panel, CSRF-токен          |
| `html_table_generator.py`     | 236   | HTML-таблица сетки: заголовки дней, временные метки (каждые 15 мин) |
| `html_block_generator.py`     | 361   | Абсолютно позиционированные блоки занятий с CSS и data-атрибутами   |

### services/ — Сервисный слой

| File                   | Lines | Purpose                                                                             |
| ---------------------- | ----- | ----------------------------------------------------------------------------------- |
| `__init__.py`          | 18    | Экспорт сервисов                                                                    |
| `schedule_pipeline.py` | 174   | `SchedulePipeline` — оркестрация: parse -> structure -> HTML                        |
| `color_service.py`     | 378   | Цвета: MD5-хэш для групп, спец.категории (Schach, Tanz, Gitarre, Deutsch), контраст |

### js_modules/ — JavaScript клиентская часть (21 модуль)

| Category           | Modules                                                                                                                                                             | Purpose                                                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Services**       | building_service, drag_drop_service, grid_snap_service, block_drop_service                                                                                          | Сервисы: здания, D&D, привязка к сетке                      |
| **Core**           | core, position, column_helpers, color_utils, adaptive_text_color                                                                                                    | Ядро: позиционирование, колонки, цвета                      |
| **UI**             | settings_panel, save_export                                                                                                                                         | Настройки, сохранение                                       |
| **Features**       | add_blocks_main, block_creation_dialog, block_positioning, block_event_handlers, quick_add_mode, block_utils, editing_update, delete_blocks, delete_blocks_observer | Создание/редактирование/удаление блоков, быстрое добавление |
| **Initialization** | app_initialization                                                                                                                                                  | Инициализация приложения                                    |
| **Export**         | export_to_excel (27K)                                                                                                                                               | Экспорт в Excel через HTTP POST                             |

### Key Constants

| Constant       | Value | Description         |
| -------------- | ----- | ------------------- |
| TIME_INTERVAL  | 5 min | Гранулярность сетки |
| GRID_START     | 09:00 | Начало сетки        |
| GRID_END       | 19:45 | Конец сетки         |
| DAY_CELL_WIDTH | 100px | Ширина ячейки дня   |
| CELL_HEIGHT    | 15px  | Высота ячейки       |
| DAYS_ORDER     | Mo-Sa | Дни недели          |
| SERVER_PORT    | 5000  | Порт Flask          |

### Output Directories

| Directory          | Contents                     |
| ------------------ | ---------------------------- |
| `html_output/`     | Сгенерированные HTML-файлы   |
| `html_output/web/` | Веб-ресурсы                  |
| `excel_exports/`   | Экспортированные Excel-файлы |
| `pdfs/`            | Сгенерированные PDF          |

---

## visualiser/ — PDF-визуализация расписания (стандарт)

Генерация PDF-расписаний через ReportLab. Формат: A3 landscape для всех дней.

**Pipeline:** `Excel -> load_data() -> process_schedule_data() -> EnhancedScheduleLayout -> create_pdf() -> PDF`

| File                               | Lines | Purpose                                                                 |
| ---------------------------------- | ----- | ----------------------------------------------------------------------- |
| `schedule_visualizer_main.py`      | 100   | Базовая точка входа для PDF-генерации                                   |
| `schedule_visualizer_enhanced.py`  | 121   | **Расширенная точка входа.** `main()` с экспортом учителей, групп, HTML |
| `data_processor.py`                | 138   | Загрузка Excel (лист "Schedule"), парсинг времени, сортировка           |
| `config_manager.py`                | 242   | JSON/INI конфигурация с дефолтами и merge                               |
| `color_manager.py`                 | 147   | Цвета групп (RGB), цвета зданий (HSV через MD5), контраст текста        |
| `enhanced_layout_manager.py`       | 126   | Расчёт layout: фиксированные block_height=57, border=4.0, spacing=6     |
| `enhanced_layout_drawing.py`       | 163   | Отрисовка: `draw_schedule()` — все дни одним проходом                   |
| `enhanced_layout_rendering.py`     | 127   | Рендеринг блоков: `draw_lesson_block()`, скруглённые прямоугольники     |
| `enhanced_export_manager.py`       | 74    | Обёртка миксинов HTML и Extra экспорта                                  |
| `enhanced_export_manager_html.py`  | 492   | HTML-экспорт: responsive, dark mode, поиск                              |
| `enhanced_export_manager_extra.py` | 207   | PNG-экспорт (convert_from_path), ICS-экспорт                            |
| `group_exporter.py`                | 133   | Экспорт расписаний по группам (отдельные PDF)                           |
| `teacher_exporter.py`              | 133   | Экспорт расписаний по преподавателям (отдельные PDF)                    |
| `example_usage_enhanced.py`        | 47    | Пример использования                                                    |

### Output Directories

| Directory            | Contents              |
| -------------------- | --------------------- |
| `group_schedules/`   | PDF по группам        |
| `teacher_schedules/` | PDF по преподавателям |
| `SoftColors/`        | Цветовые ресурсы      |

---

## visualiserTV/ — PDF-визуализация для ТВ-дисплея

**Клон visualiser/** с адаптацией под TV-дисплей: двухстраничный PDF с разными размерами холста для будней и выходных.

### Отличия от visualiser/

| Aspect                   | visualiser            | visualiserTV                                 |
| ------------------------ | --------------------- | -------------------------------------------- |
| **Canvas**               | A3 landscape (единый) | 2325x2171px (будни) + A4 portrait (выходные) |
| **Block height**         | Фиксированный 57px    | Адаптивный по контексту                      |
| **Border width**         | 4.0                   | 6.0 (будни) / 4.0 (выходные)                 |
| **Block spacing**        | 6px                   | 10px (будни) / 6px (выходные)                |
| **Font sizing**          | height/6              | +30% будни / /2.3 выходные                   |
| **Teacher/Group export** | Да                    | Нет                                          |
| **HTML export**          | Опционально           | Обязательно                                  |

### Файлы с MAJOR различиями (остальные идентичны):

| File                              | visualiser | visualiserTV | What Changed                                                                     |
| --------------------------------- | ---------- | ------------ | -------------------------------------------------------------------------------- |
| `enhanced_layout_manager.py`      | 126        | 351          | Адаптивные размеры, отдельные расчёты для будней/выходных, динамические шрифты   |
| `enhanced_layout_drawing.py`      | 163        | 255          | `draw_weekday_schedule()`, `draw_weekend_schedule()`, `draw_schedule_for_days()` |
| `enhanced_layout_rendering.py`    | 127        | 169          | `is_weekday` параметр, адаптивные шрифты, вертикальное центрирование             |
| `schedule_visualizer_enhanced.py` | 121        | 198          | `create_pdf_v2()` — dual-canvas, только HTML-экспорт                             |

---

## Module Dependency Graph

```
gui.py
 ├── gui_services/*
 │    ├── app_actions.py ──► main_sch.py (subprocess)
 │    ├── app_actions.py ──► gear_xls/ (subprocess)
 │    ├── app_actions.py ──► visualiser/ (subprocess)
 │    └── app_actions.py ──► visualiserTV/ (subprocess)
 │
main_sch.py
 ├── reader.py (ScheduleReader, ScheduleClass)
 ├── scheduler_base.py (ScheduleOptimizer)
 │    ├── model_variables.py
 │    ├── constraints.py
 │    │    ├── linked_constraints.py
 │    │    ├── resource_constraints.py
 │    │    │    ├── conflict_detector.py
 │    │    │    ├── time_conflict_constraints.py
 │    │    │    └── time_utils.py
 │    │    └── time_conflict_constraints.py
 │    │         ├── time_utils.py
 │    │         ├── time_constraint_utils.py
 │    │         ├── sequential_scheduling.py
 │    │         └── sequential_scheduling_checker.py
 │    └── objective.py
 │         └── timewindow_adapter.py
 ├── output_utils.py
 └── timewindow_adapter.py
 │
gear_xls/main.py
 ├── services/schedule_pipeline.py
 │    ├── excel_parser.py
 │    ├── schedule_structure.py
 │    └── generators/html_coordinator.py
 │         ├── html_structure_generator.py
 │         ├── html_table_generator.py
 │         └── html_block_generator.py
 ├── html_generator.py (facade)
 ├── html_styles.py
 ├── html_javascript.py ──► js_modules/* (21 files)
 ├── pdf_generator.py
 ├── server_routes.py ──► excel_exporter.py
 └── services/color_service.py
```

---

## Summary Stats

| Module        | Python Files | JS Files | Total Lines (py) |
| ------------- | ------------ | -------- | ---------------- |
| Root (solver) | 18           | 0        | ~4,200           |
| gui_services/ | 6            | 0        | ~1,060           |
| gear_xls/     | 22           | 21       | ~4,500           |
| visualiser/   | 14           | 0        | ~2,400           |
| visualiserTV/ | 14           | 0        | ~2,800           |
| **Total**     | **74**       | **21**   | **~15,000**      |
