# SchedGen — School Schedule Generator

## Project Overview
Python-based school schedule optimizer using Google OR-Tools CP-SAT solver.
~15 000 lines across 4 subsystems. Bilingual codebase (Russian comments + English code).

Full architecture: see **PROJECT_MAP.md** (Russian, comprehensive) and **Structure-Claude.md** (module map).

---

## Subsystems

| Subsystem | Directory | Entry Point | Purpose |
|-----------|-----------|-------------|---------|
| **Optimizer** | root | `main_sch.py` | CP-SAT model, constraint solving |
| **Web Editor** | `gear_xls/` | `gear_xls/main.py` | Flask + HTML drag-drop schedule editor |
| **Visualization** | `visualiser/`, `visualiserTV/` | `schedule_visualizer_enhanced.py` | PDF/HTML exports |
| **GUI** | `gui_services/` | `gui.py` + `gui_services/app_actions.py` | Tkinter wrapper |

## Data Flow
```
Excel (Plannung sheet)
  → reader.py (ScheduleReader)
  → scheduler_base.py (ScheduleOptimizer, CP-SAT)
      ├── linked_constraints.py
      ├── resource_constraints.py
      ├── time_conflict_constraints.py
      ├── timewindow_adapter.py  ← largest module (946 lines), high-risk
      └── objective.py
  → output_utils.py
  → Excel (Schedule sheet, English headers)
      ├── visualiser/ → PDF + HTML
      └── gear_xls/  → interactive web editor
```

---

## ⚠️ Critical Known Issue
`gear_xls` exports the Schedule sheet with **Russian headers**.
`visualiser` expects **English headers** (`subject, group, teacher, room, building, day, start_time, end_time, duration, pause_before, pause_after`).
Do NOT add logic that assumes these are interchangeable. See PROJECT_MAP.md for details.

---

## Development Pipeline

### Starting a new task
1. `/orchestrate "описание задачи"` — spec-agent создаёт SPEC, prompt-generator создаёт фазовые промпты
2. `python orchestrator.py start "название задачи"` — инициализирует трекер состояния
3. Применить первый промпт (Claude Code или Codex)
4. `/verify` — code-verifier создаёт VERIFY_REPORT.md + CODEX_VERIFY_PROMPT.md
5. Вставить CODEX_VERIFY_PROMPT.md в Codex, сохранить ответ как CODEX_VERIFY_RESPONSE.md
6. `/verify` повторно — консолидирует оба отчёта
7. `python orchestrator.py next` — переход к следующей фазе
8. `/update-docs` — обновляет архитектурную документацию

### Bug fix cycle
1. `/fix-cycle "описание бага"` — bug-analyzer анализирует код, создаёт fix-промпт
2. Применить fix-промпт
3. `/verify`

### Перенос в новую сессию
`python orchestrator.py handoff` — создаёт SESSION_HANDOFF.md со всем контекстом

---

## Available Agents

| Agent | Invoke with | Purpose |
|-------|-------------|---------|
| `spec-agent` | "Use spec-agent to analyze: ..." | Требования → SPEC-*.md в PROMPTS/ |
| `prompt-generator` | "Use prompt-generator to create prompts from PROMPTS/SPEC-*.md" | SPEC → фазовые промпты |
| `code-verifier` | "Use code-verifier to verify [changes] against [SPEC]" | Верификация кода (read-only) |
| `doc-updater` | "Use doc-updater to update docs for [area]" | Обновление ARCHITECTURE.md |
| `bug-analyzer` | "Use bug-analyzer to analyze: ..." | Анализ бага → fix-промпт |

## Available Skills (slash commands)

| Skill | Purpose |
|-------|---------|
| `/orchestrate [task]` | Запускает полный пайплайн: spec + prompts |
| `/verify` | Верификация + Codex-промпт |
| `/fix-cycle [bug]` | Цикл исправления бага |
| `/update-docs` | Обновление архитектурных документов |

---

## Key Files Quick Reference

| File | Role | Size |
|------|------|------|
| `scheduler_base.py` | CP-SAT model builder | 253 lines |
| `timewindow_adapter.py` | Time window heuristics — HIGH RISK | 946 lines |
| `reader.py` | Excel input parser | 392 lines |
| `constraints.py` | Constraint aggregator | 12 lines |
| `linked_constraints.py` | Sequential class chains | 96 lines |
| `resource_constraints.py` | Teacher/room/group conflicts | 194 lines |
| `time_conflict_constraints.py` | Complex time logic | 306 lines |
| `objective.py` | Optimization goal | 174 lines |
| `gui_services/app_actions.py` | Central GUI controller | 702 lines |

---

## Testing
No formal pytest suite. Diagnostic script:
```bash
python test_timewindow.py xlsx_initial/schedule_planning.xlsx --verbose
```
Or via orchestrator:
```bash
python orchestrator.py test
```

## Prompt Naming Convention
```
PROMPTS/Prompt-Fix-Phase[N]-[NN]-[Module]-[ShortDescription].md
PROMPTS/Prompt-Fix-afterFix-[NN]-[Module]-[ShortDescription].md
PROMPTS/SPEC-[descriptive-name].md
```
Next afterFix number: check existing PROMPTS/Prompt-Fix-afterFix-*.md (currently up to -09).

## File Size Limits

### New files (hard limits — enforce always)
- **Python**: max **500–700 lines**. If a new module would exceed this, split it into focused submodules with clear single responsibilities.
- **JavaScript**: max **2000 lines**. If a new JS module would exceed this, split by feature/responsibility area.

### Existing files (do not refactor without explicit user approval)
- Do **not** grow existing large files further. Prefer extracting new small modules and importing them.
- Do **not** silently refactor existing monoliths — that requires explicit agreement from the user.
- **Mandatory exception**: if an existing file is found to critically need refactoring (maintenance risk, duplicate logic, causing bugs), **report to the user** with a proposed refactoring plan before touching it.

### Known large files in the project (do not grow further)
| File | Lines | Note |
|------|-------|------|
| `timewindow_adapter.py` | 946 | HIGH RISK — extra scrutiny on any change |
| `gui_services/app_actions.py` | 702 | Over limit — avoid adding new logic here |
| `visualiser/enhanced_export_manager_html.py` | 492 | Monitor |
| `gear_xls/utils.py` | 301 | OK |

## Iteration Limits
- spec-agent: max 5 rounds of questions before forcing SPEC creation
- code verification loops: max 3 iterations before escalating to user
- bug-fix cycles: max 3 attempts before requesting human review
