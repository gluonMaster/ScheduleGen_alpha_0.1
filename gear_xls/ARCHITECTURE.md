# gear_xls — Interactive Schedule Editor

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
  ├── html_table_generator.py      (time grid, day columns, row labels)
  └── html_block_generator.py      (lesson block elements with data attributes)
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
| `html_javascript.py` | JS module orchestration/injection | 185 |
| `server_routes.py` | Flask: POST `/export_to_excel` | 120 |
| `excel_exporter.py` | Writes edited schedule back to Excel | 284 |
| `convert_to_xlsm.py` | Converts .xlsx → .xlsm + injects VBA macro | 167 |
| `utils.py` | Shared utilities | 301 |

### generators/ (modular HTML generation)
| File | Role | Lines |
|------|------|-------|
| `html_coordinator.py` | Orchestrates all generators | 274 |
| `html_structure_generator.py` | Document structure, meta, script tags | 206 |
| `html_table_generator.py` | Time grid, day headers, row structure | 236 |
| `html_block_generator.py` | Lesson block `<div>` elements | 361 |

### services/
| File | Role | Lines |
|------|------|-------|
| `schedule_pipeline.py` | Excel → Structure → HTML pipeline | 174 |
| `color_service.py` | Color assignment per subject/group | 378 |

## JavaScript Modules (js_modules/, 21 files)

| File | Role |
|------|------|
| `core.js` | App state, globals |
| `drag_drop_service.js` | Drag-and-drop of lesson blocks |
| `block_drop_service.js` | Drop target logic, collision detection |
| `grid_snap_service.js` | Snapping to time grid |
| `building_service.js` | Building/room management |
| `block_utils.js` | Block data extraction |
| `add_blocks_main.js` | UI for adding new lessons |
| `block_creation_dialog.js` | Dialog for new lesson creation |
| `block_positioning.js` | Absolute positioning calculations |
| `block_event_handlers.js` | Click, double-click handlers |
| `quick_add_mode.js` | Rapid lesson entry mode |
| `editing_update.js` | Edit-in-place updates |
| `delete_blocks.js` | Block deletion logic |
| `delete_blocks_observer.js` | MutationObserver for deletion tracking |
| `save_export.js` | Save state, trigger export |
| `export_to_excel.js` | Client-side Excel export (27KB — complex) |
| `settings_panel.js` | Settings UI |
| `color_utils.js` | Color manipulation |
| `adaptive_text_color.js` | Contrast-aware text color |
| `position.js` | Position utilities |
| `app_initialization.js` | Bootstrap on page load |

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
