(function () {
  "use strict";

  var EVENT_ROLE = "event_manager";
  var EVENT_LESSON_TYPE = "veranstaltung";
  var EVENT_SUBJECT = "Veranstaltung";
  var EVENT_INTERVAL = 15;
  var EVENT_DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"];
  var EVENT_ROOM_SCOPE = window.EVENT_ROOM_SCOPE || {
    Villa: ["0.04", "0.06", "0.08", "2.04"],
    Kolibri: ["0.3", "0.2"],
  };
  var DEFAULT_GRID_START = 9 * 60;
  var DEFAULT_GRID_END = 20 * 60;
  var DEFAULT_EVENT_COLOR = "#7c3aed";

  var gridStartMinutes = DEFAULT_GRID_START;
  var gridEndMinutes = DEFAULT_GRID_END;
  var initialized = false;

  function isEventManagerRole() {
    return window.USER_ROLE === EVENT_ROLE;
  }

  function getGridStart() {
    var value = Number(window.gridStart);
    return isFinite(value) ? value : gridStartMinutes;
  }

  function getGridEnd() {
    return gridEndMinutes;
  }

  function parseClock(value) {
    var match = String(value || "").trim().match(/^(\d{1,2}):(\d{2})$/);
    var hours;
    var minutes;

    if (!match) {
      return null;
    }
    hours = parseInt(match[1], 10);
    minutes = parseInt(match[2], 10);
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      return null;
    }
    return hours * 60 + minutes;
  }

  function formatClock(totalMinutes) {
    var hours = Math.floor(totalMinutes / 60);
    var minutes = totalMinutes % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function parseTimeRange(startTime, endTime) {
    var start = parseClock(startTime);
    var end = parseClock(endTime);

    if (start === null || end === null || end <= start) {
      return null;
    }
    return { start: start, end: end };
  }

  function floorToInterval(minutes) {
    return Math.floor(minutes / EVENT_INTERVAL) * EVENT_INTERVAL;
  }

  function ceilToInterval(minutes) {
    return Math.ceil(minutes / EVENT_INTERVAL) * EVENT_INTERVAL;
  }

  function normalizeBuilding(building) {
    var value = String(building || "").trim();
    if (value.toLowerCase() === "villa") {
      return "Villa";
    }
    if (value.toLowerCase() === "kolibri") {
      return "Kolibri";
    }
    return value;
  }

  function normalizeRoom(room, building) {
    var value = String(room || "").trim();
    var prefix = "";

    building = normalizeBuilding(building);
    if (building === "Villa") {
      prefix = "V";
    } else if (building === "Kolibri") {
      prefix = "K";
    }
    if (prefix && value.length > prefix.length && value.slice(0, prefix.length).toUpperCase() === prefix) {
      return value.slice(prefix.length).trim();
    }
    return value;
  }

  function isEventDay(day) {
    return EVENT_DAYS.indexOf(String(day || "").trim()) !== -1;
  }

  function isEventRoom(building, room) {
    var normalizedBuilding = normalizeBuilding(building);
    var normalizedRoom = normalizeRoom(room, normalizedBuilding);
    var rooms = EVENT_ROOM_SCOPE[normalizedBuilding] || [];
    return rooms.indexOf(normalizedRoom) !== -1;
  }

  function getRoomIndex(building, room) {
    var normalizedBuilding = normalizeBuilding(building);
    var normalizedRoom = normalizeRoom(room, normalizedBuilding);
    var rooms = EVENT_ROOM_SCOPE[normalizedBuilding] || [];
    return rooms.indexOf(normalizedRoom);
  }

  function isTimeRangeInsideGrid(startTime, endTime) {
    var range = parseTimeRange(startTime, endTime);
    var start = getGridStart();
    var end = getGridEnd();

    return !!(range && range.start >= start && range.end <= end);
  }

  function resolveRowsForBlock(block) {
    var lessonType = String((block && block.lesson_type) || (block && block.lessonType) || "").trim();
    var range = parseTimeRange(block && block.start_time, block && block.end_time);
    var visualStart;
    var visualEnd;
    var gridStart = getGridStart();

    if (!range || !isTimeRangeInsideGrid(block.start_time, block.end_time)) {
      return null;
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      if (range.start % EVENT_INTERVAL !== 0 || range.end % EVENT_INTERVAL !== 0) {
        return null;
      }
      visualStart = range.start;
      visualEnd = range.end;
    } else {
      visualStart = floorToInterval(range.start);
      visualEnd = ceilToInterval(range.end);
    }
    if (visualStart < gridStart || visualEnd > getGridEnd() || visualEnd <= visualStart) {
      return null;
    }
    return {
      start_row: Math.floor((visualStart - gridStart) / EVENT_INTERVAL),
      row_span: Math.floor((visualEnd - visualStart) / EVENT_INTERVAL),
    };
  }

  function normalizeBlockForView(block) {
    var normalized;
    var rows;

    if (!block || typeof block !== "object") {
      return null;
    }
    normalized = Object.assign({}, block);
    normalized.building = normalizeBuilding(normalized.building);
    normalized.room = normalizeRoom(normalized.room || normalized.room_display, normalized.building);
    normalized.day = String(normalized.day || "").trim();
    normalized.lesson_type = String(normalized.lesson_type || "group").trim() || "group";
    if (!isEventDay(normalized.day) || !isEventRoom(normalized.building, normalized.room)) {
      return null;
    }
    rows = resolveRowsForBlock(normalized);
    if (!rows) {
      return null;
    }
    normalized.start_row = rows.start_row;
    normalized.row_span = rows.row_span;
    return normalized;
  }

  function filterBlocks(blocks) {
    if (!Array.isArray(blocks)) {
      return blocks;
    }
    return blocks
      .map(function (block) {
        return normalizeBlockForView(block);
      })
      .filter(Boolean);
  }

  function filterSchedulePayload(data) {
    var filtered;

    if (!isEventManagerRole() || !data || typeof data !== "object") {
      return data;
    }
    filtered = Object.assign({}, data);
    if (Array.isArray(data.base)) {
      filtered.base = filterBlocks(data.base);
    }
    if (Array.isArray(data.individual)) {
      filtered.individual = filterBlocks(data.individual);
    }
    if (Array.isArray(data.blocks)) {
      filtered.blocks = filterBlocks(data.blocks);
    }
    return filtered;
  }

  function stripHtml(value) {
    var node = document.createElement("textarea");
    node.innerHTML = String(value || "").replace(/<[^>]+>/g, "");
    return node.value.trim();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function blockLines(block) {
    return String((block && block.innerHTML) || "")
      .split(/<br\s*\/?>/i)
      .map(stripHtml);
  }

  function collectBlockFromElement(element) {
    var lines = blockLines(element);
    var timeText = (element.getAttribute("data-start-time") || "") + "-" + (element.getAttribute("data-end-time") || "");
    var timeMatch;
    var subject = element.querySelector("strong");
    var building =
      element.getAttribute("data-building") ||
      (element.closest(".schedule-container") && element.closest(".schedule-container").getAttribute("data-building")) ||
      "";
    var lessonType = element.getAttribute("data-lesson-type") || "";
    var block;
    var startMinutes;
    var endMinutes;

    if (!timeText || timeText === "-") {
      timeText = lines[4] || "";
    }
    timeMatch = String(timeText).match(/(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})/);
    if (!timeMatch) {
      return null;
    }
    startMinutes = parseClock(timeMatch[1]);
    endMinutes = parseClock(timeMatch[2]);
    if (startMinutes === null || endMinutes === null || endMinutes <= startMinutes) {
      return null;
    }
    if (!lessonType) {
      lessonType = (subject && subject.textContent.trim()) === EVENT_SUBJECT ? EVENT_LESSON_TYPE : "group";
    }
    block = {
      id: element.getAttribute("data-block-id") || undefined,
      day: element.getAttribute("data-day") || "",
      building: building,
      room: element.getAttribute("data-room") || lines[3] || "",
      start_time: formatClock(startMinutes),
      end_time: formatClock(endMinutes),
      lesson_type: lessonType,
      subject: subject ? subject.textContent.trim() : lines[0] || "",
      teacher: lines[1] || "",
      students: lines[2] || "",
      color: element.style.backgroundColor || "",
      created_by: element.getAttribute("data-created-by") || "",
      created_by_name: element.getAttribute("data-created-by-name") || "",
      owner_kind: element.getAttribute("data-owner-kind") || "",
      version: element.getAttribute("data-version") || "",
    };
    if (element.getAttribute("data-trial-dates")) {
      block.trial_dates = parseJsonArray(element.getAttribute("data-trial-dates"));
    }
    if (element.getAttribute("data-event-dates")) {
      block.event_dates = parseJsonArray(element.getAttribute("data-event-dates"));
    }
    return normalizeBlockForView(block);
  }

  function parseJsonArray(raw) {
    try {
      var parsed = JSON.parse(raw || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function collectBlocksFromDom() {
    return Array.from(document.querySelectorAll(".schedule-container .activity-block"))
      .map(collectBlockFromElement)
      .filter(Boolean);
  }

  function deriveGridBoundsFromDom() {
    var oldInterval = Number(window.timeInterval) || 5;
    var maxRow = -1;

    gridStartMinutes = getGridStart();
    document.querySelectorAll(".schedule-grid tbody td.time-cell[data-row]").forEach(function (cell) {
      var row = parseInt(cell.getAttribute("data-row"), 10);
      if (!isNaN(row) && row > maxRow) {
        maxRow = row;
      }
    });
    gridEndMinutes = maxRow >= 0 ? gridStartMinutes + maxRow * oldInterval : DEFAULT_GRID_END;
    if (gridEndMinutes <= gridStartMinutes) {
      gridEndMinutes = DEFAULT_GRID_END;
    }
  }

  function ensureBuildingContainer(building) {
    var container = document.querySelector('.schedule-container[data-building="' + cssEscape(building) + '"]');
    var heading;

    if (container) {
      return container;
    }
    heading = document.createElement("h2");
    heading.textContent = "Building: " + building;
    container = document.createElement("div");
    container.className = "schedule-container";
    container.setAttribute("data-building", building);
    document.body.appendChild(heading);
    document.body.appendChild(container);
    return container;
  }

  function buildFixedView() {
    var scopedBuildings = Object.keys(EVENT_ROOM_SCOPE);

    document.body.classList.add("event-manager-fixed-view");
    document.querySelectorAll(".schedule-container[data-building]").forEach(function (container) {
      var building = normalizeBuilding(container.getAttribute("data-building"));
      var visible = scopedBuildings.indexOf(building) !== -1;
      var heading = findPreviousHeading(container);

      container.style.display = visible ? "" : "none";
      if (heading) {
        heading.style.display = visible ? "" : "none";
      }
      if (visible) {
        container.setAttribute("data-building", building);
        container.setAttribute("data-event-manager-view", "1");
        container.querySelectorAll(".activity-block, .schedule-grid").forEach(function (node) {
          node.parentNode.removeChild(node);
        });
      }
    });
    scopedBuildings.forEach(function (building) {
      var container = ensureBuildingContainer(building);
      container.setAttribute("data-event-manager-view", "1");
      container.querySelectorAll(".activity-block, .schedule-grid").forEach(function (node) {
        node.parentNode.removeChild(node);
      });
      container.appendChild(buildTable(building));
    });
  }

  function findPreviousHeading(container) {
    var node = container ? container.previousElementSibling : null;
    while (node) {
      if (/^H[1-6]$/i.test(node.tagName || "")) {
        return node;
      }
      node = node.previousElementSibling;
    }
    return null;
  }

  function buildTable(building) {
    var rooms = EVENT_ROOM_SCOPE[building] || [];
    var rowsCount = Math.floor((getGridEnd() - getGridStart()) / EVENT_INTERVAL) + 1;
    var table = document.createElement("table");
    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    var timeTh = document.createElement("th");
    var tbody = document.createElement("tbody");

    table.className = "schedule-grid event-manager-grid";
    table.setAttribute("data-event-manager-grid", "1");
    timeTh.className = "time-cell";
    timeTh.textContent = "Time";
    headRow.appendChild(timeTh);
    EVENT_DAYS.forEach(function (day) {
      rooms.forEach(function (room, colIndex) {
        var th = document.createElement("th");
        th.className = "day-" + day;
        th.setAttribute("data-day", day);
        th.setAttribute("data-col", String(colIndex));
        th.setAttribute("data-room", room);
        th.innerHTML = escapeHtml(day) + "<br>" + escapeHtml(room);
        headRow.appendChild(th);
      });
    });
    thead.appendChild(headRow);

    for (var rowIndex = 0; rowIndex < rowsCount; rowIndex += 1) {
      var row = document.createElement("tr");
      var timeCell = document.createElement("td");
      timeCell.className = "time-cell";
      timeCell.setAttribute("data-row", String(rowIndex));
      timeCell.setAttribute("data-col", "time");
      timeCell.textContent = formatClock(getGridStart() + rowIndex * EVENT_INTERVAL);
      row.appendChild(timeCell);
      EVENT_DAYS.forEach(function (day) {
        rooms.forEach(function (room, colIndex) {
          var td = document.createElement("td");
          td.className = "day-" + day + " event-manager-cell";
          td.setAttribute("data-day", day);
          td.setAttribute("data-row", String(rowIndex));
          td.setAttribute("data-col", String(colIndex));
          td.setAttribute("data-room", room);
          row.appendChild(td);
        });
      });
      tbody.appendChild(row);
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    return table;
  }

  function renderBlocks(blocks) {
    filterBlocks(blocks).forEach(renderBlock);
    refreshLayout();
  }

  function renderBlock(block) {
    var container;
    var element;
    var colIndex;
    var lessonType;
    var timeText;

    block = normalizeBlockForView(block);
    if (!block) {
      return null;
    }
    container = document.querySelector('.schedule-container[data-building="' + cssEscape(block.building) + '"]');
    colIndex = getRoomIndex(block.building, block.room);
    if (!container || colIndex < 0) {
      return null;
    }
    lessonType = block.lesson_type || "group";
    timeText = (block.start_time || "") + "-" + (block.end_time || "");
    element = document.createElement("div");
    element.className = "activity-block activity-day-" + block.day + " lesson-type-" + lessonType;
    if (block.id) {
      element.setAttribute("data-block-id", block.id);
    }
    element.setAttribute("data-day", block.day);
    element.setAttribute("data-col-index", String(colIndex));
    element.setAttribute("data-building", block.building);
    element.setAttribute("data-room", block.room);
    element.setAttribute("data-lesson-type", lessonType);
    element.setAttribute("data-explicit-lesson-type", lessonType);
    element.setAttribute("data-start-time", block.start_time || "");
    element.setAttribute("data-end-time", block.end_time || "");
    element.setAttribute("data-start-row", String(block.start_row));
    element.setAttribute("data-row-span", String(block.row_span));
    if (lessonType !== EVENT_LESSON_TYPE) {
      element.setAttribute("data-event-manager-readonly", "1");
      element.classList.add("event-manager-readonly-block");
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      element.setAttribute("data-created-by", block.created_by || "");
      element.setAttribute("data-created-by-name", block.created_by_name || block.teacher || "");
      element.setAttribute("data-owner-kind", block.owner_kind || "");
      element.setAttribute("data-version", String(block.version || 1));
      if (Array.isArray(block.event_dates) && block.event_dates.length > 0) {
        element.setAttribute("data-event-dates", JSON.stringify(block.event_dates));
      }
    }
    if (lessonType === "trial" && Array.isArray(block.trial_dates)) {
      element.setAttribute("data-trial-dates", JSON.stringify(block.trial_dates));
    }
    element.style.backgroundColor = block.color || (lessonType === EVENT_LESSON_TYPE ? DEFAULT_EVENT_COLOR : "#FFFBD3");
    if (typeof getContrastTextColor === "function") {
      element.style.color = getContrastTextColor(element.style.backgroundColor);
    }
    element.innerHTML = [
      "<strong>" + escapeHtml(block.subject || "") + "</strong>",
      escapeHtml(block.teacher || ""),
      escapeHtml(block.students || ""),
      escapeHtml(block.room || ""),
      escapeHtml(timeText),
    ].join("<br>");
    container.appendChild(element);
    return element;
  }

  function syncEventBlockFromRows(block) {
    var startRow;
    var rowSpan;
    var startMinutes;
    var endMinutes;
    var room;
    var header;

    if (!block || block.getAttribute("data-lesson-type") !== EVENT_LESSON_TYPE) {
      return null;
    }
    startRow = parseInt(block.getAttribute("data-start-row"), 10);
    rowSpan = parseInt(block.getAttribute("data-row-span"), 10);
    if (isNaN(startRow) || isNaN(rowSpan) || rowSpan < 1) {
      return null;
    }
    startMinutes = getGridStart() + startRow * EVENT_INTERVAL;
    endMinutes = startMinutes + rowSpan * EVENT_INTERVAL;
    if (startMinutes < getGridStart() || endMinutes > getGridEnd()) {
      return null;
    }
    header = findHeaderForBlock(block);
    room = header ? header.getAttribute("data-room") || "" : block.getAttribute("data-room") || "";
    block.setAttribute("data-room", normalizeRoom(room, block.getAttribute("data-building")));
    block.setAttribute("data-start-time", formatClock(startMinutes));
    block.setAttribute("data-end-time", formatClock(endMinutes));
    rewriteBlockRoomAndTime(block, block.getAttribute("data-room"), formatClock(startMinutes) + "-" + formatClock(endMinutes));
    return {
      start_time: formatClock(startMinutes),
      end_time: formatClock(endMinutes),
      room: block.getAttribute("data-room") || "",
    };
  }

  function findHeaderForBlock(block) {
    var container = block.closest(".schedule-container");
    var day = block.getAttribute("data-day");
    var col = block.getAttribute("data-col-index");
    return container ? container.querySelector('th.day-' + cssEscape(day) + '[data-col="' + cssEscape(col) + '"]') : null;
  }

  function rewriteBlockRoomAndTime(block, room, timeText) {
    var parts = String(block.innerHTML || "").split(/<br\s*\/?>/i);
    while (parts.length < 5) {
      parts.push("");
    }
    parts[3] = escapeHtml(room);
    parts[4] = escapeHtml(timeText);
    block.innerHTML = parts.slice(0, 5).join("<br>");
  }

  function refreshLayout() {
    if (typeof window.updateActivityPositions === "function") {
      window.updateActivityPositions();
    }
    if (typeof window.reapplyLessonTypeFilter === "function") {
      window.reapplyLessonTypeFilter();
    }
    if (typeof window.ConflictDetector !== "undefined" && window.ConflictDetector) {
      window.ConflictDetector.highlightConflicts();
    }
  }

  function attachCellCreateHandler() {
    if (document.body.__eventManagerCellCreateAttached) {
      return;
    }
    document.body.__eventManagerCellCreateAttached = true;
    document.addEventListener("click", function (event) {
      var cell;

      if (!isEventManagerRole() || window.editDialogOpen || event.defaultPrevented) {
        return;
      }
      if (event.target.closest && event.target.closest(".activity-block")) {
        return;
      }
      cell = event.target.closest ? event.target.closest('.schedule-container[data-event-manager-view="1"] .schedule-grid td.event-manager-cell') : null;
      if (!cell) {
        return;
      }
      openCreateDialogForCell(event, cell);
    });
  }

  function openCreateDialogForCell(event, cell) {
    var container = cell.closest(".schedule-container");
    var building = container ? container.getAttribute("data-building") || "" : "";
    var day = cell.getAttribute("data-day") || "";
    var room = cell.getAttribute("data-room") || "";
    var row = parseInt(cell.getAttribute("data-row"), 10);
    var col = parseInt(cell.getAttribute("data-col"), 10);
    var startMinutes = getGridStart() + row * EVENT_INTERVAL;
    var endMinutes = Math.min(startMinutes + 60, getGridEnd());
    var details;

    if (!window.openCreateBlockDialog || !isEventDay(day) || !isEventRoom(building, room) || endMinutes <= startMinutes) {
      return;
    }
    event.preventDefault();
    details = {
      building: normalizeBuilding(building),
      day: day,
      room: normalizeRoom(room, building),
      col: col,
      row: row,
      time: formatClock(startMinutes) + "-" + formatClock(endMinutes),
    };
    window.openCreateBlockDialog(event, details.day, details.col, details.row, details.building);
    applyPendingCreateDefaults(details, 0);
  }

  function applyPendingCreateDefaults(details, attempt) {
    var form = document.getElementById("create-form");
    var buildingSelect;
    var daySelect;
    var columnSelect;
    var roomInput;
    var timeInput;

    if (!form) {
      if (attempt < 10) {
        window.setTimeout(function () {
          applyPendingCreateDefaults(details, attempt + 1);
        }, 25);
      }
      return;
    }
    form.setAttribute("data-event-manager-fixed-create", "1");
    buildingSelect = form.querySelector("#new-building");
    daySelect = form.querySelector("#new-day");
    columnSelect = form.querySelector("#new-column");
    roomInput = form.querySelector("#new-room");
    timeInput = form.querySelector("#new-time");
    setFieldValue(buildingSelect, details.building, true);
    setFieldValue(daySelect, details.day, true);
    setFieldValue(columnSelect, String(details.col), true);
    setFieldValue(roomInput, details.room, true);
    setFieldValue(timeInput, details.time, false);
    if (roomInput) {
      roomInput.readOnly = true;
    }
  }

  function setFieldValue(field, value, lockField) {
    if (!field) {
      return;
    }
    field.value = value;
    if (lockField) {
      field.disabled = true;
    }
  }

  function patchGlobalTimeHelpers() {
    window.timeInterval = EVENT_INTERVAL;
    window.daysOrder = EVENT_DAYS.slice();
    window.getTimeByRow = function (rowIndex) {
      var row = parseInt(rowIndex, 10) || 0;
      var start = getGridStart() + row * EVENT_INTERVAL;
      var end = Math.min(start + 60, getGridEnd());
      if (end <= start) {
        end = Math.min(start + EVENT_INTERVAL, getGridEnd());
      }
      return formatClock(start) + "-" + formatClock(end);
    };
  }

  function ensureStyles() {
    var style;

    if (document.getElementById("schedgen-event-manager-view-style")) {
      return;
    }
    style = document.createElement("style");
    style.id = "schedgen-event-manager-view-style";
    style.textContent = [
      'body.event-manager-fixed-view .toggle-day-button[data-day="So"] { display: none !important; }',
      'body.event-manager-fixed-view #menuItemAddColumn,',
      'body.event-manager-fixed-view #menuItemNewSchedule,',
      'body.event-manager-fixed-view .col-add-btn,',
      'body.event-manager-fixed-view .col-delete-btn { display: none !important; }',
      "body.event-manager-fixed-view .schedule-container { max-height: 760px; }",
      "body.event-manager-fixed-view .schedule-grid th,",
      "body.event-manager-fixed-view .schedule-grid td { width: 112px; }",
      "body.event-manager-fixed-view .schedule-grid .time-cell { width: 78px; }",
      "body.event-manager-fixed-view .event-manager-cell { cursor: crosshair; }",
      "body.event-manager-fixed-view .event-manager-readonly-block { cursor: default !important; opacity: 0.86; }",
    ].join("\n");
    document.head.appendChild(style);
  }

  function hideSundayControls() {
    document.querySelectorAll('.toggle-day-button[data-day="So"]').forEach(function (button) {
      button.classList.remove("active");
      button.style.display = "none";
    });
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(String(value || ""));
    }
    return String(value || "").replace(/["\\]/g, "\\$&");
  }

  function init() {
    var initialBlocks;

    if (initialized || !isEventManagerRole()) {
      return;
    }
    initialized = true;
    deriveGridBoundsFromDom();
    patchGlobalTimeHelpers();
    ensureStyles();
    hideSundayControls();
    initialBlocks = collectBlocksFromDom();
    buildFixedView();
    renderBlocks(initialBlocks);
    attachCellCreateHandler();
  }

  window.SchedGenEventManagerView = {
    EVENT_DAYS: EVENT_DAYS.slice(),
    EVENT_INTERVAL: EVENT_INTERVAL,
    EVENT_ROOM_SCOPE: EVENT_ROOM_SCOPE,
    filterSchedulePayload: filterSchedulePayload,
    resolveRowsForBlock: resolveRowsForBlock,
    normalizeBlockForView: normalizeBlockForView,
    isEventRoom: isEventRoom,
    isTimeRangeInsideGrid: isTimeRangeInsideGrid,
    syncEventBlockFromRows: syncEventBlockFromRows,
    renderBlocks: renderBlocks,
    refreshLayout: refreshLayout,
    getGridStart: getGridStart,
    getGridEnd: getGridEnd,
  };

  if (isEventManagerRole()) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})();
