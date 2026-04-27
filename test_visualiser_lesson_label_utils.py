import math
import os
import sys


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "visualiser"))

from lesson_label_utils import (  # noqa: E402
    group_name_contains_subject,
    normalize_label_text,
    should_show_subject_line,
)


def _lesson(subject, group, lesson_type="group"):
    return {
        "subject": subject,
        "group": group,
        "lesson_type": lesson_type,
    }


def test_group_subject_display_decisions():
    cases = [
        ("Kunst", "Kunst Sa StudioP", False),
        ("Tanz", "Tanz Mo 6-7J", False),
        ("Deutsch", "Deutsch ab 5J Di", False),
        ("Russish", "2D", True),
        ("Russish", "6A", True),
        ("Russisch", "3JC", True),
        ("Mathe", "6B", True),
        ("Mathe", "Mathe 10B", False),
        ("Logorithmika", "4JA_Log", True),
        ("Ukr. Mus.", "Ukrainische Musik Di 5-6J", False),
        ("Russish", "", True),
    ]

    for subject, group, expected in cases:
        actual = should_show_subject_line(_lesson(subject, group))
        assert actual is expected, (subject, group, actual, expected)


def test_non_group_and_missing_subjects():
    assert should_show_subject_line({"subject": "Ind. Mathe", "group": "Ada"}) is True
    assert should_show_subject_line(_lesson("Physik", "Probe", "trial")) is True
    assert should_show_subject_line(_lesson("", "Kunst Sa StudioP")) is False
    assert should_show_subject_line(_lesson(float("nan"), "2D")) is False
    assert should_show_subject_line(_lesson(math.nan, "2D")) is False


def test_normalization_and_short_subjects():
    assert normalize_label_text(None) == ""
    assert normalize_label_text(float("nan")) == ""
    assert normalize_label_text(" Ukr.  Mus. ") == "ukr mus"
    assert group_name_contains_subject("Ukr. Mus.", "Ukrainische Musik Di 5-6J") is True
    assert should_show_subject_line(_lesson("M", "Mathe Mo")) is True
    assert should_show_subject_line(_lesson("M", "M")) is True


if __name__ == "__main__":
    test_group_subject_display_decisions()
    test_non_group_and_missing_subjects()
    test_normalization_and_short_subjects()
    print("visualiser lesson label tests passed")
