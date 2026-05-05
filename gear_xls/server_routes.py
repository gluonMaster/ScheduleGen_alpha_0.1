#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль с маршрутами для веб-сервера Flask.
"""

import json
import logging
import os
import re
import sys
from datetime import timedelta

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_cors import CORS

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from gear_xls.runtime_paths import (
    HEALTH_MARKER,
    ensure_runtime_dirs,
    get_excel_exports_dir,
    get_js_modules_dir,
    get_project_root,
    get_project_root_id,
    get_schedule_html_path,
    get_server_log_path,
    get_spiski_dir,
    get_static_dir,
    load_server_config,
    set_project_root_env,
)

from auth import authenticate, current_user, get_or_create_secret_key, login_required, role_required
from excel_exporter import process_schedule_export_request
import lock_manager
import rooms_report
import rooms_routes
import state_manager


def _build_log_handlers():
    ensure_runtime_dirs()
    handlers = [logging.FileHandler(get_server_log_path(), encoding="utf-8")]
    if _stdout_supports_text("Запуск Flask-сервера"):
        handlers.insert(0, logging.StreamHandler(sys.stdout))
    return handlers


def _stdout_supports_text(text: str) -> bool:
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return False
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except Exception:
        return False
    return True


def configure_logging():
    if getattr(configure_logging, "_configured", False):
        return
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    for handler in _build_log_handlers():
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    configure_logging._configured = True


configure_logging()
logger = logging.getLogger("server_routes")

app = Flask(__name__)
app.secret_key = get_or_create_secret_key()
app.permanent_session_lifetime = timedelta(hours=8)
app.config["SESSION_COOKIE_NAME"] = f"schedgen_session_{get_project_root_id()}"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
CORS(app, resources={r"/api/spiski/*": {"origins": "*"}})
JSON_AUTH_PATHS = {
    "/api/lock/status",
    "/api/lock/acquire",
    "/api/lock/release",
    "/api/lock/heartbeat",
    "/api/lock",
    "/api/status",
    "/api/blocks",
    "/api/columns",
    "/api/individual_lessons",
    "/api/schedule",
    "/api/schedule/publish",
    "/api/rooms/availability",
}


@app.before_request
def ensure_json_401_for_lock_api():
    if (
        request.path in JSON_AUTH_PATHS or request.path.startswith("/api/blocks/")
    ) and session.get("login") is None:
        return jsonify({"error": "Unauthorized"}), 401


@app.before_request
def csrf_same_origin_check():
    """Reject mutating requests whose Origin header does not match the server."""
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return
    if request.path in ("/login",):
        return
    origin = request.headers.get("Origin", "")
    if not origin:
        return  # No Origin: same-origin sendBeacon / form submit — allow
    scheme = "https" if request.is_secure else "http"
    expected = f"{scheme}://{request.host}"
    if origin != expected:
        logger.warning(
            "CSRF: rejected %s %s — Origin %r != %r",
            request.method, request.path, origin, expected,
        )
        return jsonify({"error": "Forbidden", "code": "CSRF_FAILED"}), 403


@app.after_request
def set_no_store_for_api(response):
    if request.path.startswith("/api/") or request.path == "/schedule":
        response.headers["Cache-Control"] = "no-store"
    return response

LOGIN_PAGE_TEMPLATE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>Вход - SchedGen</title>
<style>
body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f5f5}
.login-box{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.15);width:320px}
h2{margin-top:0}input{width:100%;box-sizing:border-box;padding:.5rem;margin:.5rem 0 1rem;border:1px solid #ccc;border-radius:4px}
button{width:100%;padding:.6rem;background:#1a73e8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1rem}
.error{color:red;margin-bottom:1rem}
</style></head><body>
<div class="login-box">
<h2>SchedGen - Вход</h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post">
<label>Логин<input name="login" type="text" autocomplete="username" required></label>
<label>Пароль<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Войти</button>
</form>
</div></body></html>"""
ROOMS_PAGE_TEMPLATE = rooms_routes.ROOMS_PAGE_TEMPLATE

EXCEL_EXPORTS_DIR = get_excel_exports_dir()
SPISKI_DIR = get_spiski_dir()
SPISKI_FILE_MAP = {
    "subjects": "disciplins.txt",
    "groups": "groups.txt",
    "teachers": "teachers.txt",
    "rooms_Villa": "kabinets_Villa.txt",
    "rooms_Kolibri": "kabinets_Kolibri.txt",
}

rooms_routes.configure(login_required, current_user, rooms_report, ROOMS_PAGE_TEMPLATE)
app.register_blueprint(rooms_routes.bp)


def _spiski_sort_key(value):
    """Case-insensitive natural sort key (e.g. '2' < '10')."""
    parts = re.findall(r"\d+|\D+", (value or "").strip())
    key = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.casefold()))
    return tuple(key)


def _load_spiski_data():
    result = {}
    for key, filename in SPISKI_FILE_MAP.items():
        filepath = os.path.join(SPISKI_DIR, filename)
        entries = []
        seen = set()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    item = line.strip()
                    if not item:
                        continue
                    item_key = item.casefold()
                    if item_key in seen:
                        continue
                    seen.add(item_key)
                    entries.append(item)
        except FileNotFoundError:
            logger.warning("Spiski file not found (using empty list): %s", filepath)
        except Exception as exc:
            logger.warning("Error reading spiski file %s: %s", filepath, exc)
        result[key] = sorted(entries, key=_spiski_sort_key)
    return result


def _build_spiski_data_js(spiski_data):
    return (
        "var spiskiData = {\n"
        f'    "subjects": {json.dumps(spiski_data.get("subjects", []), ensure_ascii=False)},\n'
        f'    "groups": {json.dumps(spiski_data.get("groups", []), ensure_ascii=False)},\n'
        f'    "teachers": {json.dumps(spiski_data.get("teachers", []), ensure_ascii=False)},\n'
        f'    "rooms_Villa": {json.dumps(spiski_data.get("rooms_Villa", []), ensure_ascii=False)},\n'
        f'    "rooms_Kolibri": {json.dumps(spiski_data.get("rooms_Kolibri", []), ensure_ascii=False)}\n'
        "};\n"
        "window.spiskiData = spiskiData;"
    )


def _inject_latest_spiski_data(html):
    fresh_spiski_js = _build_spiski_data_js(_load_spiski_data())
    updated_html, replacements = re.subn(
        r"var spiskiData = \{.*?\};\s*window\.spiskiData = spiskiData;",
        fresh_spiski_js,
        html,
        count=1,
        flags=re.S,
    )
    if replacements == 0:
        logger.warning("Failed to replace embedded spiskiData in schedule HTML")
        return html
    return updated_html


os.makedirs(EXCEL_EXPORTS_DIR, exist_ok=True)
logger.info("Excel export directory ready: %s", EXCEL_EXPORTS_DIR)


@app.route("/js_modules/<path:filename>")
def serve_js_modules(filename):
    return send_from_directory(get_js_modules_dir(), filename)


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(get_static_dir(), filename)


@app.route("/login", methods=["GET", "POST"])
def login():
    error_msg = None
    if request.method == "POST":
        login_value = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        user = authenticate(login_value, password)
        if user:
            session.permanent = True
            session["login"] = user.get("login")
            session["display_name"] = user.get("display_name")
            session["role"] = user.get("role")
            return redirect(url_for("schedule"))
        error_msg = "Неверный логин или пароль"
    return render_template_string(LOGIN_PAGE_TEMPLATE, error=error_msg)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/schedule")
@login_required
def schedule():
    html_path = get_schedule_html_path()
    if not os.path.exists(html_path):
        stub = (
            "<html><body><p>Расписание ещё не создано. "
            "Попросите Аллу сгенерировать расписание.</p></body></html>"
        )
        response = app.make_response(stub)
        response.headers["Cache-Control"] = "no-store"
        return response

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = _inject_latest_spiski_data(html)

    user = current_user()
    published_base_available = state_manager.get_base_revision() is not None
    injection = (
        "<script>\n"
        f"  window.CURRENT_USER = {json.dumps(user['login'])};\n"
        f"  window.USER_ROLE = {json.dumps(user['role'])};\n"
        f"  window.DISPLAY_NAME = {json.dumps(user['display_name'])};\n"
        f'  window.PUBLISHED_BASE_AVAILABLE = {"true" if published_base_available else "false"};\n'
        "</script>\n"
        '<link rel="stylesheet" href="/static/nav.css">\n'
    )
    if "</head>" in html:
        html = html.replace("</head>", injection + "</head>", 1)
    else:
        html = injection + html

    auth_ui_tag = (
        '<script src="/static/auth_ui.js"></script>\n'
        '<script src="/static/base_sync_ui.js"></script>\n'
        '<script src="/static/lock_ui.js"></script>\n'
        '<script src="/js_modules/trial_ui.js"></script>\n'
        '<script src="/static/individual_ui.js"></script>\n'
        # Load the search scaffold after the existing schedule UI so it can
        # reuse the injected nav slot and exposed auth/base/individual APIs.
        '<script src="/static/schedule_search_ui.js"></script>\n'
    )
    if "</body>" in html:
        html = html.replace("</body>", auth_ui_tag + "</body>", 1)
    else:
        html += auth_ui_tag

    response = app.make_response(html)
    response.headers["Cache-Control"] = "no-store"
    return response


def _require_lock(login):
    state = lock_manager.get_lock_status()
    if state.get("holder") != login:
        return {"ok": False, "error": "No active lock", "code": "NO_LOCK"}
    return None


@app.route("/api/lock/status")
@login_required
def api_lock_status():
    state = lock_manager.get_lock_status()
    return jsonify(state)


@app.route("/api/lock/acquire", methods=["POST"])
@login_required
def api_lock_acquire():
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    result = lock_manager.acquire_lock(user["login"])
    return jsonify(result)


@app.route("/api/lock/release", methods=["POST"])
@login_required
def api_lock_release():
    data = request.get_json(force=True, silent=True) or {}
    version = data.get("version")
    user = current_user()
    if version is None:
        return jsonify({"ok": False, "error": "version required"}), 400
    try:
        version = int(version)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid version"}), 400
    result = lock_manager.release_lock(user["login"], version)
    return jsonify(result)


@app.route("/api/lock/heartbeat", methods=["POST"])
@login_required
def api_lock_heartbeat():
    data = request.get_json(force=True, silent=True) or {}
    version = data.get("version")
    user = current_user()
    if version is None:
        return jsonify({"ok": False, "error": "version required"}), 400
    try:
        version = int(version)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid version"}), 400
    result = lock_manager.heartbeat(user["login"], version)
    return jsonify(result)


@app.route("/api/lock", methods=["DELETE"])
@login_required
def api_lock_force_release():
    user = current_user()
    if user["role"] != "admin":
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    result = lock_manager.force_release(user["login"])
    return jsonify(result)


@app.route("/api/status")
@login_required
def api_status():
    lock_state = lock_manager.get_lock_status()
    return jsonify(
        {
            "lock": {
                "holder": lock_state.get("holder"),
                "version": lock_state.get("version"),
                "acquired_at": lock_state.get("acquired_at"),
                "last_heartbeat": lock_state.get("last_heartbeat"),
            },
            "base_revision": state_manager.get_base_revision(),
            "individual_revision": state_manager.get_individual_revision(),
            "base_updated": False,
        }
    )


@app.route("/api/individual_lessons")
@login_required
def api_individual_lessons():
    return jsonify(state_manager.get_individual_lessons())


@app.route("/api/schedule")
@login_required
def api_schedule():
    base = state_manager.get_base_schedule()
    ind = state_manager.get_individual_lessons()
    published_base_available = base.get("published_at") is not None
    return jsonify(
        {
            "base": base.get("blocks", []),
            "individual": ind.get("blocks", []),
            "base_revision": base.get("published_at"),
            "individual_revision": ind.get("last_modified"),
            "published_base_available": published_base_available,
        }
    )


@app.route("/api/schedule/publish", methods=["POST"])
@login_required
def api_publish_schedule():
    user = current_user()
    if user["role"] != "admin":
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    data = request.get_json(force=True, silent=True) or {}
    blocks = data.get("blocks", [])
    if not isinstance(blocks, list):
        return jsonify({"ok": False, "error": "blocks must be a list"}), 400
    result = state_manager.publish_base(blocks, user["login"])
    return jsonify(
        {
            "ok": True,
            "published_at": result["published_at"],
            "base_revision": result["published_at"],
            "group_blocks_saved": len(result["blocks"]),
        }
    )


@app.route("/api/blocks", methods=["POST"])
@login_required
def api_create_block():
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    data = request.get_json(force=True, silent=True) or {}
    block, error = state_manager.add_block(data, user["role"])
    if error:
        return jsonify({"ok": False, "error": error, "code": "VALIDATION_ERROR"}), 400
    return jsonify(
        {
            "ok": True,
            "block": block,
            "individual_revision": state_manager.get_individual_revision(),
        }
    )


@app.route("/api/blocks/<block_id>", methods=["PUT"])
@login_required
def api_update_block(block_id):
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    data = request.get_json(force=True, silent=True) or {}
    block, error = state_manager.update_block(block_id, data, user["role"])
    if error == "NOT_FOUND":
        return jsonify({"ok": False, "error": "Block not found", "code": "NOT_FOUND"}), 404
    if error:
        return jsonify({"ok": False, "error": error, "code": "VALIDATION_ERROR"}), 400
    return jsonify(
        {
            "ok": True,
            "block": block,
            "individual_revision": state_manager.get_individual_revision(),
        }
    )


@app.route("/api/blocks/<block_id>", methods=["DELETE"])
@login_required
def api_delete_block(block_id):
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    deleted, del_err = state_manager.delete_block(block_id, user["role"])
    if del_err == "FORBIDDEN":
        return jsonify({"ok": False, "error": "Forbidden lesson_type", "code": "FORBIDDEN"}), 403
    if not deleted:
        return jsonify({"ok": False, "error": "Block not found", "code": "NOT_FOUND"}), 404
    return jsonify(
        {
            "ok": True,
            "individual_revision": state_manager.get_individual_revision(),
        }
    )


@app.route("/api/blocks/<block_id>/convert", methods=["POST"])
@login_required
def api_convert_block(block_id):
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    block, error = state_manager.convert_block_to_regular(block_id, user["role"])
    if error == "NOT_FOUND":
        return jsonify({"ok": False, "error": "Block not found", "code": "NOT_FOUND"}), 404
    if error == "NOT_TRIAL":
        return jsonify({"ok": False, "error": "Block is not a trial lesson", "code": "NOT_TRIAL"}), 400
    if error == "FORBIDDEN":
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify(
        {
            "ok": True,
            "block": block,
            "individual_revision": state_manager.get_individual_revision(),
        }
    )


@app.route("/api/columns", methods=["POST"])
@login_required
def api_add_column():
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    data = request.get_json(force=True, silent=True) or {}
    building = (data.get("building") or "").strip()
    day = (data.get("day") or "").strip()
    room = (data.get("room") or "").strip()
    if not building or not day or not room:
        return jsonify({"ok": False, "error": "building, day, room required"}), 400
    return jsonify({"ok": True})


@app.route("/api/columns", methods=["DELETE"])
@login_required
def api_delete_column():
    user = current_user()
    if user["role"] not in ("admin", "editor", "organizer"):
        return jsonify({"ok": False, "error": "Forbidden", "code": "FORBIDDEN"}), 403
    err = _require_lock(user["login"])
    if err:
        return jsonify(err), 403
    data = request.get_json(force=True, silent=True) or {}
    building = (data.get("building") or "").strip()
    day = (data.get("day") or "").strip()
    room = (data.get("room") or "").strip()
    if not building or not day or not room:
        return jsonify({"ok": False, "error": "building, day, room required"}), 400
    if user["role"] == "editor" and state_manager.base_has_group_lessons_in_column(
        building, day, room
    ):
        return jsonify(
            {
                "ok": False,
                "error": "Column contains group lessons",
                "code": "COLUMN_HAS_GROUP_LESSONS",
            }
        ), 403
    if user["role"] == "organizer":
        if state_manager.base_has_group_lessons_in_column(building, day, room):
            return jsonify(
                {
                    "ok": False,
                    "error": "Column contains group lessons",
                    "code": "COLUMN_HAS_GROUP_LESSONS",
                }
            ), 403
        if state_manager.individual_column_has_non_trial_blocks(building, day, room):
            return jsonify(
                {
                    "ok": False,
                    "error": "Column contains non-trial lessons",
                    "code": "COLUMN_HAS_NON_TRIAL_BLOCKS",
                }
            ), 403
    count = state_manager.delete_column_blocks(building, day, room)
    return jsonify(
        {
            "ok": True,
            "blocks_removed": count,
            "individual_revision": state_manager.get_individual_revision(),
        }
    )


@app.route("/")
def index():
    logger.info("Получен запрос к корневому маршруту")
    return "Excel Export Server is running! Access /export_to_excel via POST request to export schedule."


@app.route("/health")
def health():
    root = get_project_root()
    config = load_server_config(root, include_env=True)
    return jsonify(
        {
            "ok": True,
            "marker": HEALTH_MARKER,
            "project_root": root,
            "project_root_id": get_project_root_id(root),
            "host": config["host"],
            "port": config["port"],
        }
    )


@app.route("/export_to_excel", methods=["POST"])
@login_required
@role_required("admin")
def export_to_excel():
    try:
        schedule_data_json = request.form.get("schedule_data")
        csrf_token = request.form.get("csrf_token", "")

        if not schedule_data_json:
            logger.error("Данные расписания не получены")
            return jsonify({"error": "Данные расписания не получены"}), 400

        logger.info(
            "Получены данные для экспорта в Excel (CSRF: %s)",
            csrf_token[:8] if csrf_token else "отсутствует",
        )
        logger.info("Размер данных: %s байт", len(schedule_data_json))

        output_file = process_schedule_export_request(schedule_data_json, EXCEL_EXPORTS_DIR)
        if not output_file or not os.path.exists(output_file):
            logger.error("Не удалось создать Excel-файл")
            return jsonify({"error": "Не удалось создать Excel-файл"}), 500

        logger.info("Файл готов к отправке: %s", output_file)
        response = send_file(
            output_file,
            as_attachment=True,
            download_name=os.path.basename(output_file),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        logger.info("Excel-файл успешно отправлен: %s", output_file)
        return response

    except Exception as e:
        logger.error("Ошибка при экспорте в Excel: %s", e)
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/save_intermediate", methods=["POST"])
@login_required
def save_intermediate():
    try:
        if session.get("role") != "admin":
            return jsonify({"success": False, "reason": "forbidden"}), 403

        data = request.get_json(force=True, silent=True) or {}
        html_content = data.get("html_content", "")
        default_filename = data.get("default_filename", "intermediate_schedule.html")

        import tkinter as tk
        from tkinter import filedialog

        root = None
        save_path = ""
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            save_path = filedialog.asksaveasfilename(
                parent=root,
                title="Сохранить промежуточный результат",
                initialfile=default_filename,
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            )
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass

        if not save_path:
            return jsonify({"success": False, "reason": "cancelled"})

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("Промежуточный файл сохранён: %s", save_path)
        return jsonify({"success": True, "path": save_path})

    except Exception as e:
        logger.error("Ошибка при сохранении промежуточного файла: %s", e)
        return jsonify({"success": False, "reason": str(e)})


@app.route("/api/spiski/add", methods=["POST"])
@login_required
def add_spiski_item():
    try:
        data = request.get_json(force=True, silent=True) or {}
        key = (data.get("key", "") or "").strip()
        value = (data.get("value", "") or "").strip()

        if not key or not value:
            return jsonify({"error": "key and value are required"}), 400
        if len(value) > 200:
            return jsonify({"error": "value too long"}), 400
        if "\n" in value or "\r" in value:
            return jsonify({"error": "value must be a single line"}), 400

        filename = SPISKI_FILE_MAP.get(key)
        if not filename:
            return jsonify({"error": f"Unknown spiski key: {key}"}), 400

        filepath = os.path.join(SPISKI_DIR, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        existing = set()
        entries = []
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    item = line.strip()
                    if not item:
                        continue
                    low = item.casefold()
                    if low in existing:
                        continue
                    existing.add(low)
                    entries.append(item)

        if value.casefold() in existing:
            return jsonify({"ok": True, "added": False, "reason": "already_exists"})

        entries.append(value)
        entries.sort(key=_spiski_sort_key)

        with open(filepath, "w", encoding="utf-8") as f:
            if entries:
                f.write("\n".join(entries) + "\n")

        logger.info("Spiski: added %r to %s", value, filename)
        return jsonify({"ok": True, "added": True})

    except Exception as e:
        logger.error("Error in add_spiski_item: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/spiski/add", methods=["OPTIONS"])
def add_spiski_item_options():
    response = app.make_default_options_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    return response


@app.route("/export_to_excel", methods=["OPTIONS"])
def export_to_excel_options():
    return app.make_default_options_response()


def run_server(host=None, port=None, project_root=None):
    root = set_project_root_env(project_root)
    ensure_runtime_dirs(root)
    os.makedirs(get_excel_exports_dir(root), exist_ok=True)
    config = load_server_config(root, include_env=True)
    host = host or config["host"]
    port = int(port or config["port"])
    os.environ["HOST"] = str(host)
    os.environ["PORT"] = str(port)
    logger.info("Запуск Flask-сервера на %s:%s (project_root=%s)", host, port, root)
    if getattr(sys, "stdout", None) is not None:
        print(f"=== Flask export server starting on {host}:{port} ===")
        print(f"=== Log file: {get_server_log_path(root)} ===")
    app.run(debug=False, host=host, port=port)


if __name__ == "__main__":
    run_server()
