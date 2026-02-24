// Полный набор кабинетов для каждого здания
var BUILDING_ROOMS = {
    'Villa': ['K.06', 'K.07', 'K.08', 'K.11', '0.05', '0.06', '0.08',
              '1.03', '1.05', '1.06', '1.09', '2.03', '2.04', '2.05', '2.07', '2.09'],
    'Kolibri': ['0.3', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7']
};

var MENU_DAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
var _menuModalEscapeHandler = null;
var _menuInitialized = false;

// === Menu open/close ===
function toggleMenu() {
    var dropdown = document.getElementById('menuDropdown');
    if (!dropdown) return;
    dropdown.classList.toggle('open');
}

function closeMenu() {
    var dropdown = document.getElementById('menuDropdown');
    if (dropdown) dropdown.classList.remove('open');
}

// === Confirmation modal helpers ===
function showMenuConfirmModal(message, onConfirm) {
    hideMenuConfirmModal();

    var overlay = document.createElement('div');
    overlay.className = 'menu-modal-overlay open';
    overlay.innerHTML = [
        '<div class="menu-modal">',
        '  <p>' + message + '</p>',
        '  <button class="menu-modal-btn-yes">Да, создать</button>',
        '  <button class="menu-modal-btn-cancel">Отмена</button>',
        '</div>'
    ].join('');

    document.body.appendChild(overlay);

    var yesBtn = overlay.querySelector('.menu-modal-btn-yes');
    var cancelBtn = overlay.querySelector('.menu-modal-btn-cancel');

    if (yesBtn) {
        yesBtn.addEventListener('click', function() {
            hideMenuConfirmModal();
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            hideMenuConfirmModal();
        });
    }

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            hideMenuConfirmModal();
        }
    });

    _menuModalEscapeHandler = function(e) {
        if (e.key === 'Escape') {
            hideMenuConfirmModal();
        }
    };
    document.addEventListener('keydown', _menuModalEscapeHandler);
}

function hideMenuConfirmModal() {
    var overlay = document.querySelector('.menu-modal-overlay');
    if (overlay && overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
    }
    if (_menuModalEscapeHandler) {
        document.removeEventListener('keydown', _menuModalEscapeHandler);
        _menuModalEscapeHandler = null;
    }
}

// === "Создать новое расписание" entry point ===
function handleNewSchedule() {
    closeMenu();
    showMenuConfirmModal(
        'Вы уверены, что хотите создать новое расписание? Все текущие данные будут удалены.',
        function() {
            _doCreateNewSchedule();
        }
    );
}

// === Core schedule creation logic ===
function _doCreateNewSchedule() {
    // Step 1: Remove all activity blocks from all containers
    document.querySelectorAll('.schedule-container .activity-block').forEach(function(b) {
        b.parentNode.removeChild(b);
    });

    // Step 2: Capture current grid row count before removing tables (keeps bounds consistent)
    var anyTable = document.querySelector('.schedule-container .schedule-grid');
    var rowCount = anyTable ? anyTable.querySelectorAll('tbody tr').length : null;

    // Step 3: Remove existing schedule-grid tables from all containers
    document.querySelectorAll('.schedule-container .schedule-grid').forEach(function(t) {
        t.parentNode.removeChild(t);
    });

    // Step 4: Rebuild tables for each building
    var containers = document.querySelectorAll('.schedule-container');
    containers.forEach(function(container) {
        var building = container.getAttribute('data-building');
        var rooms = BUILDING_ROOMS[building];
        if (!rooms) {
            console.warn('Нет конфигурации кабинетов для здания:', building);
            return;
        }

        var table = _buildFullTable(building, rooms, rowCount);
        container.appendChild(table);

        // Step 5: Update container width
        var timeTh = table.querySelector('thead th.time-cell');
        var tw = timeTh ? (parseFloat(window.getComputedStyle(timeTh).width) || 80) : 80;
        var dcw = (typeof dayCellWidth !== 'undefined') ? dayCellWidth : 100;
        var totalCols = MENU_DAYS.length * rooms.length;
        container.style.width = (tw + totalCols * dcw) + 'px';
    });

    // Step 6: Finalize
    if (typeof updateActivityPositions === 'function') {
        updateActivityPositions();
    }

    // Step 7: Reset day visibility to "all days visible"
    document.querySelectorAll('.toggle-day-button.active').forEach(function(btn) {
        btn.classList.remove('active');
    });
    MENU_DAYS.forEach(function(day) {
        document.querySelectorAll('th.day-' + day + ', td.day-' + day).forEach(function(cell) {
            cell.style.display = '';
        });
    });

    _showNotification('Создано новое пустое расписание');
}

// === Table builder ===
function _buildFullTable(building, rooms, rowCount) {
    var gStart = (typeof gridStart !== 'undefined') ? gridStart : 540;   // 09:00
    var tInterval = (typeof timeInterval !== 'undefined') ? timeInterval : 5;
    var cellH = (typeof gridCellHeight !== 'undefined') ? gridCellHeight : 15;
    var dcw = (typeof dayCellWidth !== 'undefined') ? dayCellWidth : 100;
    var tcw = 80;

    // Prefer the rowCount derived from the old table to preserve actual gridEnd.
    var rowsCount = rowCount;
    if (!rowsCount || rowsCount <= 0) {
        var gEnd = 1185; // 19:45 fallback
        rowsCount = Math.floor((gEnd - gStart) / tInterval) + 1; // inclusive end
    }

    var table = document.createElement('table');
    table.className = 'schedule-grid';

    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');

    var timeTh = document.createElement('th');
    timeTh.className = 'time-cell';
    timeTh.textContent = 'Время';
    timeTh.style.width = tcw + 'px';
    headRow.appendChild(timeTh);

    MENU_DAYS.forEach(function(day) {
        for (var col = 0; col < rooms.length; col++) {
            var th = document.createElement('th');
            th.className = 'day-' + day;
            th.innerHTML = day + '<br>' + rooms[col];
            th.style.width = dcw + 'px';
            headRow.appendChild(th);
        }
    });

    thead.appendChild(headRow);

    var tbody = document.createElement('tbody');
    var timeStep = Math.max(1, Math.floor(15 / tInterval));

    for (var r = 0; r < rowsCount; r++) {
        var tr = document.createElement('tr');

        var timeTd = document.createElement('td');
        timeTd.className = 'time-cell';
        timeTd.setAttribute('data-row', r);
        timeTd.setAttribute('data-col', 'time');
        timeTd.textContent = (r % timeStep === 0) ? _formatTime(gStart + r * tInterval) : '';
        timeTd.style.height = cellH + 'px';
        tr.appendChild(timeTd);

        MENU_DAYS.forEach(function(day) {
            for (var col = 0; col < rooms.length; col++) {
                var td = document.createElement('td');
                td.className = 'day-' + day;
                td.setAttribute('data-row', r);
                td.setAttribute('data-col', col);
                td.style.height = cellH + 'px';
                tr.appendChild(td);
            }
        });

        tbody.appendChild(tr);
    }

    table.appendChild(thead);
    table.appendChild(tbody);
    return table;
}

function _formatTime(minutes) {
    var h = Math.floor(minutes / 60);
    var m = minutes % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
}

// === Notification helper ===
function _showNotification(message) {
    var note = document.createElement('div');
    note.textContent = message;
    note.style.cssText = [
        'position:fixed',
        'bottom:30px',
        'left:50%',
        'transform:translateX(-50%)',
        'background:#333',
        'color:#fff',
        'padding:12px 24px',
        'border-radius:6px',
        'z-index:10200',
        'font-size:14px',
        'box-shadow:0 4px 12px rgba(0,0,0,0.25)'
    ].join(';');

    document.body.appendChild(note);
    setTimeout(function() {
        if (note.parentNode) note.parentNode.removeChild(note);
    }, 3000);
}

// === Initialization ===
function initMenu() {
    if (_menuInitialized) {
        return;
    }

    document.addEventListener('click', function(e) {
        var btn = document.getElementById('menuButton');
        var dd = document.getElementById('menuDropdown');
        if (!dd) return;
        if (btn && btn.contains(e.target)) return;
        if (dd.contains(e.target)) return;
        closeMenu();
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeMenu();
    });

    _menuInitialized = true;
}

// Exports
window.initMenu = initMenu;
window.toggleMenu = toggleMenu;
window.closeMenu = closeMenu;
window.handleNewSchedule = handleNewSchedule;
