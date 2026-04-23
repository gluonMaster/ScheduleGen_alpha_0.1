from gear_xls.room_name_utils import normalize_room_fields, normalize_room_name


def test_normalize_room_name_strips_building_prefix_for_villa():
    assert normalize_room_name("V2.03", "Villa") == "2.03"
    assert normalize_room_name("VK.07", "Villa") == "K.07"
    assert normalize_room_name("K.07", "Villa") == "K.07"


def test_normalize_room_name_strips_building_prefix_for_kolibri():
    assert normalize_room_name("K3.1", "Kolibri") == "3.1"
    assert normalize_room_name("2.2", "Kolibri") == "2.2"


def test_normalize_room_fields_updates_room_and_room_display():
    block = {
        "building": "Kolibri",
        "room": "K3.1",
        "room_display": "K3.1",
        "lesson_type": "group",
    }

    normalized = normalize_room_fields(block)

    assert normalized["room"] == "3.1"
    assert normalized["room_display"] == "3.1"
    assert block["room"] == "K3.1"
