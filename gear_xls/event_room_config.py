from __future__ import annotations

from gear_xls.room_name_utils import normalize_building_name, normalize_room_name


EVENT_ROOM_SCOPE = {
    "Villa": ("0.04", "0.06", "0.08", "2.04"),
    "Kolibri": ("0.3", "0.2"),
}


def normalize_room_key(building: object, room: object) -> tuple[str, str]:
    normalized_building = normalize_building_name(building)
    normalized_room = normalize_room_name(room, normalized_building)
    return normalized_building, normalized_room


def get_event_room_config() -> dict[str, list[str]]:
    return {building: list(rooms) for building, rooms in EVENT_ROOM_SCOPE.items()}


def is_event_room(building: object, room: object) -> bool:
    normalized_building, normalized_room = normalize_room_key(building, room)
    return normalized_room in EVENT_ROOM_SCOPE.get(normalized_building, ())
