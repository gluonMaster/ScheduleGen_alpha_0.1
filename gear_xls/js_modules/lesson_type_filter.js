window.currentLessonTypeFilter = 'all';

function classifyLessonType(subject) {
    if (!subject) {
        return 'group';
    }
    if (subject.indexOf('Nachhilfe') !== -1) {
        return 'nachhilfe';
    }
    if (subject.indexOf('Ind.') !== -1) {
        return 'individual';
    }
    return 'group';
}

function getBlockSubjectText(block) {
    if (!block) {
        return '';
    }

    var strongElement = block.querySelector('strong');
    if (strongElement) {
        return (strongElement.textContent || '').trim();
    }

    var firstLine = ((block.innerHTML || '').split(/<br\s*\/?>/i)[0] || '').trim();
    return firstLine.replace(/<\/?[^>]+(>|$)/g, '').trim();
}

function updateBlockLessonType(block) {
    if (!block) {
        return;
    }

    var subject = getBlockSubjectText(block);
    var lessonType = classifyLessonType(subject);
    block.setAttribute('data-lesson-type', lessonType);
}

function applyLessonTypeFilter(filterValue) {
    window.currentLessonTypeFilter = filterValue;

    document.querySelectorAll('.activity-block').forEach(function(block) {
        var lessonType = block.getAttribute('data-lesson-type') || 'group';
        var shouldShow = false;

        if (filterValue === 'all') {
            shouldShow = true;
        } else if (filterValue === 'non-group') {
            shouldShow = lessonType === 'individual' || lessonType === 'nachhilfe';
        } else {
            shouldShow = lessonType === filterValue;
        }

        if (shouldShow) {
            block.classList.remove('lesson-type-filter-hidden');
        } else {
            block.classList.add('lesson-type-filter-hidden');
        }
    });

    document.querySelectorAll('.lesson-filter-item').forEach(function(item) {
        item.classList.remove('lesson-filter-active');
    });

    var activeItem = document.querySelector('.lesson-filter-item[data-filter="' + filterValue + '"]');
    if (activeItem) {
        activeItem.classList.add('lesson-filter-active');
    }
}

function reapplyLessonTypeFilter() {
    applyLessonTypeFilter(window.currentLessonTypeFilter);
}

function initLessonTypeFilter() {
    document.querySelectorAll('.activity-block').forEach(function(block) {
        updateBlockLessonType(block);
    });

    applyLessonTypeFilter('all');
}

window.classifyLessonType = classifyLessonType;
window.updateBlockLessonType = updateBlockLessonType;
window.applyLessonTypeFilter = applyLessonTypeFilter;
window.reapplyLessonTypeFilter = reapplyLessonTypeFilter;
window.initLessonTypeFilter = initLessonTypeFilter;
