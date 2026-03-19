---
name: multiuser-web-editor-spec
description: Статус разработки многопользовательского веб-редактора с ролями доступа
type: project
---

Все 5 фаз реализованы (2026-03-19). Код не закоммичен (uncommitted changes в git).

**Ключевые файлы SPEC/промптов:**
- `PROMPTS/SPEC-multiuser-web-editor.md` — полное ТЗ (16 разделов, 17 edge cases)
- `PROMPTS/Prompt-MultiUser-Phase1-01-Auth-AuthModuleAndLoginRoutes.md`
- `PROMPTS/Prompt-MultiUser-Phase2-01-Lock-LockManagerAndAPI.md`
- `PROMPTS/Prompt-MultiUser-Phase3-01-IndividualLessons-StateManagerAndBlocksAPI.md`
- `PROMPTS/Prompt-MultiUser-Phase4-01-Publish-PublishFlowAndBaseSchedule.md`
- `PROMPTS/Prompt-MultiUser-Phase5-01-Rooms-RoomsAvailabilityReport.md`

**Пользователи и роли:**
- `alla` / admin — полный доступ, все инструменты GUI, оптимизация
- `valentina` / editor — добавление/удаление/редактирование инд. и нахильфе занятий; добавление/удаление столбцов (с защитой групповых занятий); отчёт аудиторий
- `olesya` / viewer — только просмотр + отчёт аудиторий

**Архитектурные решения:**
- Flask раздаёт `schedule.html` через `/schedule` (не file://)
- Два слоя данных: `schedule_state/base_schedule.json` (Алла публикует) + `schedule_state/individual_lessons.json` (Валентина, автосохранение)
- Каноничные координаты блока: `(building, day, room, start_time, end_time)` — не `col_index`
- Блокировка редактирования: `lock.json` с версионированием, heartbeat 60 сек, таймаут 30 мин
- Единый polling-эндпоинт `/api/status` (лок + ревизии за один запрос, 30 сек)
- Все JS-вызовы — same-origin relative URLs, никаких `http://localhost:5000`
- OS-level file lock для всех write-операций над JSON-состоянием (не только threading.Lock)

**Новые Python-модули:** `auth.py`, `lock_manager.py`, `state_manager.py`, `rooms_report.py`, `scripts/set_password.py`
**Новые JS-модули:** `static/auth_ui.js`, `static/rooms_report.js`, `static/nav.css`

**Единственное изменение в GUI:** кнопка 3.2 (`open_web_app`) открывает `http://localhost:5000/schedule` вместо `file://`

**Why:** После добавления индивидуальных занятий потребовалось предоставить Валентине редактор без доступа к оптимизатору, и Олесе — просмотр расписания и отчёт аудиторий.

**How to apply:** Реализация завершена. Следующий шаг — тестирование в браузере, затем коммит. При доработке помнить: роль valentina защищена от изменения групповых блоков, роль viewer — read-only.
