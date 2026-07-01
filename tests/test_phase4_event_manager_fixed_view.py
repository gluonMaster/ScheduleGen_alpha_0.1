from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_event_manager_view_script_loads_before_schedule_layers():
    text = read_text("gear_xls/server_routes.py")

    event_view = text.index("/static/event_manager_view.js")
    base_sync = text.index("/static/base_sync_ui.js")
    individual = text.index("/static/individual_ui.js")

    assert event_view < base_sync < individual
    assert "window.EVENT_ROOM_SCOPE" in text
    assert "get_event_room_config()" in text


def test_event_manager_view_defines_fixed_rooms_days_and_15_minute_mapping():
    text = read_text("gear_xls/static/event_manager_view.js")

    assert 'window.USER_ROLE === EVENT_ROLE' in text
    assert 'var EVENT_INTERVAL = 15' in text
    assert 'var EVENT_DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"]' in text
    assert 'Villa: ["0.04", "0.06", "0.08", "2.04"]' in text
    assert 'Kolibri: ["0.3", "0.2"]' in text
    assert "floorToInterval(range.start)" in text
    assert "ceilToInterval(range.end)" in text
    assert 'data-event-manager-view", "1"' in text
    assert "filterSchedulePayload" in text
    assert "syncEventBlockFromRows" in text
    assert "addColumnIfMissing" not in text


def test_event_manager_refresh_paths_filter_and_do_not_create_columns():
    individual = read_text("gear_xls/static/individual_ui.js")
    base = read_text("gear_xls/static/base_sync_ui.js")

    for text in (individual, base):
        assert "SchedGenEventManagerView.filterSchedulePayload" in text
        assert "SchedGenEventManagerView.resolveRowsForBlock" in text
        assert 'currentRole() === "event_manager"' in text
        assert "return -1;" in text


def test_event_manager_polling_and_grid_bounds_are_explicit():
    lock_ui = read_text("gear_xls/static/lock_ui.js")
    individual = read_text("gear_xls/static/individual_ui.js")
    state_manager = read_text("gear_xls/state_manager.py")

    assert 'currentRole() === "event_manager" ? 7000 : 30000' in lock_ui
    assert "shouldDeferIndividualRefresh" in individual
    assert "eventMutationInFlight" in individual
    assert "isEventTimeInsideGrid" in individual
    assert "_EVENT_GRID_START_MINUTES = 9 * 60" in state_manager
    assert "_EVENT_GRID_END_MINUTES = 20 * 60" in state_manager
