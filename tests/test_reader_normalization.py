from math import nan

from reader import ScheduleClass
from scheduler_base import ScheduleOptimizer


def test_schedule_class_normalizes_blank_excel_resource_values():
    class_data = ScheduleClass(
        subject="  Math  ",
        group=nan,
        teacher=nan,
        main_room=nan,
        alternative_rooms=[nan, " 1.01 ", None, ""],
        building=nan,
        duration=45,
        day=nan,
    )

    assert class_data.subject == "Math"
    assert class_data.group == ""
    assert class_data.teacher == ""
    assert class_data.main_room == ""
    assert class_data.possible_rooms == ["1.01"]
    assert class_data.building == ""
    assert class_data.day == ""
    assert class_data.get_groups() == []


def test_optimizer_ignores_nan_teacher_values_when_sorting_resources():
    classes = [
        ScheduleClass(
            subject="Math",
            group="1A",
            teacher="Teacher B",
            main_room="1.01",
            alternative_rooms=[],
            building="Villa",
            duration=45,
            day="Mo",
        ),
        ScheduleClass(
            subject="Music",
            group="2A",
            teacher=nan,
            main_room="1.02",
            alternative_rooms=[],
            building="Villa",
            duration=45,
            day="Di",
        ),
    ]

    optimizer = ScheduleOptimizer(classes)

    assert optimizer.teachers == ["Teacher B"]
    assert optimizer.rooms == ["1.01", "1.02"]
