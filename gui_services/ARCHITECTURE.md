# gui_services — Tkinter GUI Service Layer

## Purpose
Orchestrates all SchedGen subsystems through a Tkinter GUI.
Separates UI construction from business logic using a service-based architecture.

## Entry Point
`gui.py` (project root) → creates main `ApplicationInterface` → delegates everything to `gui_services/`

## Module Responsibilities

| File | Role | Lines |
|------|------|-------|
| `app_actions.py` | **Central business logic controller** | 651 |
| `ui_builder.py` | Tkinter component factory | 124 |
| `process_manager.py` | Subprocess launch + monitoring | 166 |
| `file_manager.py` | Cross-platform file operations | 74 |
| `logger.py` | Logging to Tkinter Text widget | 28 |
| `__init__.py` | Module exports | 18 |

## AppActions — Central Controller

`app_actions.py` is the most important file. It orchestrates all user actions:

1. **File selection** — validates Plannung Excel, sets working paths
2. **Optimizer launch** — runs `main_sch.py` via subprocess, captures output
3. **Visualization launch** — runs `schedule_visualizer_enhanced.py` via subprocess
4. **Web editor launch** — runs `gear_xls/main.py` via subprocess
5. **Artifact copying** — copies PDF/HTML to OneDrive if configured
6. **Error handling** — all user-facing errors and status messages

## Subprocess Architecture
All subsystems run as **separate subprocess calls** (not imported as modules):
```
gui.py  →  AppActions
               ↓
           ProcessManager.run(main_sch.py, [args])          → optimizer
           ProcessManager.run(schedule_visualizer_enhanced.py, [args])  → visualizer
           ProcessManager.run(gear_xls/main.py, [args])     → web editor
```

This design:
- Isolates crashes (a visualizer crash doesn't kill the GUI)
- Allows stdout/stderr capture for the log widget
- Enables progress indication via output monitoring

## UI Structure

```
gui.py (ApplicationInterface)
  ↓
UIBuilder (ui_builder.py)
  constructs:
  ├── File selection area (Entry + Browse button)
  ├── Action buttons (Optimize, Visualize, Open Editor, ...)
  ├── Progress indicators
  └── Log Text widget (receives Logger output)
```

All Tkinter widget creation is delegated to `UIBuilder`.
`AppActions` only calls `UIBuilder.build_*()` — never creates widgets directly.

## Logger
`logger.py` — thin wrapper that writes to a Tkinter `Text` widget.
Not related to Python's `logging` module.
Used by AppActions to display status messages to the user.

## File Manager
`file_manager.py` — cross-platform file operations:
- Path normalization for Windows/Mac
- File existence checks with proper error messages
- Handles long Windows paths

## Data Flow (GUI perspective)
```
User selects Excel file (Plannung)
  ↓ AppActions.on_file_selected()
  ↓ AppActions.run_optimizer()
      ProcessManager runs main_sch.py → writes optimized_schedule.xlsx to visualiser/
  ↓ AppActions.run_visualizer()
      ProcessManager runs schedule_visualizer_enhanced.py → writes PDF + HTML
  ↓ AppActions.copy_artifacts()
      FileManager copies PDF + HTML to OneDrive (if auto_copy_enabled)
```

## Error Handling Pattern
```python
try:
    result = self.process_manager.run(...)
    if result.returncode != 0:
        self.logger.error(f"Process failed: {result.stderr}")
except FileNotFoundError:
    self.logger.error("Executable not found: ...")
```

All errors go through `Logger` → displayed in the GUI text widget.
No silent failures.

## See Also
- `MIGRATION.md` — migration notes from previous architecture
- `README.md` — quick reference for service usage
