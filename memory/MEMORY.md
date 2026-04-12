# SchedGen Project Memory

Last updated: 2026-04-12

## Active Work

- The multiuser web editor is implemented across all 5 phases, but the work is still uncommitted.
- Current stage: prolonged manual browser QA and hardening after the initial implementation.
- Main focus now: continue fixing issues found during manual verification, then make a clean commit.
- Related summary: `memory/project_multiuser_spec.md`
- Live search directly inside `/schedule` is now implemented and independently verified.
- The authoritative spec is `PROMPTS/SPEC-web-editor-live-search.md`.
- The phased implementation prompt set used for the feature:
  - `PROMPTS/Prompt-LiveSearch-Impl-00-Overview.md`
  - `PROMPTS/Prompt-LiveSearch-Impl-01-Generators-Scaffold.md`
  - `PROMPTS/Prompt-LiveSearch-Impl-02-Core-Search.md`
  - `PROMPTS/Prompt-LiveSearch-Impl-03-Compact-Layout.md`
  - `PROMPTS/Prompt-LiveSearch-Impl-04-Integration-QA.md`
- Verification artifacts:
  - `VERIFY_REPORT.md`
  - `CODEX_VERIFY_RESPONSE.md`

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
  - room search/autocomplete now uses the full deduplicated room list from `spiski/kabinets_Kolibri.txt` and `spiski/kabinets_Villa.txt`;
  - a room that exists in `spiski` but has no lessons is now reported as free, not as "room not found".
- Non-group lessons (`individual` / `nachhilfe`) are now shown in the web editor even when they originally came from `optimized_schedule.xlsx`.
- Manual QA also uncovered several runtime regressions, and they were fixed:
  - non-group block edit persistence after logout/login;
  - non-group drag and resize persistence;
  - group drag/drop and resize in admin edit mode;
  - fallback publish collector when old inline `collectScheduleData()` is unavailable;
  - warning guard when leaving `/schedule` with unpublished group changes.
  - `/schedule` now refreshes embedded `spiskiData` from the current `spiski/*.txt` files on every request, so newly added teachers/subjects/students survive the next login.
- Another manual-QA bug was fixed after this memory file was first written:
  - publishing while some days were hidden could lead to hidden-day blocks disappearing from the web editor after re-showing the day;
  - root cause: publish snapshotting and layer refresh interacted badly with `display:none` day hiding;
  - fix applied in:
    - `gear_xls/static/base_sync_ui.js`
    - `gear_xls/static/individual_ui.js`
    - `gear_xls/js_modules/export_to_excel.js`
  - important behavior now:
    - publish temporarily reveals hidden days while collecting the full schedule snapshot;
    - baseline/group snapshotting no longer drops hidden-day blocks;
    - re-rendered non-group blocks respect current hidden-day state.
- Live search was implemented after the original memory entry:
  - generator scaffold now exposes the metadata needed by search on blocks, headers, and cells;
  - `gear_xls/static/schedule_search_ui.js` provides search UI, DOM indexing, token matching, 4-level filtering, row compaction, hidden-day reveal, edit-mode interlock, and mutation reapply;
  - `gear_xls/static/auth_ui.js` exposes a dedicated nav mount slot and clears search before entering edit mode;
  - publish / export / save entry points reset active search before DOM serialization;
  - verification found no blockers.
- Follow-up cleanup after verification:
  - search status visibility no longer uses inline `style.display`; it now uses a dedicated CSS class;
  - redundant double search-reset in Excel export was removed while preserving safe direct-call behavior.

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
- `gear_xls/server_routes.py` runs Flask on `host=0.0.0.0` by default, so the app is reachable from other machines in the LAN if firewall/routing allow it.
- The web editor runtime itself uses same-origin relative URLs; browser-side schedule/editor calls do not depend on hardcoded `localhost`.
- The only remaining hardcoded local-open convenience path is in `gui_services/app_actions.py`, where the desktop GUI opens `http://localhost:5000/schedule` on the server machine.
- For stable LAN access, the preferred infrastructure setup is:
  - DHCP reservation for the server machine;
  - internal DNS `A` record such as `schedgen.company.local -> fixed server IP`;
  - clients then open the app by name instead of raw IP.
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
  - `gear_xls/static/schedule_search_ui.js`
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

### Generated vs Source Files

- `gear_xls/html_output/schedule.html` is a generated artifact, not the primary implementation target.
- Feature work should go into generators, route injection, JS modules, and CSS.
- It is acceptable to inspect `gear_xls/html_output/schedule.html` to understand the actual DOM shape, but final feature implementation should not rely on hand-editing that file.
- The new live-search spec explicitly requires this: after implementation, the user should regenerate the web editor and get the feature in the newly generated `schedule.html`.
- The local worktree may also contain transient/generated/runtime artifacts from QA, for example:
  - `gear_xls/html_output/schedule.html`
  - `gear_xls/schedule_state/*.json`
  - `visualiser/intermediate_schedule.html`
  - current `spiski/*.txt` edits
- These files should be reviewed carefully before any commit and should not automatically be treated as the intended source-level implementation of a feature.

### Safe Bootstrap of Non-Group Lessons

- `schedule.html` may contain embedded `individual` / `nachhilfe` blocks generated from `optimized_schedule.xlsx`.
- A safe one-time bootstrap was added in `gear_xls/state_manager.py`:
  - import embedded non-group blocks into `individual_lessons.json` only if the individual state is still pristine;
  - do not import if `individual_lessons.json` already has user edits;
  - do not import after the base layer has already been published.
- This rule exists specifically to avoid overwriting later manual edits by other users.
- Because of the separate runtime state layer, regenerating the web app from a new Excel file must also reset `gear_xls/schedule_state/base_schedule.json`, `gear_xls/schedule_state/individual_lessons.json`, and `gear_xls/schedule_state/lock.json`; otherwise old persisted model data can overlay the freshly generated HTML.

### Publish / Navigation Guard

- Unpublished group edits are intentionally local until `Publish`.
- Because of that, navigation guards were added:
  - warn on logout if there are unpublished group changes;
  - warn on top-nav transitions such as `/schedule -> /rooms`;
  - browser `beforeunload` uses the native unsaved-changes prompt.

### Notes For The Implemented Live Search

- The authoritative spec is `PROMPTS/SPEC-web-editor-live-search.md`.
- The feature is implemented in source modules/generators, not by hand-editing `gear_xls/html_output/schedule.html`.
- Main implementation files:
  - `gear_xls/static/schedule_search_ui.js`
  - `gear_xls/static/auth_ui.js`
  - `gear_xls/static/nav.css`
  - `gear_xls/static/base_sync_ui.js`
  - `gear_xls/static/individual_ui.js`
  - `gear_xls/generators/html_block_generator.py`
  - `gear_xls/generators/html_table_generator.py`
  - `gear_xls/js_modules/export_to_excel.js`
  - `gear_xls/js_modules/save_export.js`
  - `gear_xls/js_modules/column_helpers.js`
  - `gear_xls/js_modules/column_delete.js`
- Important technical findings confirmed during implementation/verification:
  - initial static group blocks in generated `schedule.html` do not reliably contain `data-room`, `data-start-time`, and `data-end-time`;
  - runtime search must therefore hydrate missing attrs or compute them with fallback logic from block text / row metadata;
  - vertical row collapsing cannot hide every non-covered row blindly:
    - `gear_xls/js_modules/position.js` computes block height using the cell at `endRow = startRow + rowSpan`;
    - therefore row-collapsing must preserve boundary `endRow` rows, otherwise visible blocks get incorrect heights;
  - search must be search-only UI state and must not leak into:
    - publish
    - Excel export
    - intermediate/final save
  - the spec requires automatic search reset before those actions, and this is now implemented.
- Verified behavior:
  - multi-token AND search with case-insensitive substring matching;
  - umlaut folding (`\u00E4/\u00F6/\u00FC/\u00DF`) plus Cyrillic-safe case folding with NFKC normalization;
  - 4-level filtering of blocks, columns, rows, and building sections;
  - hidden-day indexing plus temporary reveal of only matching columns/blocks;
  - edit-mode mutual exclusion;
  - DOM-serialization reset before publish/export/save.
- Verification result:
  - `VERIFY_REPORT.md` found no blockers and 4 non-blocking warnings;
  - `CODEX_VERIFY_RESPONSE.md` initially found one extra low-severity warning, then follow-up cleanup resolved it.
- Remaining low-risk caveats after cleanup:
  - row-derived time fallback still assumes `09:00` + `5 min` if `gridStart` / `timeInterval` globals are absent;
  - `isDayHidden()` still assumes the current one-button-per-day UI as its primary signal;
  - saved standalone HTML opened directly via `file://...` will not load `/static/schedule_search_ui.js`; it works only when the page is served over HTTP by the app or another server exposing the same `/static/...` paths.

## What Was Recently Fixed During Manual QA

- Security and config:
  - hardcoded `127.0.0.1` API usage removed from `spiski` frontend calls;
  - origin checks added for mutating requests;
  - export route access tightened;
  - `debug=False`;
  - GUI buttons `3.1` / `3.2` now detect an already running local Flask server by probing `http://127.0.0.1:5000/`, so repeated opens do not spawn duplicate server terminals.
- Editor layout:
  - sticky offsets of nav / lock banner / update banner were synchronized;
  - editor mode controls moved into the top nav;
  - vertical space usage improved.
- `/rooms`:
  - duration-aware free-slot filtering was added.
  - room lookup now distinguishes "known but empty room" from "unknown room", and the search suggestions no longer duplicate plain room names vs `room + building`.
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
- Hidden-day publish/display regression:
  - publish snapshot now safely includes blocks from hidden days;
  - group runtime attrs are re-synced after move/resize/edit through `syncGroupBlockRuntimeAttrs(...)`;
  - day-hidden state is preserved better when non-group blocks are re-rendered.
- Live search:
  - generator scaffold, core engine, compact layout, and integration/QA phases are all implemented;
  - search now mounts into the top nav, indexes current DOM state, and survives schedule mutations by reapplying on relevant changes;
  - CSS isolation was tightened further by moving status visibility from inline style to a CSS class;
  - Excel export no longer performs a redundant second search reset in the normal `_exportWithAutoUnhide() -> exportScheduleToExcel()` path.

## Planned / Future SPECs

- `SPEC-trial-lesson` is still not implemented.
- Expected semantics:
  - "expired" means visual marking (`trial-expired`), not automatic deletion;
  - preferred storage is a separate `trial_date` column in the Excel `Schedule` sheet;
  - UI would be a double-click dialog for non-group blocks.
- Live search is no longer a future track; any future work on it should build on the implemented feature plus:
  - `VERIFY_REPORT.md`
  - `CODEX_VERIFY_RESPONSE.md`

## User / Project Preferences

- Do not change the existing color scheme logic for groups in `color_service.py` unless explicitly requested.
- Keep changes to `app_actions.py` minimal.
- Prompt/spec language is Russian.
- Prompts should stay self-contained and explicitly state what is already done and what remains.
- For live-search follow-up changes:
  - do not treat the current `gear_xls/html_output/schedule.html` as a file to be manually edited;
  - continue implementing in source modules/generators so the feature survives regeneration.
