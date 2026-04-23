# Инструкция по запуску и настройке автозапуска Flask-сервера на Windows 10/11

## Что именно реализовано

В проекте автозапуск сделан не как Windows Service, а как **tray-приложение**, которое:

- стартует в интерактивной Windows-сессии пользователя;
- поднимает Flask-сервер в фоне без видимого `cmd`-окна;
- пишет логи в отдельные файлы;
- умеет включать и выключать автозапуск через `Task Scheduler`.

Важно: в текущей реализации автозапуск происходит **после входа пользователя в Windows**, а не до логина.

## Что должно быть уже установлено

На компьютере должен быть установлен Python с рабочим `python.exe` и `pythonw.exe`.

Также в том же Python-окружении должны быть установлены зависимости, нужные для серверной части:

- `flask`
- `flask-cors`
- `bcrypt`

Проверка:

```powershell
python -c "import sys, flask, flask_cors, bcrypt; print(sys.executable)"
```

Если команда завершается ошибкой, нужно установить недостающие пакеты именно в тот Python, который будет использоваться для автозапуска.

Пример:

```powershell
python -m pip install flask flask-cors bcrypt
```

## Какие абсолютные пути важны

Для автозапуска обязательно важны **абсолютные пути**:

1. Абсолютный путь к `pythonw.exe`
2. Абсолютный путь к `server_tray.py`
3. Абсолютный путь к корню проекта

Корень проекта должен содержать как минимум:

- `gear_xls\`
- `xlsx_initial\`
- `visualiser\`
- `gui.py`
- `server_tray.py`

Пример корня проекта:

```text
C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Пример абсолютного пути к launcher-скрипту:

```text
C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py
```

Пример абсолютного пути к Python:

```text
C:\Python314\python.exe
C:\Python314\pythonw.exe
```

Если Python установлен в другом месте, во всех командах ниже нужно подставить **свои абсолютные пути**.

## Как узнать, какой Python используется

Рекомендуется сначала явно узнать путь к `python.exe`, из которого вы будете включать автозапуск:

```powershell
python -c "import sys; print(sys.executable)"
```

Если нужно запускать проект не через `python` из `PATH`, а через конкретный интерпретатор, используйте его абсолютный путь.

Пример:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control status --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Именно это рекомендуется для production-настройки: не надеяться на `PATH`, а использовать абсолютный путь к `python.exe`.

## Куда пишутся runtime-файлы и логи

После первого запуска tray/сервера проект автоматически создаёт в корне проекта:

- `logs\`
- `runtime\`

Основные файлы:

- `logs\flask_server.log`
- `logs\server_tray.log`
- `runtime\server_tray_state.json`

Также сервер использует абсолютные пути внутри проекта:

- `gear_xls\config\users.json`
- `gear_xls\config\secret_key.txt`
- `gear_xls\schedule_state\*`
- `gear_xls\html_output\*`
- `gear_xls\excel_exports\*`
- `spiski\*`

Никакие отдельные настройки путей в коде для автозапуска обычно менять не нужно, если проект лежит в постоянной папке и запускается с корректным `--project-root`.

## Рекомендуемый способ настройки автозапуска

### Шаг 1. Один раз проверить ручной запуск tray

Откройте PowerShell и выполните:

```powershell
C:\Python314\pythonw.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --mode tray --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Если пути содержат пробелы, обязательно используйте кавычки:

```powershell
& "C:\Python314\pythonw.exe" "C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py" --mode tray --project-root "C:\Konst\2026\Kolibri\SchedGen_PreRelease"
```

Что должно произойти:

- в системном трее появится иконка;
- будет создан файл `runtime\server_tray_state.json`;
- будут созданы логи в `logs\`;
- Flask-сервер начнёт слушать порт `5000`.

Проверка:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/ | Select-Object -ExpandProperty Content
```

В ответе должен присутствовать текст:

```text
Excel Export Server is running!
```

### Шаг 2. Включить автозапуск штатной командой проекта

Рекомендуемый способ:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control enable_autostart --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Если пути содержат пробелы:

```powershell
& "C:\Python314\python.exe" "C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py" --control enable_autostart --project-root "C:\Konst\2026\Kolibri\SchedGen_PreRelease"
```

Что делает эта команда:

- находит `pythonw.exe` рядом с текущим `python.exe`;
- создаёт или обновляет задачу `Task Scheduler`;
- записывает в задачу абсолютные пути;
- регистрирует автозапуск под текущим Windows-пользователем.

Имя задачи в планировщике:

```text
SchedGen Flask Tray
```

## Как проверить статус автозапуска

Проверка через проект:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control status --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Если tray уже запущен, команда вернёт JSON со статусом.

Проверка задачи напрямую:

```powershell
schtasks /Query /TN "SchedGen Flask Tray" /XML
```

## Какая задача должна быть создана в Task Scheduler

В канонической конфигурации задача создаётся так:

- **Task name**: `SchedGen Flask Tray`
- **Trigger**: `At logon`
- **User**: текущий пользователь Windows
- **LogonType**: `InteractiveToken`
- **Run only when user is logged on**: да

Action должен содержать именно абсолютные пути:

- **Program** = абсолютный путь к `pythonw.exe`
- **Arguments** = абсолютный путь к `server_tray.py` + `--mode tray --project-root <absolute_project_root>`
- **Start in** = абсолютный путь к корню проекта

Пример:

- Program:

```text
C:\Python314\pythonw.exe
```

- Arguments:

```text
"C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py" --mode tray --project-root "C:\Konst\2026\Kolibri\SchedGen_PreRelease"
```

- Start in:

```text
C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

## Резервный способ: создать задачу вручную

Используйте этот способ только если штатная команда `--control enable_autostart` по какой-то причине не сработала.

### Через графический Task Scheduler

1. Откройте `Task Scheduler`
2. Выберите `Create Task`
3. На вкладке `General`:
   - задайте имя `SchedGen Flask Tray`
   - выберите `Run only when user is logged on`
4. На вкладке `Triggers`:
   - создайте trigger `At log on`
   - укажите нужного пользователя
5. На вкладке `Actions`:
   - `Program/script`: абсолютный путь к `pythonw.exe`
   - `Add arguments`: абсолютный путь к `server_tray.py` и `--mode tray --project-root "<absolute_project_root>"`
   - `Start in`: абсолютный путь к корню проекта
6. Сохраните задачу

### Через командную строку вручную

Ручное создание через `schtasks` в этой реализации не является каноническим способом, потому что проект сам формирует XML с правильным `InteractiveToken`.

Поэтому, если нужна CLI-настройка, используйте именно:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control enable_autostart --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

## Как выключить автозапуск

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control disable_autostart --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Или через трей-меню: `Выключить автозапуск`.

## Как запускать и проверять сервер вручную

Запустить или привести систему в рабочее состояние:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control ensure_running --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Открыть веб-интерфейс:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control open_web --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Остановить сервер:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control stop_server --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Перезапустить сервер:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control restart_server --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

Проверить статус:

```powershell
C:\Python314\python.exe C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py --control status --project-root C:\Konst\2026\Kolibri\SchedGen_PreRelease
```

## Что делать после переноса проекта в другую папку

Если проект был перенесён, автозапуск нужно **перерегистрировать**, потому что `Task Scheduler` хранит абсолютные пути.

Правильный порядок:

1. Выключить автозапуск:

```powershell
C:\Python314\python.exe D:\NewPath\SchedGen_PreRelease\server_tray.py --control disable_autostart --project-root D:\NewPath\SchedGen_PreRelease
```

2. Включить заново уже с новым абсолютным путём:

```powershell
C:\Python314\python.exe D:\NewPath\SchedGen_PreRelease\server_tray.py --control enable_autostart --project-root D:\NewPath\SchedGen_PreRelease
```

Если изменился не только путь к проекту, но и путь к Python, используйте новый абсолютный путь к `python.exe`.

## Что делать после смены Python

Если Python был переустановлен или перемещён, задача автозапуска может ссылаться на старый `pythonw.exe`.

Нужно:

1. Проверить текущий путь:

```powershell
python -c "import sys; print(sys.executable)"
```

2. Перевключить автозапуск командой `disable_autostart`, затем `enable_autostart`

Это обновит абсолютный путь к `pythonw.exe` внутри задачи.

## Что нужно знать про GUI

Кнопки GUI `3.1` и `3.2` теперь используют тот же control-plane, что и tray.

Но для запуска самого `gui.py` в проекте могут понадобиться дополнительные зависимости GUI-части, в частности `pywin32`, потому что GUI импортирует `win32com`.

Если ваша цель только в том, чтобы сервер автоматически стартовал на Windows, для настройки автозапуска достаточно `server_tray.py`; GUI для этого не обязателен.

Отдельно обратите внимание на файл:

```text
run_gui.bat
```

Если вы используете его для запуска GUI, проверьте, что путь к `pythonw.exe` там корректен для вашей машины. Это отдельная история от автозапуска tray, но там тоже может потребоваться корректный абсолютный путь.

## Проверка после перезагрузки

После перезагрузки или повторного входа пользователя в Windows проверьте:

1. В трее появилась иконка `SchedGen Flask Tray`
2. Существует файл:

```text
<project_root>\runtime\server_tray_state.json
```

3. Обновляются логи:

```text
<project_root>\logs\server_tray.log
<project_root>\logs\flask_server.log
```

4. Локально открывается:

```text
http://127.0.0.1:5000/schedule
```

5. Health-check отвечает:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/
```

## Типовые проблемы

### 1. `pythonw.exe not found in the current Python runtime`

Причина:

- автозапуск включается из Python, рядом с которым нет `pythonw.exe`

Что делать:

- использовать другой установленный Python;
- запускать команду `enable_autostart` через правильный абсолютный путь к `python.exe`.

### 2. Не создаётся задача в планировщике

Проверьте:

- запускаете ли вы PowerShell от нужного пользователя;
- существует ли `server_tray.py` по указанному абсолютному пути;
- существует ли `pythonw.exe` по пути, который соответствует выбранному `python.exe`.

Также смотрите лог:

```text
<project_root>\logs\server_tray.log
```

### 3. Сервер не стартует после логина

Проверьте:

- есть ли задача `SchedGen Flask Tray`;
- корректны ли её `Program`, `Arguments`, `Start in`;
- установлен ли Python именно по тому пути, который прописан в задаче;
- установлены ли зависимости `flask`, `flask-cors`, `bcrypt`.

### 4. Проект перенесли в другую папку

Это почти всегда означает, что нужно заново включить автозапуск с новым абсолютным `--project-root`.

### 5. Сайт не открывается с других компьютеров локальной сети

Сервер слушает `0.0.0.0:5000`, но настройка Windows Firewall автоматически не выполняется.

Если доступ нужен с других машин:

- проверьте локальный firewall;
- откройте входящий TCP-порт `5000`, если это требуется политикой вашей сети.

## Рекомендуемый минимальный production-сценарий

1. Определить абсолютный путь к Python:

```powershell
python -c "import sys; print(sys.executable)"
```

2. Проверить зависимости:

```powershell
python -c "import sys, flask, flask_cors, bcrypt; print(sys.executable)"
```

3. Один раз вручную запустить tray:

```powershell
& "C:\Python314\pythonw.exe" "C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py" --mode tray --project-root "C:\Konst\2026\Kolibri\SchedGen_PreRelease"
```

4. Включить автозапуск:

```powershell
& "C:\Python314\python.exe" "C:\Konst\2026\Kolibri\SchedGen_PreRelease\server_tray.py" --control enable_autostart --project-root "C:\Konst\2026\Kolibri\SchedGen_PreRelease"
```

5. Перелогиниться в Windows и проверить:

- иконку в трее;
- `http://127.0.0.1:5000/schedule`;
- файлы в `logs\` и `runtime\`.
