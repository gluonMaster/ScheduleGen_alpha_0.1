# SchedGen Project Memory

Last updated: 2026-03-19

## Active Work

- The multiuser web editor is implemented across all 5 phases, but the work is still uncommitted.
- Current stage: prolonged manual browser QA and hardening after the initial implementation.
- Main focus now: continue fixing issues found during manual verification, then make a clean commit.
- Related summary: `memory/project_multiuser_spec.md`

## Current QA Status

- Authentication, roles, locking, publish flow, individual lessons CRUD, and rooms report are already implemented.
- A security pass was completed and the main issues were fixed:
  - `spiski` API now uses same-origin relative URLs and is protected by login.
  - `/export_to_excel` is protected by `login_required + role_required("admin")`.
  - Origin validation was added for mutating requests as a CSRF-style safeguard.
  - `SESSION_COOKIE_SAMESITE = "Lax"` and `SESSION_COOKIE_HTTPONLY = True` are set.
  - Flask no longer runs with `debug=True`.
- Layout and UX fixes already applied:
  - the top black nav no longer overlaps the editor controls;
  - the old separate mode bar was removed and its controls were moved into the top nav;
  - the extra main schedule title row was removed to save vertical space.
- `/rooms` was extended:
  - an optional event duration filter was added;
  - search now works even if room/building are not specified;
  - the report shows only intervals large enough for the requested duration when duration is set.
- Non-group lessons (`individual` / `nachhilfe`) are now shown in the web editor even when they originally came from `optimized_schedule.xlsx`.
- Manual QA also uncovered several runtime regressions, and they were fixed:
  - non-group block edit persistence after logout/login;
  - non-group drag and resize persistence;
  - group drag/drop and resize in admin edit mode;
  - fallback publish collector when old inline `collectScheduleData()` is unavailable;
  - warning guard when leaving `/schedule` with unpublished group changes.

## Important Current Behavior

- Group lessons and non-group lessons are persisted differently.
- Group lessons live in the published base layer:
  - source of truth after publish: `gear_xls/schedule_state/base_schedule.json`;
  - admin can edit them in the browser;
  - changes survive reload/logout only after explicit `Publish`.
- Non-group lessons live in their own autosaved layer:
  - source of truth: `gear_xls/schedule_state/individual_lessons.json`;
  - editor/admin changes are saved immediately through the API;
  - drag/drop, resize, create, delete, and dialog edit should persist without publish.
- This distinction is by design and must be preserved unless the spec changes.

## Key Architecture Notes

### Roles

- `alla` / `admin`: full access, including publish and group lesson editing.
- `valentina` / `editor`: edits only non-group lessons, can use the rooms report.
- `olesya` / `viewer`: read-only schedule view plus the rooms report.

### Server / State

- Flask serves the schedule via `/schedule`; this is not a `file://` workflow anymore.
- Main backend modules:
  - `gear_xls/server_routes.py`
  - `gear_xls/auth.py`
  - `gear_xls/lock_manager.py`
  - `gear_xls/state_manager.py`
  - `gear_xls/base_schedule_manager.py`
  - `gear_xls/rooms_routes.py`
  - `gear_xls/rooms_report.py`
- Main frontend/runtime modules:
  - `gear_xls/static/auth_ui.js`
  - `gear_xls/static/lock_ui.js`
  - `gear_xls/static/base_sync_ui.js`
  - `gear_xls/static/individual_ui.js`
  - `gear_xls/static/rooms_report.js`
  - `gear_xls/static/nav.css`

### Locking

- Edit lock is stored in `gear_xls/schedule_state/lock.json`.
- Heartbeat is active while the lock holder stays in edit mode.
- Admin can force release the lock.
- A reload while already holding the lock should restart heartbeat correctly.

### Base vs Individual Layers

- `gear_xls/schedule_state/base_schedule.json` stores the published base schedule.
- `gear_xls/schedule_state/individual_lessons.json` stores autosaved non-group lessons.
- `base_schedule.json` is authoritative for published group lessons.
- `individual_lessons.json` is authoritative for non-group lessons after initialization.

### Safe Bootstrap of Non-Group Lessons

- `schedule.html` may contain embedded `individual` / `nachhilfe` blocks generated from `optimized_schedule.xlsx`.
- A safe one-time bootstrap was added in `gear_xls/state_manager.py`:
  - import embedded non-group blocks into `individual_lessons.json` only if the individual state is still pristine;
  - do not import if `individual_lessons.json` already has user edits;
  - do not import after the base layer has already been published.
- This rule exists specifically to avoid overwriting later manual edits by other users.

### Publish / Navigation Guard

- Unpublished group edits are intentionally local until `Publish`.
- Because of that, navigation guards were added:
  - warn on logout if there are unpublished group changes;
  - warn on top-nav transitions such as `/schedule -> /rooms`;
  - browser `beforeunload` uses the native unsaved-changes prompt.

## What Was Recently Fixed During Manual QA

- Security and config:
  - hardcoded `127.0.0.1` API usage removed from `spiski` frontend calls;
  - origin checks added for mutating requests;
  - export route access tightened;
  - `debug=False`.
- Editor layout:
  - sticky offsets of nav / lock banner / update banner were synchronized;
  - editor mode controls moved into the top nav;
  - vertical space usage improved.
- `/rooms`:
  - duration-aware free-slot filtering was added.
- Non-group lesson runtime:
  - existing blocks now bind reliably to their persistent `data-block-id`;
  - drag/drop persists;
  - resize persists;
  - dialog edits persist across logout/login.
- Group lesson runtime:
  - drag/drop and resize were restored for published base blocks in admin mode;
  - DOM metadata is re-synced after move/resize/edit;
  - cursor hints for editable blocks were restored;
  - leaving the page with unpublished base edits now triggers a warning.

## Planned / Future SPECs

- `SPEC-trial-lesson` is still not implemented.
- Expected semantics:
  - "expired" means visual marking (`trial-expired`), not automatic deletion;
  - preferred storage is a separate `trial_date` column in the Excel `Schedule` sheet;
  - UI would be a double-click dialog for non-group blocks.

## User / Project Preferences

- Do not change the existing color scheme logic for groups in `color_service.py` unless explicitly requested.
- Keep changes to `app_actions.py` minimal.
- Prompt/spec language is Russian.
- Prompts should stay self-contained and explicitly state what is already done and what remains.
