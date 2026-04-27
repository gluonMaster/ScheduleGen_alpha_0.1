"""
Shared lesson label helpers for PDF and HTML visualisation.
"""

import math
import re
import unicodedata

from lesson_type_utils import classify_lesson_type


SUBJECT_GROUP_ALIASES = {
    "ukr mus": ("ukrainische musik",),
    "ukrainische musik": ("ukr mus",),
}

_SEPARATOR_RE = re.compile(r"[\s\._\-/+(),]+")


def _is_missing_value(value):
    if value is None:
        return True

    if value.__class__.__name__ in {"NAType", "NaTType"}:
        return True

    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):
        pass

    try:
        return bool(value != value)
    except (TypeError, ValueError):
        return False


def label_text_or_empty(value):
    """Return display text while keeping missing values out of labels."""
    if _is_missing_value(value):
        return ""
    return str(value).strip()


def normalize_label_text(value):
    """
    Normalize subject/group text for conservative token-aware comparisons.
    """
    text = label_text_or_empty(value)
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text).casefold()
    text = _SEPARATOR_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_lesson_type(lesson):
    """
    Resolve lesson type using explicit lesson_type first, then subject rules.
    """
    raw_lesson_type = label_text_or_empty(lesson.get("lesson_type"))
    if raw_lesson_type:
        return raw_lesson_type.casefold()
    return classify_lesson_type(label_text_or_empty(lesson.get("subject")))


def _contains_normalized_phrase(group_text, subject_text, allow_short=False):
    if not group_text or not subject_text:
        return False
    if not allow_short and len(subject_text) < 3:
        return False

    group_tokens = group_text.split()
    subject_tokens = subject_text.split()
    if not group_tokens or not subject_tokens:
        return False

    if len(subject_tokens) == 1 and not allow_short and len(subject_tokens[0]) < 3:
        return False

    max_start = len(group_tokens) - len(subject_tokens)
    for start in range(max_start + 1):
        if group_tokens[start:start + len(subject_tokens)] == subject_tokens:
            return True
    return False


def group_name_contains_subject(subject, group):
    """
    Return True when the group name already communicates the subject.
    """
    subject_text = normalize_label_text(subject)
    group_text = normalize_label_text(group)
    if not subject_text or not group_text:
        return False

    if _contains_normalized_phrase(group_text, subject_text):
        return True

    for alias in SUBJECT_GROUP_ALIASES.get(subject_text, ()):
        alias_text = normalize_label_text(alias)
        if _contains_normalized_phrase(group_text, alias_text, allow_short=True):
            return True

    return False


def should_show_subject_line(lesson):
    """
    Decide whether a lesson block should render a separate subject line.
    """
    subject = lesson.get("subject")
    if not normalize_label_text(subject):
        return False

    if get_lesson_type(lesson) != "group":
        return True

    return not group_name_contains_subject(subject, lesson.get("group"))
