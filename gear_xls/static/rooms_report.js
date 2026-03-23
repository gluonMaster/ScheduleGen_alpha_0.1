var _availData = null;
var _selectedBuilding = "";
var _selectedRoom = "";
var _selectedDays = [];
var _searchQuery = "";
var _requestedDurationMinutes = 0;

var DAY_ORDER = ["Mo", "Di", "Mi", "Do", "Fr", "Sa"];
var SLOT_MINUTES = 15;

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function parseTimeToMin(t) {
  var match = String(t || "").trim().match(/^(\d{1,2}):(\d{2})$/);
  var hour;
  var minute;

  if (!match) return -1;
  hour = parseInt(match[1], 10);
  minute = parseInt(match[2], 10);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return -1;
  return hour * 60 + minute;
}

function formatMin(m) {
  return (
    (m < 600 ? "0" : "") +
    Math.floor(m / 60) +
    ":" +
    (m % 60 < 10 ? "0" : "") +
    (m % 60)
  );
}

function parseDurationMinutes(value) {
  var parsed = parseInt(String(value || "").trim(), 10);
  if (isNaN(parsed) || parsed <= 0) return 0;
  return parsed;
}

function formatDuration(minutes) {
  var hours = Math.floor(minutes / 60);
  var restMinutes = minutes % 60;
  var parts = [];

  if (hours) {
    parts.push(hours + " ч");
  }
  if (restMinutes) {
    parts.push(restMinutes + " мин");
  }
  if (!parts.length) {
    return "0 мин";
  }
  return parts.join(" ");
}

function makeWindow(startMin, endMin) {
  return {
    start: formatMin(startMin),
    end: formatMin(endMin),
    startMin: startMin,
    endMin: endMin,
    duration: endMin - startMin,
  };
}

function deriveFreeWindows(occupied, dayStart, dayEnd) {
  var sorted;
  var merged = [];
  var free = [];
  var cursor = dayStart;
  var i;

  if (!occupied.length) {
    return [makeWindow(dayStart, dayEnd)];
  }

  sorted = occupied.slice().sort(function(a, b) {
    return a.start - b.start;
  });

  for (i = 0; i < sorted.length; i += 1) {
    var start = Math.max(dayStart, sorted[i].start);
    var end = Math.min(dayEnd, sorted[i].end);

    if (start < 0 || end <= start) continue;
    if (merged.length && start <= merged[merged.length - 1].end) {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, end);
    } else {
      merged.push({ start: start, end: end });
    }
  }

  if (!merged.length) {
    return [makeWindow(dayStart, dayEnd)];
  }

  for (i = 0; i < merged.length; i += 1) {
    if (cursor < merged[i].start) {
      free.push(makeWindow(cursor, merged[i].start));
    }
    cursor = Math.max(cursor, merged[i].end);
  }

  if (cursor < dayEnd) {
    free.push(makeWindow(cursor, dayEnd));
  }

  return free.filter(function(windowItem) {
    return windowItem.duration > 0;
  });
}

function showError(msg) {
  var el = document.getElementById("rooms-table-wrap");
  if (el) {
    el.innerHTML = '<p style="color:red;padding:12px">' + escapeHtml(msg) + "</p>";
  }
}

function getBuildings(data) {
  return Object.keys((data && data.buildings) || {}).sort();
}

function compareText(a, b) {
  return String(a || "").localeCompare(String(b || ""), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function normalizeSearchText(value) {
  return String(value || "")
    .trim()
    .replace(/,/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function getRoomsForBuilding(data, building) {
  var buildings = (data && data.buildings) || {};

  if (building) {
    return (((buildings[building] || {}).rooms) || []).slice().sort(compareText);
  }

  var seen = {};
  var rooms = [];

  getBuildings(data).forEach(function(name) {
    (((buildings[name] || {}).rooms) || []).forEach(function(room) {
      var key = String(room || "").toLowerCase();

      if (!seen[key]) {
        seen[key] = true;
        rooms.push(room);
      }
    });
  });

  return rooms.sort(compareText);
}

function getOccupiedRoomsForBuilding(buildingData) {
  var seen = {};
  var rooms = [];

  Object.keys((buildingData && buildingData.days) || {}).forEach(function(day) {
    Object.keys((((buildingData || {}).days || {})[day]) || {}).forEach(function(room) {
      var key = String(room || "").toLowerCase();

      if (!seen[key]) {
        seen[key] = true;
        rooms.push(room);
      }
    });
  });

  return rooms.sort(compareText);
}

function getRoomCombos(data) {
  var seen = {};
  var combos = [];

  getBuildings(data).forEach(function(building) {
    (((data.buildings[building] || {}).rooms) || []).forEach(function(room) {
      var key = building + "::" + room;

      if (seen[key]) return;
      seen[key] = true;
      combos.push({
        building: building,
        room: room,
        text: normalizeSearchText(room + " " + building),
      });
    });
  });

  return combos.sort(function(a, b) {
    var byRoom = compareText(a.room, b.room);

    if (byRoom) return byRoom;
    return compareText(a.building, b.building);
  });
}

function getActiveDays() {
  return _selectedDays.length ? _selectedDays.slice() : DAY_ORDER.slice();
}

function getTargetsFromFilters(data) {
  var buildings = _selectedBuilding ? [_selectedBuilding] : getBuildings(data);
  var targets = [];

  buildings.forEach(function(building) {
    var buildingData = (data.buildings || {})[building];
    var rooms;

    if (!buildingData) return;
    rooms = (buildingData.rooms || []).slice();
    if (_selectedRoom) {
      rooms = rooms.filter(function(room) {
        return room === _selectedRoom;
      });
    }
    rooms.sort(compareText).forEach(function(room) {
      targets.push({ building: building, room: room });
    });
  });

  return targets;
}

function filterWindowsByDuration(windows, requestedDuration) {
  if (!requestedDuration) {
    return windows.slice();
  }
  return windows.filter(function(windowItem) {
    return windowItem.duration >= requestedDuration;
  });
}

function formatWindowList(windows, includeDuration) {
  return windows
    .map(function(windowItem) {
      var label = windowItem.start + "–" + windowItem.end;
      if (includeDuration) {
        label += " (" + formatDuration(windowItem.duration) + ")";
      }
      return label;
    })
    .join(", ");
}

function applySearchStateFromInputs() {
  var searchBox = document.getElementById("search-box");
  var durationInput = document.getElementById("duration-minutes");

  _searchQuery = searchBox ? searchBox.value.trim() : "";
  _requestedDurationMinutes = durationInput
    ? parseDurationMinutes(durationInput.value)
    : 0;
}

function setOptions(select, values, emptyLabel) {
  var parts = ['<option value="">' + escapeHtml(emptyLabel) + "</option>"];

  values.forEach(function(value) {
    parts.push('<option value="' + escapeHtml(value) + '">' + escapeHtml(value) + "</option>");
  });
  select.innerHTML = parts.join("");
}

function populateFilters(data) {
  var buildingSelect = document.getElementById("filter-building");
  var roomSelect = document.getElementById("filter-room");
  var buildings = getBuildings(data);

  if (_selectedBuilding && buildings.indexOf(_selectedBuilding) === -1) {
    _selectedBuilding = "";
    _selectedRoom = "";
  }

  setOptions(buildingSelect, buildings, "Все");
  buildingSelect.value = _selectedBuilding;

  function refillRooms() {
    var rooms = getRoomsForBuilding(data, _selectedBuilding);

    if (_selectedRoom && rooms.indexOf(_selectedRoom) === -1) {
      _selectedRoom = "";
    }

    setOptions(roomSelect, rooms, "Все");
    roomSelect.value = _selectedRoom;
  }

  refillRooms();

  buildingSelect.onchange = function() {
    _selectedBuilding = this.value;
    _selectedRoom = "";
    refillRooms();
    renderTable();
  };

  roomSelect.onchange = function() {
    _selectedRoom = this.value;
    renderTable();
  };
}

function populateAutocomplete(data) {
  var datalist = document.getElementById("room-suggestions");
  var items = getRoomCombos(data).map(function(item) {
    return item.room + " " + item.building;
  });

  datalist.innerHTML = items
    .map(function(item) {
      return '<option value="' + escapeHtml(item) + '"></option>';
    })
    .join("");
}

function loadAvailability() {
  fetch("/api/rooms/availability")
    .then(function(r) {
      if (r.status === 401) {
        window.location.href = "/login";
        return null;
      }
      if (!r.ok) {
        showError("Ошибка загрузки данных: " + r.status);
        return null;
      }
      return r.json();
    })
    .then(function(data) {
      if (!data) return;
      _availData = data;
      populateFilters(data);
      populateAutocomplete(data);
      applySearchStateFromInputs();
      renderTable();
    })
    .catch(function(e) {
      showError("Сетевая ошибка: " + e.message);
    });
}

function buildColumns(data) {
  var activeBuildings;
  var activeDays;
  var columns = [];

  if (!data || !data.buildings) return [];

  activeBuildings = _selectedBuilding ? [_selectedBuilding] : getBuildings(data);
  activeDays = getActiveDays();

  activeBuildings.forEach(function(building) {
    var buildingData = data.buildings[building];
    var allRooms;
    var rooms;

    if (!buildingData) return;

    allRooms = (buildingData.rooms || []).slice();
    if (_selectedRoom) {
      rooms = allRooms.filter(function(room) {
        return room === _selectedRoom;
      });
    } else {
      rooms = getOccupiedRoomsForBuilding(buildingData);
      if (!rooms.length) {
        rooms = allRooms;
      }
    }

    rooms.sort(compareText);
    activeDays.forEach(function(day) {
      rooms.forEach(function(room) {
        var daySlots = (((buildingData.days || {})[day] || {})[room]) || [];
        columns.push({
          building: building,
          day: day,
          room: room,
          slots: daySlots,
        });
      });
    });
  });

  return columns;
}

function buildSlotLookup(columns) {
  columns.forEach(function(column) {
    var lookup = {};

    (column.slots || []).forEach(function(slot) {
      var start = parseTimeToMin(slot.start);
      var end = parseTimeToMin(slot.end);
      var first = Math.ceil(start / SLOT_MINUTES) * SLOT_MINUTES;
      var t;

      if (start < 0 || end <= start) return;
      for (t = first; t < end; t += SLOT_MINUTES) {
        lookup[t] = slot;
      }
    });

    column.lookup = lookup;
  });
}

function renderTable() {
  var thead = document.getElementById("rooms-thead");
  var tbody = document.getElementById("rooms-tbody");
  var freeEl = document.getElementById("free-windows");
  var columns;
  var singleBuilding;
  var head;
  var gridStart;
  var gridEnd;
  var rows = [];
  var time;

  if (!_availData || !thead || !tbody) return;

  columns = buildColumns(_availData);
  buildSlotLookup(columns);

  if (!columns.length) {
    thead.innerHTML = "<tr><th>Время</th></tr>";
    tbody.innerHTML = '<tr><td>Нет данных для выбранных фильтров</td></tr>';
    if (freeEl) freeEl.innerHTML = "";
    renderFreeWindows();
    return;
  }

  singleBuilding = !!_selectedBuilding || getBuildings(_availData).length === 1;
  head = ["<tr><th>Время</th>"];

  columns.forEach(function(column) {
    var label = column.day + " " + column.room;

    if (!singleBuilding) label += " (" + column.building + ")";
    head.push("<th>" + escapeHtml(label) + "</th>");
  });
  head.push("</tr>");

  gridStart = parseTimeToMin(_availData.grid_start);
  gridEnd = parseTimeToMin(_availData.grid_end);

  for (time = gridStart; time < gridEnd; time += SLOT_MINUTES) {
    rows.push("<tr>");
    rows.push("<th>" + (time % 60 === 0 ? escapeHtml(formatMin(time)) : "") + "</th>");
    columns.forEach(function(column) {
      var slot = column.lookup[time] || null;
      var cls;
      var titleText;
      var text;

      if (!slot) {
        rows.push('<td class="slot-free"></td>');
        return;
      }

      cls = /^(individual|nachhilfe)$/i.test(slot.lesson_type || "")
        ? "slot-busy-ind"
        : "slot-busy";
      titleText = [slot.subject || "", slot.students || ""].join(" ").trim();
      titleText = titleText
        ? titleText + " / " + (slot.teacher || "")
        : (slot.teacher || "");
      text = (slot.subject || "").slice(0, 10) || "*";

      rows.push(
        '<td class="' +
          cls +
          '" title="' +
          escapeHtml(titleText.trim()) +
          '">' +
          escapeHtml(text) +
          "</td>"
      );
    });
    rows.push("</tr>");
  }

  thead.innerHTML = head.join("");
  tbody.innerHTML = rows.join("");
  renderFreeWindows();
}

function resolveSearchTargets(data, query) {
  var lower = normalizeSearchText(query);
  var combos = getRoomCombos(data);

  if (!lower) return [];

  var exactCombo = combos.filter(function(item) {
    return item.text === lower;
  });

  if (exactCombo.length) return exactCombo;

  return combos.filter(function(item) {
    return normalizeSearchText(item.room) === lower;
  });
}

function renderFreeWindows() {
  var target = document.getElementById("free-windows");
  var resolved = [];
  var activeDays;
  var requestedDuration;
  var gridStart;
  var gridEnd;
  var unique = {};
  var parts = [];
  var sectionsAdded = 0;

  if (!_availData || !target) return;

  activeDays = getActiveDays();
  requestedDuration = _requestedDurationMinutes;

  if (_searchQuery) {
    resolved = resolveSearchTargets(_availData, _searchQuery);
    if (!resolved.length) {
      target.innerHTML = "<p>Аудитория не найдена: " + escapeHtml(_searchQuery) + "</p>";
      return;
    }
  } else if (_selectedBuilding && _selectedRoom) {
    resolved = [{ building: _selectedBuilding, room: _selectedRoom }];
  } else if (requestedDuration > 0) {
    resolved = getTargetsFromFilters(_availData);
  } else {
    target.innerHTML = "";
    return;
  }

  gridStart = parseTimeToMin(_availData.grid_start);
  gridEnd = parseTimeToMin(_availData.grid_end);

  if (requestedDuration > 0) {
    parts.push(
      "<p>Показаны только окна, где помещается событие длительностью не менее " +
        escapeHtml(formatDuration(requestedDuration)) +
        ".</p>"
    );
  }

  resolved.forEach(function(item) {
    var key = item.building + "::" + item.room;
    var buildingData;
    var hasAnyOccupied = false;
    var fullyFreeText = "";
    var lines = [];

    if (unique[key]) return;
    unique[key] = true;

    buildingData = _availData.buildings[item.building] || { days: {} };

    activeDays.forEach(function(day) {
      var slots = (((buildingData.days || {})[day] || {})[item.room]) || [];
      var occupied = slots
        .map(function(slot) {
          return { start: parseTimeToMin(slot.start), end: parseTimeToMin(slot.end) };
        })
        .filter(function(slot) {
          return slot.start >= 0 && slot.end > slot.start;
        });
      var free = filterWindowsByDuration(
        deriveFreeWindows(occupied, gridStart, gridEnd),
        requestedDuration
      );
      var text = "нет свободного времени";

      if (occupied.length) {
        hasAnyOccupied = true;
      }
      if (!requestedDuration && !occupied.length) {
        text = "весь день";
      } else if (free.length) {
        text = formatWindowList(free, requestedDuration > 0);
      }

      if (requestedDuration > 0) {
        if (free.length) {
          lines.push("<li>" + escapeHtml(day + ": " + text) + "</li>");
        }
        return;
      }

      lines.push("<li>" + escapeHtml(day + ": " + text) + "</li>");
    });

    if (!requestedDuration && !hasAnyOccupied) {
      sectionsAdded += 1;
      if (activeDays.length === DAY_ORDER.length) {
        fullyFreeText =
          "\u0410\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u044f " +
          item.room +
          " (" +
          item.building +
          ") \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u0430 \u0432\u043e \u0432\u0441\u0435 \u0440\u0430\u0431\u043e\u0447\u0438\u0435 \u0434\u043d\u0438.";
      } else if (activeDays.length > 1) {
        fullyFreeText =
          "\u0410\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u044f " +
          item.room +
          " (" +
          item.building +
          ") \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u0430 \u0432\u043e \u0432\u0441\u0435 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0435 \u0434\u043d\u0438.";
      } else {
        fullyFreeText =
          "\u0410\u0443\u0434\u0438\u0442\u043e\u0440\u0438\u044f " +
          item.room +
          " (" +
          item.building +
          ") \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u0430 \u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435 \u0432\u0441\u0435\u0433\u043e \u0434\u043d\u044f (" +
          activeDays[0] +
          ").";
      }
      parts.push("<p>" + escapeHtml(fullyFreeText) + "</p>");
      return;
    }

    if (!lines.length) {
      return;
    }

    sectionsAdded += 1;
    parts.push(
      "<h3>Аудитория " +
        escapeHtml(item.room) +
        " (" +
        escapeHtml(item.building) +
        ") — свободное время:</h3>"
    );
    parts.push("<ul>");
    parts.push(lines.join(""));
    parts.push("</ul>");
  });

  if (!sectionsAdded) {
    if (requestedDuration > 0) {
      target.innerHTML =
        "<p>Не найдено свободных окон длительностью не менее " +
        escapeHtml(formatDuration(requestedDuration)) +
        " для выбранных фильтров.</p>";
      return;
    }
    target.innerHTML = "";
    return;
  }

  target.innerHTML = parts.join("");
}

function _wireDayFilters() {
  var allBox = document.getElementById("d-all");
  var boxes = DAY_ORDER.map(function(day) {
    return document.getElementById("d-" + day);
  });

  allBox.onchange = function() {
    if (!this.checked) return;
    boxes.forEach(function(box) {
      box.checked = false;
    });
    _selectedDays = [];
    renderTable();
  };

  boxes.forEach(function(box, index) {
    box.onchange = function() {
      if (allBox.checked) allBox.checked = false;
      _selectedDays = boxes
        .map(function(item, idx) {
          return item.checked ? DAY_ORDER[idx] : null;
        })
        .filter(function(day) {
          return !!day;
        });
      if (!_selectedDays.length) {
        allBox.checked = true;
      }
      renderTable();
    };
  });
}

document.addEventListener("DOMContentLoaded", function() {
  var durationInput = document.getElementById("duration-minutes");

  loadAvailability();

  document.getElementById("btn-search").addEventListener("click", function() {
    applySearchStateFromInputs();
    renderTable();
  });

  document.getElementById("search-box").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      applySearchStateFromInputs();
      renderTable();
    }
  });

  durationInput.addEventListener("input", function() {
    _requestedDurationMinutes = parseDurationMinutes(this.value);
    renderTable();
  });

  durationInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      applySearchStateFromInputs();
      renderTable();
    }
  });

  document.getElementById("btn-refresh").addEventListener("click", loadAvailability);
  _wireDayFilters();
});
