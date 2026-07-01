from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_auth_ui_splits_legacy_lock_and_event_capabilities():
    text = read_text("gear_xls/static/auth_ui.js")

    assert "function isLegacyLockRole(role)" in text
    assert 'function canUseEventEditor(role)' in text
    assert 'function canManageColumns(role)' in text
    assert 'function canPublish(role)' in text
    assert 'function canExport(role)' in text
    assert 'role === "admin" || role === "editor" || role === "organizer"' in text
    assert 'role === "admin" || role === "event_manager"' in text
    assert 'data-owner-kind' in text
    assert 'data-created-by' in text


def test_individual_ui_renders_event_metadata_and_uses_event_api():
    text = read_text("gear_xls/static/individual_ui.js")

    for marker in (
        'data-lesson-type", block.lesson_type || "individual"',
        '"data-created-by"',
        '"data-created-by-name"',
        '"data-owner-kind"',
        '"data-version"',
        '"data-event-dates"',
        'requestJson("/api/events"',
        '"/api/events/" + encodeURIComponent(blockId)',
        "expected_version",
        "replaceInputWithoutAutocomplete(studentsInput",
    ):
        assert marker in text


def test_lesson_type_filter_preserves_veranstaltung_and_non_group_excludes_it():
    text = read_text("gear_xls/js_modules/lesson_type_filter.js")
    menu = read_text("gear_xls/js_modules/menu.js")

    assert "Veranstaltung" in text
    assert "return 'veranstaltung';" in text
    assert "explicitType === 'group' || explicitType === 'veranstaltung'" in text
    assert "lessonType === 'individual' || lessonType === 'nachhilfe' || lessonType === 'trial'" in text
    assert "Только Veranstaltung" in menu
    assert "value: 'veranstaltung'" in menu


def test_conflict_detector_uses_data_attrs_and_event_room_time_only():
    text = read_text("gear_xls/js_modules/conflict_detector.js")

    assert "data-start-time" in text
    assert "data-end-time" in text
    assert "data-room" in text
    assert "hasEvent" in text
    assert "block1.lessonType === 'veranstaltung' || block2.lessonType === 'veranstaltung'" in text
    assert "return null;" in text


def test_legacy_drag_fallbacks_do_not_mutate_veranstaltung():
    drag_fallback = read_text("gear_xls/js_modules/drag_drop_refactored.js")
    block_handlers = read_text("gear_xls/js_modules/block_event_handlers.js")
    drag_service = read_text("gear_xls/js_modules/services/drag_drop_service.js")
    resize = read_text("gear_xls/js_modules/block_resize.js")

    for text in (drag_fallback, block_handlers, drag_service, resize):
        assert "lessonType === 'veranstaltung'" in text


def test_event_room_entries_are_available_to_standard_ui():
    menu = read_text("gear_xls/js_modules/menu.js")
    villa_rooms = read_text("spiski/kabinets_Villa.txt").splitlines()
    kolibri_rooms = read_text("spiski/kabinets_Kolibri.txt").splitlines()

    assert "'0.04'" in menu
    assert "'0.2'" in menu
    assert "0.04" in villa_rooms
    assert "0.2" in kolibri_rooms
