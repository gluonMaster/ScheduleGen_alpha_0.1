(function () {
  "use strict";

  var individualRevision = null;
  var syncNoticeTimer = null;
  var activeEditedBlock = null;
  var pendingDragStart = null;
  var activeDrag = null;
  var pendingResize = null;

  function authUi() {
    return window.SchedGenAuthUI || null;
  }

  function baseSyncUi() {
    return window.SchedGenBaseSyncUI || null;
  }

  function currentRole() {
    return authUi() ? authUi().currentRole() : "viewer";
  }

  function isEditableRole() {
    return authUi() ? authUi().isEditableRole(currentRole()) : false;
  }

  function isInEditMode() {
    return !!(authUi() && authUi().isEditMode() && isEditableRole());
  }

  function handleSessionExpired() {
    if (typeof window.handleSessionExpired === "function") {
      window.handleSessionExpired();
    }
  }

  function requestJson(url, method, payload) {
    var options = {
      method: method || "GET",
      headers: { Accept: "application/json" },
    };

    if (typeof payload !== "undefined") {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }

    return fetch(url, options)
      .then(function (response) {
        if (response.status === 401) {
          handleSessionExpired();
          return null;
        }
        return response.text().then(function (text) {
          var data = {};
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (error) {
              data = {};
            }
          }
          return { ok: response.ok, status: response.status, data: data };
        });
      })
      .catch(function (error) {
        console.error("Individual API request failed:", error);
        return null;
      });
  }

  function init() {
    if (!authUi()) {
      return;
    }
    attachOpenEditDialogHook();
    attachGlobalInterceptors();
    attachManagedDragHandlers();
    window.refreshIndividualLayer = refreshIndividualLayer;
    window.SchedGenIndividualUI = {
      getIndividualRevision: function () {
        return individualRevision;
      },
      handleIndividualRevision: handleIndividualRevision,
      refreshIndividualLayer: refreshIndividualLayer,
    };
    refreshIndividualLayer();
  }

  function attachGlobalInterceptors() {
    if (document.body.__individualUiHooksAttached) {
      return;
    }
    document.body.__individualUiHooksAttached = true;

    document.addEventListener(
      "submit",
      function (event) {
        if (event.target && event.target.id === "create-form") {
          interceptCreateSubmit(event);
        } else if (event.target && event.target.id === "edit-form") {
          interceptEditSubmit(event);
        }
      },
      true
    );

    document.addEventListener(
      "click",
      function (event) {
        if (event.target.closest("#addColSubmit")) {
          interceptAddColumnSubmit(event);
          return;
        }
        if (event.target.closest(".col-delete-btn")) {
          interceptDeleteColumnClick(event);
          return;
        }
        if (
          document.body.classList.contains("delete-mode") &&
          event.target.closest(".activity-block")
        ) {
          interceptDeleteBlockClick(event);
        }
      },
      true
    );
  }

  function attachOpenEditDialogHook() {
    if (
      typeof window.openEditDialog !== "function" ||
      window.openEditDialog.__individualHooked
    ) {
      return;
    }

    var original = window.openEditDialog;
    var wrapped = function (block) {
      var result = original.apply(this, arguments);
      bindEditFormToBlock(block);
      return result;
    };

    wrapped.__individualHooked = true;
    window.openEditDialog = wrapped;
  }

  function attachManagedDragHandlers() {
    if (document.body.__individualManagedDragAttached) {
      return;
    }
    document.body.__individualManagedDragAttached = true;
    document.addEventListener("mousedown", handleManagedResizeStart, true);
    document.addEventListener("mousemove", handleManagedDragMove, true);
    document.addEventListener("mouseup", handleManagedDragEnd, true);
    document.addEventListener("mouseup", handleManagedResizeEnd);
  }

  function handleIndividualRevision(revision) {
    if (!revision || revision === individualRevision) {
      return;
    }
    if (!isInEditMode()) {
      refreshIndividualLayer();
      return;
    }
    individualRevision = revision;
    showNotice(
      "Индивидуальные занятия обновлены на сервере. Завершите редактирование для синхронизации.",
      "warning",
      6000
    );
  }

  function refreshIndividualLayer(preloaded) {
    if (preloaded) {
      applyIndividualState(preloaded);
      return Promise.resolve(preloaded);
    }

    return requestJson("/api/schedule").then(function (result) {
      if (!result || !result.ok) {
        return null;
      }
      applyIndividualState(result.data);
      return result.data;
    });
  }

  function applyIndividualState(data) {
    var blocks = [];
    if (
      baseSyncUi() &&
      typeof baseSyncUi().applyBaseScheduleData === "function" &&
      data &&
      ("base_revision" in data || "published_base_available" in data)
    ) {
      baseSyncUi().applyBaseScheduleData(data);
    }
    if (Array.isArray(data && data.individual)) {
      blocks = data.individual;
      individualRevision = data.individual_revision || null;
    } else if (Array.isArray(data && data.blocks)) {
      blocks = data.blocks;
      individualRevision = data.last_modified || data.individual_revision || null;
    }

    removeIndividualBlocks();
    blocks.forEach(function (block) {
      renderIndividualBlock(block, true);
    });

    if (typeof updateActivityPositions === "function") {
      updateActivityPositions();
    }
    if (typeof reapplyLessonTypeFilter === "function") {
      reapplyLessonTypeFilter();
    }
  }

  function removeIndividualBlocks() {
    document
      .querySelectorAll(
        '.activity-block[data-block-id], .activity-block[data-lesson-type="individual"], .activity-block[data-lesson-type="nachhilfe"]'
      )
      .forEach(function (block) {
        if (activeEditedBlock === block) {
          activeEditedBlock = null;
        }
        if (block.parentNode) {
          block.parentNode.removeChild(block);
        }
      });
  }

  function renderIndividualBlock(block, deferLayout) {
    var building = (block.building || "").trim();
    var day = (block.day || "").trim();
    var room = (block.room || "").trim();
    var container = findScheduleContainer(building);
    var colIndex;
    var rows;
    var timeText;
    var element;

    if (!container || !building || !day || !room) {
      return null;
    }

    removeBlockById(block.id);
    colIndex = resolveColumnIndex(building, day, room);
    if (colIndex < 0) {
      return null;
    }

    rows = resolveRows(block);
    timeText = (block.start_time || "") + "-" + (block.end_time || "");

    element = document.createElement("div");
    element.className =
      "activity-block activity-day-" +
      day +
      " lesson-type-" +
      (block.lesson_type || "individual");
    element.setAttribute("data-block-id", block.id || "");
    element.setAttribute("data-day", day);
    element.setAttribute("data-col-index", String(colIndex));
    element.setAttribute("data-building", building);
    element.setAttribute("data-lesson-type", block.lesson_type || "individual");
    element.setAttribute("data-room", room);
    element.setAttribute("data-start-time", block.start_time || "");
    element.setAttribute("data-end-time", block.end_time || "");
    element.setAttribute("data-start-row", String(rows.start_row));
    element.setAttribute("data-row-span", String(rows.row_span));
    element.style.backgroundColor = block.color || defaultColor(block.lesson_type);
    element.style.width = "100px";

    if (typeof getContrastTextColor === "function") {
      element.style.color = getContrastTextColor(element.style.backgroundColor);
    }

    element.innerHTML = [
      "<strong>" + escapeHtml(block.subject || "") + "</strong>",
      escapeHtml(block.teacher || ""),
      escapeHtml(block.students || ""),
      escapeHtml(room),
      escapeHtml(timeText),
    ].join("<br>");

    container.appendChild(element);
    attachIndividualBlockInteractions(element);

    if (!deferLayout && typeof updateActivityPositions === "function") {
      updateActivityPositions();
    }
    return element;
  }

  function attachIndividualBlockInteractions(block) {
    if (!block || block.__individualInteractionsAttached) {
      return;
    }
    block.__individualInteractionsAttached = true;

    block.addEventListener("mousedown", function (event) {
      handleIndividualBlockMouseDown(block, event);
    });
    block.addEventListener("dblclick", function (event) {
      handleIndividualBlockDoubleClick(block, event);
    });
  }

  function handleIndividualBlockMouseDown(block, event) {
    var clientX;
    var clientY;
    var rect;

    if (!block || event.button !== 0) {
      return;
    }
    if (!block.getAttribute("data-block-id")) {
      return;
    }
    if (window.editDialogOpen || document.body.classList.contains("delete-mode")) {
      return;
    }
    if (!isInEditMode()) {
      return;
    }

    rect = block.getBoundingClientRect();
    if (event.clientY >= rect.bottom - 8) {
      return;
    }

    clientX = event.clientX;
    clientY = event.clientY;
    clearPendingDragStart();
    pendingDragStart = {
      block: block,
      clientX: clientX,
      clientY: clientY,
      timer: window.setTimeout(function () {
        beginManagedDrag(block, clientX, clientY);
      }, 200),
    };
    event.preventDefault();
  }

  function handleIndividualBlockDoubleClick(block, event) {
    if (!block || document.body.classList.contains("delete-mode")) {
      return;
    }
    clearPendingDragStart();
    cancelManagedDrag(block);
    event.preventDefault();
    event.stopPropagation();
    openManagedEditDialog(block);
  }

  function clearPendingDragStart() {
    if (pendingDragStart && pendingDragStart.timer) {
      clearTimeout(pendingDragStart.timer);
    }
    pendingDragStart = null;
  }

  function handleManagedResizeStart(event) {
    var block =
      event.target && event.target.closest
        ? event.target.closest(".activity-block[data-block-id]")
        : null;

    if (
      !block ||
      event.button !== 0 ||
      !isInEditMode() ||
      window.editDialogOpen ||
      document.body.classList.contains("delete-mode")
    ) {
      pendingResize = null;
      return;
    }
    if (!isInManagedResizeZone(block, event.clientY)) {
      pendingResize = null;
      return;
    }

    pendingResize = {
      blockId: block.getAttribute("data-block-id") || "",
      snapshot: captureBlockSnapshot(block),
    };
  }

  function handleManagedResizeEnd() {
    var resize = pendingResize;
    var block;

    if (!resize || !resize.blockId) {
      pendingResize = null;
      return;
    }
    pendingResize = null;
    block = document.querySelector(
      '.activity-block[data-block-id="' + cssEscape(resize.blockId) + '"]'
    );
    if (!block) {
      return;
    }

    persistChangedBlock(
      block,
      resize.snapshot,
      "Не удалось сохранить новую длительность занятия из-за ошибки сети."
    );
  }

  function isInManagedResizeZone(block, clientY) {
    var rect = block.getBoundingClientRect();
    return clientY >= rect.bottom - 6 && clientY <= rect.bottom + 2;
  }

  function beginManagedDrag(block, clientX, clientY) {
    var rect;

    if (!block || !block.parentElement || !isInEditMode()) {
      clearPendingDragStart();
      return;
    }

    rect = block.getBoundingClientRect();
    activeDrag = {
      block: block,
      container: block.parentElement,
      offsetX: clientX - rect.left,
      offsetY: clientY - rect.top,
      initialLeft: parseFloat(block.style.left) || 0,
      initialTop: parseFloat(block.style.top) || 0,
      moved: false,
      snapshot: captureBlockSnapshot(block),
    };
    clearPendingDragStart();
    block.style.opacity = "0.7";
  }

  function handleManagedDragMove(event) {
    var drag = activeDrag;
    var containerRect;
    var newLeft;
    var newTop;
    var snapped;

    if (!drag || !drag.block || !drag.container || window.editDialogOpen) {
      return;
    }

    containerRect = drag.container.getBoundingClientRect();
    newLeft = event.clientX - containerRect.left - drag.offsetX + drag.container.scrollLeft;
    newTop = event.clientY - containerRect.top - drag.offsetY + drag.container.scrollTop;

    if (typeof GridSnapService !== "undefined" && GridSnapService) {
      snapped = GridSnapService.snapToGrid(newLeft, newTop, drag.block);
      newLeft = snapped.left;
      newTop = snapped.top;
    }

    drag.moved =
      drag.moved ||
      Math.abs(newLeft - drag.initialLeft) > 1 ||
      Math.abs(newTop - drag.initialTop) > 1;
    drag.block.style.left = newLeft + "px";
    drag.block.style.top = newTop + "px";
    event.preventDefault();
  }

  function handleManagedDragEnd(event) {
    var drag = activeDrag;

    if (!drag) {
      clearPendingDragStart();
      return;
    }

    activeDrag = null;
    drag.block.style.opacity = "1";
    if (!drag.moved) {
      return;
    }

    if (typeof BlockDropService !== "undefined" && BlockDropService) {
      BlockDropService.processBlockDrop(drag.block);
    } else if (typeof processBlockDrop === "function") {
      processBlockDrop(drag.block);
    }

    persistDraggedBlock(drag);
    event.preventDefault();
  }

  function cancelManagedDrag(block) {
    if (!activeDrag) {
      return;
    }
    if (block && activeDrag.block !== block) {
      return;
    }
    if (activeDrag.block) {
      activeDrag.block.style.opacity = "1";
    }
    activeDrag = null;
  }

  function openManagedEditDialog(block) {
    if (!block || typeof window.openEditDialog !== "function") {
      return;
    }
    activeEditedBlock = block;
    window.openEditDialog(
      block,
      block.style.left || "",
      block.style.top || "",
      block.getAttribute("data-building") || ""
    );
    bindEditFormToBlock(block);
  }

  function bindEditFormToBlock(block) {
    var form = document.getElementById("edit-form");
    var blockId;

    if (!form || !block) {
      return;
    }

    blockId = block.getAttribute("data-block-id") || "";
    form.__editedBlock = block;
    if (blockId) {
      form.setAttribute("data-block-id", blockId);
    } else {
      form.removeAttribute("data-block-id");
    }
    activeEditedBlock = block;
  }

  function resolveEditedBlock(form) {
    var blockId;

    if (form && form.__editedBlock) {
      return form.__editedBlock;
    }
    blockId = form ? form.getAttribute("data-block-id") : "";
    if (blockId) {
      return document.querySelector(
        '.activity-block[data-block-id="' + cssEscape(blockId) + '"]'
      );
    }
    return activeEditedBlock;
  }

  function captureBlockSnapshot(block) {
    return {
      className: block.className,
      innerHTML: block.innerHTML,
      left: block.style.left,
      top: block.style.top,
      backgroundColor: block.style.backgroundColor,
      color: block.style.color,
      attrs: {
        "data-block-id": block.getAttribute("data-block-id"),
        "data-building": block.getAttribute("data-building"),
        "data-day": block.getAttribute("data-day"),
        "data-col-index": block.getAttribute("data-col-index"),
        "data-lesson-type": block.getAttribute("data-lesson-type"),
        "data-room": block.getAttribute("data-room"),
        "data-start-row": block.getAttribute("data-start-row"),
        "data-row-span": block.getAttribute("data-row-span"),
        "data-start-time": block.getAttribute("data-start-time"),
        "data-end-time": block.getAttribute("data-end-time"),
      },
      payload: buildBlockPayloadFromElement(block),
    };
  }

  function restoreBlockSnapshot(block, snapshot) {
    if (!block || !snapshot) {
      return;
    }

    block.className = snapshot.className || block.className;
    block.innerHTML = snapshot.innerHTML || "";
    block.style.left = snapshot.left || "";
    block.style.top = snapshot.top || "";
    block.style.backgroundColor = snapshot.backgroundColor || "";
    block.style.color = snapshot.color || "";

    Object.keys(snapshot.attrs || {}).forEach(function (name) {
      setOrRemoveAttribute(block, name, snapshot.attrs[name]);
    });

    if (typeof updateActivityPositions === "function") {
      updateActivityPositions();
    }
    if (typeof reapplyLessonTypeFilter === "function") {
      reapplyLessonTypeFilter();
    }
    if (typeof ConflictDetector !== "undefined") {
      ConflictDetector.highlightConflicts();
    }
  }

  function buildBlockPayloadFromElement(block) {
    var parts = (block.innerHTML || "").split(/<br\s*\/?>/i);
    var timeText = stripHtml(parts[4] || "").trim();
    var timeInfo = parseTimeRange(timeText);
    var lessonType = getBlockLessonType(block);
    var colIndex = toInteger(block.getAttribute("data-col-index"), -1);
    var startRow = toInteger(
      block.getAttribute("data-start-row"),
      timeInfo ? timeInfo.start_row : -1
    );
    var rowSpan = toInteger(
      block.getAttribute("data-row-span"),
      timeInfo ? timeInfo.row_span : -1
    );

    if (
      !block ||
      !timeInfo ||
      !block.getAttribute("data-building") ||
      !block.getAttribute("data-day") ||
      !stripHtml(parts[3] || "").trim() ||
      !getBlockSubject(block)
    ) {
      return null;
    }

    return {
      building: (block.getAttribute("data-building") || "").trim(),
      day: (block.getAttribute("data-day") || "").trim(),
      room: stripHtml(parts[3] || "").trim(),
      subject: getBlockSubject(block).trim(),
      teacher: stripHtml(parts[1] || "").trim(),
      students: stripHtml(parts[2] || "").trim(),
      lesson_type: lessonType,
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: startRow >= 0 ? startRow : timeInfo.start_row,
      row_span: rowSpan >= 1 ? rowSpan : timeInfo.row_span,
      color: block.style.backgroundColor || defaultColor(lessonType),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
  }

  function persistDraggedBlock(drag) {
    persistChangedBlock(
      drag && drag.block,
      drag && drag.snapshot,
      "Не удалось сохранить новое положение занятия из-за ошибки сети."
    );
  }

  function persistChangedBlock(block, snapshot, networkErrorMessage) {
    var blockId = block ? block.getAttribute("data-block-id") : "";
    var payload = block ? buildBlockPayloadFromElement(block) : null;

    if (!block || !blockId || !payload) {
      restoreBlockSnapshot(block, snapshot);
      return;
    }
    if (
      snapshot &&
      snapshot.payload &&
      JSON.stringify(snapshot.payload) === JSON.stringify(payload)
    ) {
      return;
    }

    requestJson("/api/blocks/" + encodeURIComponent(blockId), "PUT", payload).then(
      function (result) {
        if (!result) {
          restoreBlockSnapshot(block, snapshot);
          alert(networkErrorMessage || "Не удалось сохранить изменения занятия из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          restoreBlockSnapshot(block, snapshot);
          handleMutationError(
            result,
            "Недостаточно прав для изменения этого типа занятия."
          );
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        removeBlockById(blockId);
        renderIndividualBlock(result.data.block);
        if (typeof updateActivityPositions === "function") {
          updateActivityPositions();
        }
        if (typeof ConflictDetector !== "undefined") {
          ConflictDetector.highlightConflicts();
        }
      }
    );
  }

  function setOrRemoveAttribute(node, name, value) {
    if (value === null || typeof value === "undefined" || value === "") {
      node.removeAttribute(name);
      return;
    }
    node.setAttribute(name, value);
  }

  function findScheduleContainer(building) {
    if (typeof BuildingService !== "undefined") {
      return BuildingService.findScheduleContainerForBuilding(building);
    }
    return document.querySelector(
      '.schedule-container[data-building="' + cssEscape(building) + '"]'
    );
  }

  function resolveColumnIndex(building, day, room) {
    var colIndex =
      typeof findMatchingColumnInBuilding === "function"
        ? findMatchingColumnInBuilding(day, room, building)
        : -1;
    if (colIndex >= 0) {
      return colIndex;
    }
    return createDynamicColumn(building, day, room);
  }

  function createDynamicColumn(building, day, room) {
    if (typeof addColumnIfMissing !== "function") {
      return -1;
    }
    return addColumnIfMissing(day, room, building);
  }

  function resolveRows(block) {
    var startRow = toInteger(block.start_row, -1);
    var rowSpan = toInteger(block.row_span, -1);
    var minutes;

    if (startRow >= 0 && rowSpan >= 1) {
      return { start_row: startRow, row_span: rowSpan };
    }

    minutes = parseTimeRange((block.start_time || "") + "-" + (block.end_time || ""));
    return {
      start_row: minutes ? minutes.start_row : 0,
      row_span: minutes ? minutes.row_span : 1,
    };
  }

  function parseTimeRange(value) {
    var match = (value || "").trim().match(/^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/);
    var startMinutes;
    var endMinutes;
    var gridStartValue;
    var interval;

    if (!match) {
      return null;
    }

    startMinutes = parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
    endMinutes = parseInt(match[3], 10) * 60 + parseInt(match[4], 10);
    if (startMinutes >= endMinutes) {
      return null;
    }

    gridStartValue = typeof gridStart !== "undefined" ? gridStart : 9 * 60;
    interval = typeof timeInterval !== "undefined" ? timeInterval : 5;

    return {
      start_time: match[1] + ":" + match[2],
      end_time: match[3] + ":" + match[4],
      start_row: Math.floor((startMinutes - gridStartValue) / interval),
      row_span: Math.floor((endMinutes - startMinutes) / interval),
    };
  }

  function interceptCreateSubmit(event) {
    var form = event.target;
    var validationError = getCreateValidationError(form);
    var payload = buildCreatePayload(form);
    var role = currentRole();

    if (validationError || !payload) {
      stopDomMutation(event);
      alert(validationError || "Пожалуйста, проверьте данные занятия.");
      return;
    }

    if (payload.lesson_type === "group") {
      if (role === "editor") {
        stopDomMutation(event);
        alert("Недостаточно прав для создания этого типа занятия.");
      }
      return;
    }

    stopDomMutation(event);
    if (!isInEditMode()) {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }

    requestJson("/api/blocks", "POST", payload).then(function (result) {
      if (!result) {
        alert("Не удалось создать занятие из-за ошибки сети.");
        return;
      }
      if (!result.ok) {
        handleMutationError(result, "Недостаточно прав для создания этого типа занятия.");
        return;
      }
      individualRevision = result.data.individual_revision || individualRevision;
      closeOverlay(form);
      renderIndividualBlock(result.data.block);
      if (typeof updateActivityPositions === "function") {
        updateActivityPositions();
      }
      if (typeof ConflictDetector !== "undefined") {
        ConflictDetector.highlightConflicts();
      }
    });
  }

  function interceptEditSubmit(event) {
    var form = event.target;
    var block = resolveEditedBlock(form);
    var validationError = getEditValidationError(form);
    var payload;
    var blockId;
    var currentLessonType;

    if (!block) {
      return;
    }

    payload = buildEditPayload(form, block);
    if (validationError || !payload) {
      stopDomMutation(event);
      alert(validationError || "Пожалуйста, проверьте данные занятия.");
      return;
    }

    blockId = (form.getAttribute("data-block-id") || block.getAttribute("data-block-id") || "").trim();
    currentLessonType = getBlockLessonType(block);

    if (payload.lesson_type === "group" && currentRole() === "editor") {
      stopDomMutation(event);
      alert("Недостаточно прав для изменения этого типа занятия.");
      return;
    }

    if (!blockId && currentLessonType === "group" && payload.lesson_type === "group") {
      return;
    }

    if (!blockId) {
      return;
    }

    stopDomMutation(event);
    if (!isInEditMode()) {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }

    requestJson("/api/blocks/" + encodeURIComponent(blockId), "PUT", payload).then(
      function (result) {
        if (!result) {
          alert("Не удалось обновить занятие из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          handleMutationError(result, "Недостаточно прав для изменения этого типа занятия.");
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        activeEditedBlock = null;
        closeOverlay(form);
        removeBlockById(blockId);
        renderIndividualBlock(result.data.block);
        if (typeof updateActivityPositions === "function") {
          updateActivityPositions();
        }
        if (typeof ConflictDetector !== "undefined") {
          ConflictDetector.highlightConflicts();
        }
      }
    );
  }

  function interceptDeleteBlockClick(event) {
    var block = event.target.closest(".activity-block");
    var blockId;
    var lessonType;
    var info;

    if (!block) {
      return;
    }

    blockId = block.getAttribute("data-block-id");
    lessonType = getBlockLessonType(block);

    if (!blockId && lessonType === "group") {
      if (currentRole() === "editor") {
        stopDomMutation(event);
        alert("Недостаточно прав для удаления групповых занятий.");
      }
      return;
    }

    if (!blockId) {
      return;
    }

    stopDomMutation(event);
    if (!isInEditMode()) {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }

    info = describeBlock(block);
    if (
      !confirm(
        "Вы действительно хотите удалить занятие?\n\n" +
          "Здание: " +
          info.building +
          "\nДень: " +
          info.day +
          "\nПредмет: " +
          info.subject +
          "\nПреподаватель: " +
          info.teacher +
          "\nВремя: " +
          info.time
      )
    ) {
      return;
    }

    requestJson("/api/blocks/" + encodeURIComponent(blockId), "DELETE").then(
      function (result) {
        if (!result) {
          alert("Не удалось удалить занятие из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          handleMutationError(result, "Недостаточно прав для удаления этого типа занятия.");
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        if (block.parentNode) {
          block.parentNode.removeChild(block);
        }
        showNotice("Занятие удалено: " + info.subject + " (" + info.time + ")", "success");
      }
    );
  }

  function interceptAddColumnSubmit(event) {
    var overlay = document.getElementById("addColumnOverlay");
    var building;
    var day;
    var room;
    var container;
    var prevCount;
    var colIndex;
    var newCount;

    if (!overlay || !event.target.closest("#addColSubmit")) {
      return;
    }

    stopDomMutation(event);
    if (!isInEditMode()) {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }

    building = getFieldValue(overlay, "#addColBuilding");
    day = getFieldValue(overlay, "#addColDay");
    room = getFieldValue(overlay, "#addColRoom").trim();

    if (!room) {
      alert("Пожалуйста, введите название кабинета");
      focusField(overlay, "#addColRoom");
      return;
    }
    if (/[<>&"']/.test(room)) {
      alert("Название кабинета содержит недопустимые символы: < > & \" '");
      focusField(overlay, "#addColRoom");
      return;
    }

    requestJson("/api/columns", "POST", { building: building, day: day, room: room }).then(
      function (result) {
        if (!result) {
          alert("Не удалось добавить колонку из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          handleMutationError(result, "Недостаточно прав для добавления колонки.");
          return;
        }

        container = findScheduleContainer(building);
        prevCount = container
          ? container.querySelectorAll(".schedule-grid thead th.day-" + day).length
          : -1;
        colIndex = typeof addColumnIfMissing === "function" ? addColumnIfMissing(day, room, building) : -1;
        newCount = container
          ? container.querySelectorAll(".schedule-grid thead th.day-" + day).length
          : -1;

        if (colIndex === -1) {
          alert("Не удалось создать или найти колонку для кабинета " + room);
          return;
        }

        closeOverlay(overlay);
        if (typeof updateActivityPositions === "function") {
          updateActivityPositions();
        }
        showNotice(
          newCount > prevCount
            ? "Добавлена колонка " + day + " " + room
            : "Колонка " + day + " " + room + " уже существует",
          "success"
        );
      }
    );
  }

  function interceptDeleteColumnClick(event) {
    var button = event.target.closest(".col-delete-btn");
    var th;
    var container;
    var building;
    var day;
    var dayHeaders;
    var colIndex;
    var room;

    if (!button) {
      return;
    }

    stopDomMutation(event);
    if (!isInEditMode()) {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }

    th = button.closest("th");
    container = th ? th.closest(".schedule-container") : null;
    if (!th || !container) {
      return;
    }

    building = container.getAttribute("data-building") || "";
    day = resolveHeaderDay(th);
    if (!day) {
      return;
    }

    dayHeaders = Array.from(
      container.querySelectorAll(".schedule-grid thead th.day-" + day)
    );
    colIndex = dayHeaders.indexOf(th);
    room =
      typeof extractRoomFromDayHeader === "function"
        ? extractRoomFromDayHeader(th, day)
        : th.textContent.replace(day, "").trim();

    if (colIndex < 0) {
      return;
    }

    if (currentRole() === "editor" && columnHasGroupBlocks(container, building, day, colIndex)) {
      alert(
        "Нельзя удалить кабинет " +
          room +
          ": он содержит групповые занятия. Обратитесь к Алле."
      );
      return;
    }

    if (
      !confirm(
        "Удалить колонку " +
          day +
          " " +
          room +
          "? Все блоки в этой колонке будут удалены."
      )
    ) {
      return;
    }

    requestJson("/api/columns", "DELETE", {
      building: building,
      day: day,
      room: room,
    }).then(function (result) {
      if (!result) {
        alert("Не удалось удалить колонку из-за ошибки сети.");
        return;
      }
      if (!result.ok) {
        handleMutationError(result, "Недостаточно прав для удаления колонки.");
        return;
      }
      individualRevision = result.data.individual_revision || individualRevision;
      if (typeof removeColumn === "function") {
        removeColumn(building, day, colIndex);
      }
      showNotice("Колонка " + day + " " + room + " удалена", "success");
    });
  }

  function buildCreatePayload(form) {
    var building = getFieldValue(form, "#new-building");
    var day = getFieldValue(form, "#new-day");
    var room = getFieldValue(form, "#new-room").trim();
    var subject = getFieldValue(form, "#new-subject");
    var teacher = getFieldValue(form, "#new-teacher");
    var students = getFieldValue(form, "#new-students");
    var timeRange = getFieldValue(form, "#new-time").trim();
    var color = getFieldValue(form, "#color-value").trim();
    var timeInfo = parseTimeRange(timeRange);
    var colIndex =
      typeof findMatchingColumnInBuilding === "function"
        ? findMatchingColumnInBuilding(day, room, building)
        : -1;

    if (!building || !day || !room || !subject || !timeInfo) {
      return null;
    }

    return {
      building: building,
      day: day,
      room: room,
      subject: subject,
      teacher: teacher,
      students: students,
      lesson_type: inferLessonType(subject),
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: timeInfo.start_row,
      row_span: timeInfo.row_span,
      color: color || defaultColor(inferLessonType(subject)),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
  }

  function buildEditPayload(form, block) {
    var building = getFieldValue(form, "#edit-building");
    var subject = getFieldValue(form, "#edit-subject");
    var teacher = getFieldValue(form, "#edit-teacher");
    var students = getFieldValue(form, "#edit-students");
    var room = getFieldValue(form, "#edit-room").trim();
    var timeRange = getFieldValue(form, "#edit-time").trim();
    var timeInfo = parseTimeRange(timeRange);
    var day = block.getAttribute("data-day") || "";
    var colIndex =
      typeof findMatchingColumnInBuilding === "function"
        ? findMatchingColumnInBuilding(day, room, building)
        : -1;

    if (!building || !day || !room || !subject || !timeInfo) {
      return null;
    }

    return {
      building: building,
      day: day,
      room: room,
      subject: subject,
      teacher: teacher,
      students: students,
      lesson_type: inferLessonType(subject),
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: timeInfo.start_row,
      row_span: timeInfo.row_span,
      color: block.style.backgroundColor || defaultColor(inferLessonType(subject)),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
  }

  function getCreateValidationError(form) {
    return validateBlockInputs(
      getFieldValue(form, "#new-building"),
      getFieldValue(form, "#new-day"),
      getFieldValue(form, "#new-room").trim(),
      getFieldValue(form, "#new-subject"),
      getFieldValue(form, "#new-time").trim()
    );
  }

  function getEditValidationError(form) {
    return validateBlockInputs(
      getFieldValue(form, "#edit-building"),
      "x",
      getFieldValue(form, "#edit-room").trim(),
      getFieldValue(form, "#edit-subject"),
      getFieldValue(form, "#edit-time").trim()
    );
  }

  function validateBlockInputs(building, day, room, subject, timeRange) {
    var timeInfo = parseTimeRange(timeRange);

    if (!building || !day || !room || !subject) {
      return "Пожалуйста, заполните обязательные поля занятия.";
    }
    if (/[<>&"']/.test(room)) {
      return "Название кабинета содержит недопустимые символы: < > & \" '.";
    }
    if (!timeInfo) {
      return "Пожалуйста, введите время в формате ЧЧ:ММ-ЧЧ:ММ.";
    }
    if (timeInfo.start_row < 0 || timeInfo.row_span < 1) {
      return "Время занятия выходит за пределы сетки расписания.";
    }
    return null;
  }

  function handleMutationError(result, forbiddenMessage) {
    var code = result.data && result.data.code;
    var error = (result.data && result.data.error) || "Ошибка сервера";

    if (result.status === 403 && code === "NO_LOCK") {
      alert(
        "Для редактирования необходимо захватить блокировку. Нажмите «Начать редактирование»."
      );
      return;
    }
    if (result.status === 403 && code === "FORBIDDEN") {
      alert(forbiddenMessage);
      return;
    }
    if (result.status === 403 && code === "COLUMN_HAS_GROUP_LESSONS") {
      alert("Нельзя удалить кабинет: в опубликованном расписании есть групповые занятия.");
      return;
    }
    if (result.status === 404 && code === "NOT_FOUND") {
      alert("Блок не найден на сервере.");
      return;
    }
    alert(error);
  }

  function stopDomMutation(event) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
  }

  function getFieldValue(root, selector) {
    var field = root.querySelector(selector);
    return field ? field.value || "" : "";
  }

  function focusField(root, selector) {
    var field = root.querySelector(selector);
    if (field) {
      field.focus();
    }
  }

  function closeOverlay(source) {
    var root = source && source.closest ? source.closest(".dialog-overlay, .menu-modal-overlay") : null;
    var cancelButton;
    var editForm;

    if (!root && source && source.id === "addColumnOverlay") {
      root = source;
    }

    if (!root) {
      return;
    }

    editForm = root.querySelector("#edit-form");
    cancelButton = root.querySelector("#cancel-create, #cancel-edit, #addColCancel");
    if (cancelButton) {
      if (editForm) {
        activeEditedBlock = null;
      }
      cancelButton.click();
      return;
    }

    if (root.parentNode) {
      root.parentNode.removeChild(root);
    }
    document.body.style.overflow = "";
    window.editDialogOpen = false;
    if (editForm) {
      activeEditedBlock = null;
    }
  }

  function removeBlockById(blockId) {
    if (!blockId) {
      return;
    }
    document
      .querySelectorAll('.activity-block[data-block-id="' + cssEscape(blockId) + '"]')
      .forEach(function (block) {
        if (activeEditedBlock === block) {
          activeEditedBlock = null;
        }
        if (block.parentNode) {
          block.parentNode.removeChild(block);
        }
      });
  }

  function describeBlock(block) {
    var parts = (block.innerHTML || "").split(/<br\s*\/?>/i);
    var subject = block.querySelector("strong");

    return {
      building: block.getAttribute("data-building") || "",
      day: block.getAttribute("data-day") || "",
      subject: subject ? subject.textContent.trim() : "",
      teacher: stripHtml(parts[1] || ""),
      time: stripHtml(parts[4] || ""),
    };
  }

  function getBlockLessonType(block) {
    return block.getAttribute("data-lesson-type") || inferLessonType(getBlockSubject(block));
  }

  function getBlockSubject(block) {
    var strong = block.querySelector("strong");
    if (strong) {
      return strong.textContent || "";
    }
    return stripHtml(((block.innerHTML || "").split(/<br\s*\/?>/i)[0] || ""));
  }

  function columnHasGroupBlocks(container, building, day, colIndex) {
    return Array.from(
      container.querySelectorAll(
        '.activity-block[data-building="' +
          cssEscape(building) +
          '"][data-day="' +
          cssEscape(day) +
          '"]'
      )
    ).some(function (block) {
      return (
        toInteger(block.getAttribute("data-col-index"), -1) === colIndex &&
        getBlockLessonType(block) === "group"
      );
    });
  }

  function resolveHeaderDay(th) {
    var dayClass = Array.from(th.classList).find(function (cls) {
      return cls.indexOf("day-") === 0;
    });
    return dayClass ? dayClass.replace("day-", "") : "";
  }

  function inferLessonType(subject) {
    if (typeof classifyLessonType === "function") {
      return classifyLessonType(subject || "");
    }
    if ((subject || "").indexOf("Nachhilfe") !== -1) {
      return "nachhilfe";
    }
    if ((subject || "").indexOf("Ind.") !== -1) {
      return "individual";
    }
    return "group";
  }

  function defaultColor(lessonType) {
    return lessonType === "nachhilfe" ? "#D8F0FF" : "#FFF1BF";
  }

  function showNotice(message, type, duration) {
    var note = document.getElementById("schedgen-individual-notice");

    if (syncNoticeTimer) {
      clearTimeout(syncNoticeTimer);
      syncNoticeTimer = null;
    }

    if (!note) {
      note = document.createElement("div");
      note.id = "schedgen-individual-notice";
      note.style.cssText = [
        "position:fixed",
        "right:20px",
        "bottom:20px",
        "z-index:10020",
        "max-width:420px",
        "padding:12px 16px",
        "border-radius:8px",
        "color:#fff",
        "font:13px/1.4 sans-serif",
        "box-shadow:0 8px 20px rgba(0,0,0,.2)",
      ].join(";");
      document.body.appendChild(note);
    }

    note.textContent = message;
    note.style.backgroundColor =
      type === "warning" ? "#c57f00" : type === "success" ? "#2e7d32" : "#546e7a";
    note.style.display = "block";

    syncNoticeTimer = setTimeout(function () {
      note.style.display = "none";
    }, duration || 3000);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function stripHtml(value) {
    return String(value || "").replace(/<[^>]+>/g, "").trim();
  }

  function toInteger(value, fallback) {
    var parsed = parseInt(value, 10);
    return isNaN(parsed) ? fallback : parsed;
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(String(value || ""));
    }
    return String(value || "").replace(/["\\]/g, "\\$&");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
