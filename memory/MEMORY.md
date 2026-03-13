# SchedGen Project Memory

## Active SPECs
- `PROMPTS/SPEC-lesson-type-filter.md` — фильтрация занятий по типу (групп/инд/наххильфе), 4 фазы, 18 файлов.
  **Статус: SPEC финализирован, аудирован против кода. Следующий шаг — запустить prompt-generator.**
  Команда: `Use prompt-generator to create prompts from PROMPTS/SPEC-lesson-type-filter.md`

## Planned / Future SPECs
- **SPEC-trial-lesson** (не создан): разовые/пробные занятия для негрупповых уроков.
  - Семантика: "истёкшее" = визуальная маркировка `trial-expired`, не автоудаление
  - Хранение: предпочтительно новая колонка `trial_date` в Excel-листе Schedule (gear_xls читает его своим кодом, изолировано от оптимизатора)
  - UI: диалог при двойном клике (расширить существующий edit dialog) — только для non-group блоков
  - Зависимость: нужен `data-lesson-type` на блоках (Фаза 1 SPEC-lesson-type-filter)

## Key Architecture Notes (verified against code)
- gear_xls: Flask-сервер (не статический HTML), генерирует HTML заново при каждой загрузке
- Классификация занятий: contains("Nachhilfe") → nachhilfe; contains("Ind.") → individual; иначе → group (case-sensitive)
- Фильтры в веб-редакторе НЕ влияют на экспорт в Excel (всегда экспортируется всё)
- Визуализатор: фильтрация на уровне данных (DataFrame) через параметр `--lesson-type`
- Tkinter GUI: фильтр типа занятий применяется к кнопкам "4. Запустить визуализатор" И "7. Учесть изменения"
- `toggleDay()` (core.js:19) ставит `display:none` на сами `.activity-block` — поэтому фильтр типа занятий НЕЛЬЗЯ реализовывать через display:none, только через CSS-класс `lesson-type-filter-hidden` (visibility:hidden)
- `export_to_excel.js:21` пропускает блоки с `display:none` — это намеренная логика, менять нельзя
- JS модули gear_xls загружаются из двух списков в `html_javascript.py`: `base_module_names` и `add_blocks_module_names`. Новый `lesson_type_filter.js` идёт в `add_blocks_module_names` перед `block_content_sync` (не перед `app_initialization`)

## User Preferences
- Цветовая схема блоков по группам (color_service.py) — не трогать. Негрупповые занятия маркировать border-left синим.
- app_actions.py (651 строк) — не добавлять много кода, макс +5-10 строк
- Язык SPEC-файлов: русский
