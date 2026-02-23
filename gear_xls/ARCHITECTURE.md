# gear_xls — Interactive Schedule Editor

## ⚠️ Breaking Changes (Phase 5 — cell-anchor positioning refactor)

- **`settings_panel.js` removed** — the compensation settings panel (gear icon, bottom-right corner) has been deleted entirely. No compensation system remains.
- **Compensation system fully removed** — `horizontalCompensation`, `compensationK`, `compensationB`, and all `Math.pow` compensation formulas are gone. `data-original-top` and `data-compensated` attributes are no longer set; any legacy occurrences are stripped with `removeAttribute`.
- **`position.js` rewritten** — `updateActivityPositions()` now positions blocks by calling `getBoundingClientRect()` on anchor cells (`td[data-row][data-col]`) instead of summing `<th>` widths. Two new backward-compat helpers added: `deriveStartRowFromBlock()` and `deriveRowSpanFromBlock()`.
- **New block data attributes** — every `.activity-block` div now carries `data-start-row` and `data-row-span`. These are emitted by `html_block_generator.py` at generation time and kept up-to-date by all drag/drop/add code paths.
- **`gridStart` JS global added** — `html_javascript.py` now accepts a `grid_start` parameter and emits `var gridStart = N;` (minutes since midnight) before all module code. Propagation chain: `html_coordinator.py → html_structure_generator.py → html_javascript.py`.

---

## Purpose
Web-based drag-and-drop schedule editor. User selects a Schedule Excel file, edits it visually in a browser, and exports changes back to Excel.

## Entry Point
`gear_xls/main.py` — Tkinter file selector dialog → launches Flask server → opens browser

## Data Pipeline
```
Excel (Schedule sheet, English headers)
  ↓
excel_parser.py  (ScheduleExcelParser)
  reads columns A-I: subject, group, teacher, room, building, day, start_time, end_time, duration
  ↓
schedule_structure.py  (ScheduleStructure)
  hierarchical model: days → teachers → lessons
  ↓
services/schedule_pipeline.py  (pipeline orchestration)
  ↓
html_generator.py  → generators/html_coordinator.py
  ├── html_structure_generator.py  (document skeleton, CSS includes)
  │     calls get_javascript(..., grid_start=N) → emits var gridStart = N
  ├── html_table_generator.py      (time grid, day columns, row labels)
  │     emits td[data-row][data-col] on every grid cell
  └── html_block_generator.py      (lesson block elements with data-start-row, data-row-span)
  ↓
HTML file (opened in browser via webbrowser.open)
  ↓
  [User edits: drag, resize, add, delete blocks]
  ↓
Flask POST /export_to_excel  (server_routes.py)
  ↓
excel_exporter.py  (ScheduleExcelExporter)
  ↓
Excel (Schedule sheet, ⚠️ Russian headers — see Critical Issue)
```

## Key Modules

| File | Role | Lines |
|------|------|-------|
| `main.py` | Entry: Tkinter file picker, server startup | 250 |
| `integration.py` | High-level: file load → HTML → server | 285 |
| `excel_parser.py` | Reads Schedule sheet (positional cols A–I) | 189 |
| `schedule_structure.py` | Hierarchical schedule data model | 169 |
| `html_generator.py` | HTML generation facade | 313 |
| `html_styles.py` | CSS generation | 205 |
| `html_javascript.py` | JS module orchestration/injection; accepts `grid_start` param, emits `var gridStart = N` | 185 |
| `server_routes.py` | Flask: POST `/export_to_excel` | 120 |
| `excel_exporter.py` | Writes edited schedule back to Excel | 284 |
| `convert_to_xlsm.py` | Converts .xlsx → .xlsm + injects VBA macro | 167 |
| `utils.py` | Shared utilities | 301 |

### generators/ (modular HTML generation)
| File | Role | Lines |
|------|------|-------|
| `html_coordinator.py` | Orchestrates all generators; determines `grid_start`/`grid_end` from building data | 274 |
| `html_structure_generator.py` | Document structure, meta, script tags; passes `grid_start` to `get_javascript()` | 206 |
| `html_table_generator.py` | Time grid, day headers, row structure; emits `td[data-row][data-col]` on every cell | 236 |
| `html_block_generator.py` | Lesson block `<div>` elements; emits `data-start-row` and `data-row-span` on every block | 361 |

### services/
| File | Role | Lines |
|------|------|-------|
| `schedule_pipeline.py` | Excel → Structure → HTML pipeline | 174 |
| `color_service.py` | Color assignment per subject/group | 378 |

## JavaScript Modules (js_modules/, 22 files)

### Root modules
| File | Role |
|------|------|
| `core.js` | App state, globals (`toggleDay` calls `updateActivityPositions` after show/hide) |
| `position.js` | **Cell-anchor positioning**: `updateActivityPositions()` uses `getBoundingClientRect()` on `td[data-row][data-col]` anchor cells; backward-compat helpers `deriveStartRowFromBlock()` and `deriveRowSpanFromBlock()` |
| `drag_drop_refactored.js` | Top-level drag-and-drop controller |
| `block_positioning.js` | `positionNewBlock()` sets `data-start-row`/`data-row-span` then calls `updateActivityPositions()`; strips any legacy `data-original-top`/`data-compensated` attributes |
| `block_event_handlers.js` | Click, double-click handlers |
| `block_utils.js` | Block data extraction |
| `block_creation_dialog.js` | Dialog for new lesson creation |
| `add_blocks_main.js` | UI for adding new lessons |
| `quick_add_mode.js` | Rapid lesson entry mode |
| `editing_update.js` | Edit-in-place updates |
| `delete_blocks.js` | Block deletion logic |
| `delete_blocks_observer.js` | MutationObserver for deletion tracking |
| `save_export.js` | Save state, trigger export |
| `export_to_excel.js` | Client-side Excel export; primary time source is block text; fallback uses `gridStart + startRow * timeInterval` from `data-start-row`/`data-row-span` (replaces old `data-original-top` formula) |
| `column_helpers.js` | Column management across multiple buildings |
| `conflict_detector.js` | Detects and highlights scheduling conflicts |
| `color_utils.js` | Color manipulation |
| `adaptive_text_color.js` | Contrast-aware text color |
| `app_initialization.js` | Bootstrap on page load |

### services/ sub-modules
| File | Role |
|------|------|
| `services/building_service.js` | Building/room management |
| `services/drag_drop_service.js` | Drag-and-drop of lesson blocks |
| `services/grid_snap_service.js` | Snapping to time grid; `snapToClosestCell()` sets `data-start-row` during drag |
| `services/block_drop_service.js` | Drop target logic, collision detection; `updateBlockPositionData()` sets `data-start-row` on drop, strips `data-original-top`/`data-compensated` |

## JS Globals

The following variables are emitted by `html_javascript.py` inside `DOMContentLoaded` before any module code runs:

| Variable | Type | Source | Description |
|----------|------|--------|-------------|
| `gridCellHeight` | number | `html_javascript.py` | Height of one time-grid cell in pixels |
| `dayCellWidth` | number | `html_javascript.py` | Width of one day column in pixels |
| `headerHeight` | number | `html_javascript.py` | Height of the table header in pixels |
| `daysOrder` | array | `html_javascript.py` | Ordered list of active day codes |
| `timeInterval` | number | `html_javascript.py` | Minutes per grid row |
| `borderWidth` | number | `html_javascript.py` | Cell border width in pixels |
| `gridStart` | number | `html_javascript.py` (via `grid_start` param) | Grid start time in minutes since midnight (e.g. 540 = 09:00) |
| `measuredTimeColWidth` | number | `html_javascript.py` | Measured width of time column (set at runtime) |
| `editDialogOpen` | boolean | `html_javascript.py` | Global dialog state guard |
| `draggedBlock` | element\|null | `html_javascript.py` | Currently dragged block reference |

`gridStart` propagation chain:
```
html_coordinator.py._determine_grid_bounds()
  → grid_start value
  → html_coordinator.py.generate_complete_schedule()
  → html_structure_generator.py.generate_document_head(grid_start=N)
  → html_javascript.py.get_javascript(..., grid_start=N)
  → emits: var gridStart = N;
```

## Block Data Attributes

Every `.activity-block` div carries the following data attributes. All are set at generation time by `html_block_generator.py` and kept current by JS on every drag, drop, or add operation.

| Attribute | Set by (Python) | Kept current by (JS) | Meaning |
|-----------|-----------------|----------------------|---------|
| `data-day` | `html_block_generator.py` | drag/drop services, `editing_update.js` | Day code (e.g. `Mo`) |
| `data-col-index` | `html_block_generator.py` | `block_drop_service.js`, `grid_snap_service.js` | 0-based column index within the day |
| `data-building` | `html_block_generator.py` | — | Building identifier |
| `data-start-row` | `html_block_generator.py` | `block_positioning.js`, `block_drop_service.js`, `grid_snap_service.js`, `position.js` (backward-compat fallback) | 0-based row index from `gridStart` (= `(startMinutes - gridStart) / timeInterval`) |
| `data-row-span` | `html_block_generator.py` | `block_positioning.js`, `position.js` (backward-compat fallback) | Number of grid rows spanned (= `durationMinutes / timeInterval`) |

`data-start-row` and `data-row-span` are the single source of truth for `updateActivityPositions()`. If either is absent on a legacy HTML file, `deriveStartRowFromBlock()` / `deriveRowSpanFromBlock()` compute the values from the block's time text and write them back.

## Positioning Architecture (Phase 5)

`updateActivityPositions()` in `position.js` uses a cell-anchor approach:

1. For each `.activity-block`, read `data-start-row`, `data-row-span`, `data-day`, `data-col-index`.
2. Query the anchor cell: `td.day-{day}[data-col="{col}"][data-row="{startRow}"]`.
3. Call `getBoundingClientRect()` on the anchor cell and on the end-boundary cell (`data-row = startRow + rowSpan`).
4. Convert viewport-relative coordinates to container-relative (accounting for scroll, border).
5. Set `block.style.left/top/width/height` directly.

This replaces the previous approach of summing `<th>` widths and applying polynomial compensation formulas. No compensation constants (`compensationK`, `compensationB`) exist in the codebase.

## ⚠️ Critical Contract Issue

| Direction | Headers |
|-----------|---------|
| **Input** (from Schedule sheet) | **English**: `subject, group, teacher, room, building, day, start_time, end_time, duration, pause_before, pause_after` |
| **Output** (exported back to Excel) | **Russian**: uses Russian column names |

This incompatibility means gear_xls exports cannot be directly fed into `visualiser/` without header translation.
**Do not silently "fix" this** — it may affect downstream processing. See PROJECT_MAP.md for full context.

## Dependencies
- Flask (web server)
- pandas, openpyxl (Excel I/O)
- pdfkit (HTML → PDF, requires wkhtmltopdf installed separately)
- win32com (VBA macro injection — Windows only)
- webbrowser (standard library, opens browser)

## Artifacts
- `gear_xls/html_output/` — generated HTML files (gitignored)
- `gear_xls/excel_exports/` — exported Excel files (gitignored)
- `gear_xls/pdfs/` — generated PDFs (gitignored)
- `gear_xls/Modul1.bas` — VBA macro source for Plannung generation
