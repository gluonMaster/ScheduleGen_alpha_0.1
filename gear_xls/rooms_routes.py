import json

from flask import Blueprint, jsonify, make_response


ROOMS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Аудитории — SchedGen</title>
<link rel="stylesheet" href="/static/nav.css">
<style>
body { font-family: sans-serif; margin: 0; padding-top: calc(var(--schedgen-nav-height) + 4px); background: #fafafa; }
#rooms-controls { padding: 12px 16px; background: #fff; border-bottom: 1px solid #ddd;
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center; position: sticky;
    top: var(--schedgen-nav-height); z-index: 8000; }
#rooms-controls label { font-size: 13px; }
#rooms-controls select, #rooms-controls input[type=text], #rooms-controls input[type=number] {
    padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
#search-box { width: 200px; }
#duration-minutes { width: 110px; }
#rooms-table-wrap { overflow-x: auto; padding: 12px 16px; }
table.rooms-table { border-collapse: collapse; font-size: 12px; min-width: 600px; }
table.rooms-table th, table.rooms-table td {
    border: 1px solid #ddd; padding: 3px 6px; text-align: center; white-space: nowrap; }
table.rooms-table th { background: #f0f4f8; }
td.slot-busy { background: #b3d4f5; cursor: default; }
td.slot-busy-ind { background: #c8e6c9; cursor: default; }
td.slot-free { background: #fff; }
#free-windows { padding: 12px 16px; font-size: 13px; }
#free-windows h3 { margin: 0 0 8px; }
#free-windows ul { margin: 0; padding-left: 20px; }
.day-toggle { display: inline-block; margin: 0 2px; }
.day-toggle input { display: none; }
.day-toggle label { display: inline-block; padding: 3px 8px; border: 1px solid #aaa;
    border-radius: 4px; cursor: pointer; font-size: 12px; background: #fff; }
.day-toggle input:checked + label { background: #1a73e8; color: #fff; border-color: #1a73e8; }
</style>
</head>
<body>
<script>
  window.CURRENT_USER = {{ current_user }};
  window.USER_ROLE = {{ user_role }};
  window.DISPLAY_NAME = {{ display_name }};
</script>
<div id="rooms-controls">
  <label>Здание:
    <select id="filter-building">
      <option value="">Все</option>
    </select>
  </label>
  <label>Аудитория:
    <select id="filter-room">
      <option value="">Все</option>
    </select>
  </label>
  <span>День:
    <span class="day-toggle"><input type="checkbox" id="d-all" checked><label for="d-all">Все</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Mo"><label for="d-Mo">Mo</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Di"><label for="d-Di">Di</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Mi"><label for="d-Mi">Mi</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Do"><label for="d-Do">Do</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Fr"><label for="d-Fr">Fr</label></span>
    <span class="day-toggle"><input type="checkbox" id="d-Sa"><label for="d-Sa">Sa</label></span>
  </span>
  <label>Поиск:
    <input type="text" id="search-box" placeholder="0.06 Kolibri ..." autocomplete="off" list="room-suggestions">
    <datalist id="room-suggestions"></datalist>
  </label>
  <label>Длительность, мин:
    <input type="number" id="duration-minutes" min="1" step="5" placeholder="90" autocomplete="off">
  </label>
  <button id="btn-search">Найти</button>
  <button id="btn-refresh" title="Обновить данные">&#8635;</button>
</div>
<div id="rooms-table-wrap">
  <table class="rooms-table" id="rooms-table">
    <thead id="rooms-thead"></thead>
    <tbody id="rooms-tbody"></tbody>
  </table>
</div>
<div id="free-windows"></div>
<script src="/static/auth_ui.js"></script>
<script src="/static/rooms_report.js"></script>
</body>
</html>"""

bp = Blueprint("rooms_routes", __name__)
_current_user = None
_login_required = None
_page_template = ROOMS_PAGE_TEMPLATE
_rooms_report = None
_configured = False


def configure(login_required, current_user, rooms_report, page_template=None):
    global _configured, _current_user, _login_required, _page_template, _rooms_report
    _current_user = current_user
    _login_required = login_required
    _rooms_report = rooms_report
    if page_template is not None:
        _page_template = page_template
    if _configured:
        return

    @bp.route("/api/rooms/availability")
    @_login_required
    def api_rooms_availability():
        return jsonify(_rooms_report.compute_availability())

    @bp.route("/rooms")
    @_login_required
    def rooms():
        user = _current_user()
        html = (
            _page_template.replace("{{ current_user }}", json.dumps(user["login"]))
            .replace("{{ user_role }}", json.dumps(user["role"]))
            .replace("{{ display_name }}", json.dumps(user["display_name"]))
        )
        response = make_response(html)
        response.headers["Cache-Control"] = "no-store"
        return response

    _configured = True
