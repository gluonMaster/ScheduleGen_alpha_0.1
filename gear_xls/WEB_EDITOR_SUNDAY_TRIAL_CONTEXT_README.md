# Context bundle for WEB_EDITOR_SUNDAY_TRIAL_TZ.md

This archive contains the files most relevant for reviewing the Sunday (`So`) trial-lesson change.

## Included areas

- Mini-TZ / requirements:
  - `gear_xls/WEB_EDITOR_SUNDAY_TRIAL_TZ.md`

- Web editor day model and generated schedule grid:
  - `gear_xls/generators/html_coordinator.py`
  - `gear_xls/generators/html_structure_generator.py`
  - `gear_xls/generators/html_table_generator.py`
  - `gear_xls/html_javascript.py`
  - `gear_xls/schedule_structure.py`

- Web editor client-side behavior:
  - `gear_xls/js_modules/menu.js`
  - `gear_xls/js_modules/column_helpers.js`
  - `gear_xls/js_modules/core.js`
  - `gear_xls/js_modules/block_creation_dialog.js`
  - `gear_xls/js_modules/export_to_excel.js`
  - `gear_xls/js_modules/trial_ui.js`
  - `gear_xls/static/individual_ui.js`
  - `gear_xls/static/base_sync_ui.js`

- Server-side persistence, permissions, validation, backup/restore:
  - `gear_xls/server_routes.py`
  - `gear_xls/state_manager.py`
  - `gear_xls/backup_manager.py`
  - `gear_xls/base_schedule_manager.py`

- Export / generated output path:
  - `gear_xls/excel_exporter.py`
  - `gear_xls/pdf_generator.py`

- Final visualizer paths:
  - `visualiser/data_processor.py`
  - `visualiser/schedule_visualizer_enhanced.py`
  - `visualiser/enhanced_layout_manager.py`
  - `visualiser/enhanced_export_manager_html.py`
  - `visualiser/teacher_exporter.py`
  - `visualiser/group_exporter.py`
  - `visualiserTV/data_processor.py`
  - `visualiserTV/schedule_visualizer_enhanced.py`
  - `visualiserTV/enhanced_layout_manager.py`
  - `visualiserTV/enhanced_export_manager_html.py`
  - `visualiserTV/teacher_exporter.py`
  - `visualiserTV/group_exporter.py`

## Intentionally excluded

- `gear_xls/config/users.json` is not included because it contains password hashes and is not required for reviewing this change.
- Generated HTML output and runtime state files are not included to keep the bundle small and avoid stale generated data.
