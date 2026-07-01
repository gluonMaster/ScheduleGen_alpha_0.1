(function () {
  "use strict";

  var individualRevision = null;
  var pendingIndividualRevision = null;
  var pendingRevisionNotice = null;
  var syncNoticeTimer = null;
  var activeEditedBlock = null;
  var pendingDragStart = null;
  var activeDrag = null;
  var pendingResize = null;
  var hoveredManagedBlock = null;
  var managedLegacyDragReleaseTimer = null;
  var compactRowsManagedDragPaused = false;
  var compactRowsManagedResizePaused = false;
  var eventMutationInFlight = 0;
  var eventManagersRequest = null;
  var eventManagers = null;
  var EVENT_SUBJECT = "Veranstaltung";
  var EVENT_LESSON_TYPE = "veranstaltung";
  var EVENT_DEFAULT_COLOR = "#7c3aed";
  var EVENT_ROOM_SCOPE = {
    Villa: ["0.04", "0.06", "0.08", "2.04"],
    Kolibri: ["0.3", "0.2"],
  };
  if (window.EVENT_ROOM_SCOPE && typeof window.EVENT_ROOM_SCOPE === "object") {
    EVENT_ROOM_SCOPE = window.EVENT_ROOM_SCOPE;
  }

  function authUi() {
    return window.SchedGenAuthUI || null;
  }

  function baseSyncUi() {
    return window.SchedGenBaseSyncUI || null;
  }

  function scheduleSearch() {
    return window.ScheduleSearch || null;
  }

  function notifySearchScheduleMutation() {
    var search = scheduleSearch();

    if (!search || typeof search.handleScheduleMutation !== "function") {
      return;
    }
    search.handleScheduleMutation();
  }

  function refreshCompactRowsAfterIndividualMutation() {
    if (
      window.ScheduleCompactRows &&
      typeof window.ScheduleCompactRows.refresh === "function"
    ) {
      window.ScheduleCompactRows.refresh();
    } else if (typeof window.updateActivityPositions === "function") {
      window.updateActivityPositions();
    }
  }

  function pauseCompactRowsForManagedDrag() {
    if (
      !compactRowsManagedDragPaused &&
      window.ScheduleCompactRows &&
      typeof window.ScheduleCompactRows.pauseForInteraction === "function"
    ) {
      window.ScheduleCompactRows.pauseForInteraction("drag");
      compactRowsManagedDragPaused = true;
    }
  }

  function resumeCompactRowsAfterManagedDrag(refresh) {
    if (
      compactRowsManagedDragPaused &&
      window.ScheduleCompactRows &&
      typeof window.ScheduleCompactRows.resumeAfterInteraction === "function"
    ) {
      window.ScheduleCompactRows.resumeAfterInteraction("drag", { refresh: !!refresh });
    }
    compactRowsManagedDragPaused = false;
  }

  function pauseCompactRowsForManagedResize() {
    if (
      !compactRowsManagedResizePaused &&
      window.ScheduleCompactRows &&
      typeof window.ScheduleCompactRows.pauseForInteraction === "function"
    ) {
      window.ScheduleCompactRows.pauseForInteraction("resize");
      compactRowsManagedResizePaused = true;
    }
  }

  function resumeCompactRowsAfterManagedResize(refresh) {
    if (
      compactRowsManagedResizePaused &&
      window.ScheduleCompactRows &&
      typeof window.ScheduleCompactRows.resumeAfterInteraction === "function"
    ) {
      window.ScheduleCompactRows.resumeAfterInteraction("resize", { refresh: !!refresh });
    }
    compactRowsManagedResizePaused = false;
  }

  function reapplyLessonTypeFilterAfterIndividualMutation() {
    if (typeof reapplyLessonTypeFilter === "function") {
      reapplyLessonTypeFilter();
      return;
    }
    refreshCompactRowsAfterIndividualMutation();
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

  function canUseEventEditor() {
    return !!(
      authUi() &&
      typeof authUi().canUseEventEditor === "function" &&
      authUi().canUseEventEditor(currentRole())
    );
  }

  function isEventBlock(block) {
    return getBlockLessonType(block) === EVENT_LESSON_TYPE;
  }

  function canRoleMutateBlock(role, block) {
    var lessonType = getBlockLessonType(block);

    if (authUi() && typeof authUi().canMutateBlock === "function") {
      return authUi().canMutateBlock(role, block);
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      if (role === "admin") {
        return true;
      }
      return (
        role === "event_manager" &&
        block &&
        (block.getAttribute("data-owner-kind") || "event_manager") === "event_manager" &&
        (block.getAttribute("data-created-by") || "") === (window.CURRENT_USER || "")
      );
    }
    if (role === "admin") {
      return true;
    }
    if (role === "editor") {
      return lessonType !== "group";
    }
    if (role === "organizer") {
      return lessonType === "trial";
    }
    return false;
  }

  function canCurrentRoleMutateBlock(block) {
    return canRoleMutateBlock(currentRole(), block);
  }

  function getMutationDeniedMessage(action, block) {
    var role = currentRole();
    var lessonType = getBlockLessonType(block);

    if (role === "organizer") {
      return action === "delete"
        ? "Организатор может удалять только пробные/разовые занятия."
        : "Организатор может редактировать только пробные/разовые занятия.";
    }
    if (role === "editor" && lessonType === "group") {
      return action === "delete"
        ? "Недостаточно прав для удаления групповых занятий."
        : "Недостаточно прав для изменения этого типа занятия.";
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      return "Veranstaltung доступна для изменения только администратору или владельцу event-manager.";
    }
    return "Недостаточно прав для этого действия.";
  }

  function canInteractWithManagedBlock(block) {
    if (!block || !canCurrentRoleMutateBlock(block)) {
      return false;
    }
    if (isEventBlock(block)) {
      return canUseEventEditor();
    }
    return isInEditMode();
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

  function beginEventMutation() {
    eventMutationInFlight += 1;
  }

  function endEventMutation() {
    eventMutationInFlight = Math.max(0, eventMutationInFlight - 1);
  }

  function responseRequiresIndividualRefresh(data) {
    return !!(
      data &&
      (data.force_individual_refresh ||
        Number(data.individual_cleanup_removed || 0) > 0)
    );
  }

  function resultRequiresIndividualRefresh(result) {
    return !!(result && responseRequiresIndividualRefresh(result.data));
  }

  function refreshIndividualLayerForCleanup(result) {
    if (!resultRequiresIndividualRefresh(result)) {
      return false;
    }
    refreshIndividualLayer();
    return true;
  }

  function isDayHidden(day, container) {
    var button;
    var header;

    if (!day) {
      return false;
    }

    button = document.querySelector(
      '.toggle-day-button.active[data-day="' + cssEscape(day) + '"]'
    );
    if (button) {
      return true;
    }

    if (!container || !container.querySelector) {
      return false;
    }

    header = container.querySelector("th.day-" + day);
    return !!(header && window.getComputedStyle(header).display === "none");
  }

  function init() {
    if (!authUi()) {
      return;
    }
    ensureEventStyles();
    ensureExplicitLessonTypeUpdater();
    attachOpenEditDialogHook();
    attachGlobalInterceptors();
    attachEditModeChangeListener();
    attachManagedDragHandlers();
    attachCreateDialogEnhancer();
    window.refreshIndividualLayer = refreshIndividualLayer;
    window.SchedGenIndividualUI = {
      getIndividualRevision: function () {
        return individualRevision;
      },
      handleIndividualRevision: handleIndividualRevision,
      flushPendingRevision: flushPendingRevision,
      refreshIndividualLayer: refreshIndividualLayer,
    };
    refreshIndividualLayer();
  }

  function ensureEventStyles() {
    var style;

    if (document.getElementById("schedgen-event-styles")) {
      return;
    }
    style = document.createElement("style");
    style.id = "schedgen-event-styles";
    style.textContent = [
      '.activity-block[data-lesson-type="veranstaltung"],',
      ".activity-block.lesson-type-veranstaltung {",
      "  border: 2px solid #6d28d9 !important;",
      "  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.26), 0 0 0 1px rgba(109,40,217,0.24);",
      "  padding-top: 18px !important;",
      "  overflow: hidden;",
      "}",
      '.activity-block[data-lesson-type="veranstaltung"]::before,',
      ".activity-block.lesson-type-veranstaltung::before {",
      "  content: 'EVENT';",
      "  position: absolute;",
      "  top: 4px;",
      "  right: 4px;",
      "  padding: 2px 6px;",
      "  border-radius: 999px;",
      "  background: #4c1d95;",
      "  color: #fff;",
      "  font-size: 10px;",
      "  font-weight: 700;",
      "  letter-spacing: 0.08em;",
      "  z-index: 2;",
      "  pointer-events: none;",
      "}",
      '.activity-block[data-lesson-type="veranstaltung"] strong,',
      ".activity-block.lesson-type-veranstaltung strong { display: block; width: 100%; margin-bottom: 2px; }",
      ".event-owner-wrapper { margin-bottom: 10px; display: flex; flex-direction: column; }",
      ".event-owner-wrapper small, .event-form-hint { margin-top: 6px; color: #51606b; font-size: 12px; line-height: 1.4; }",
    ].join("\n");
    document.head.appendChild(style);
  }

  function ensureExplicitLessonTypeUpdater() {
    var originalUpdate;

    if (window.__schedgenExplicitLessonTypeUpdaterInstalled) {
      return;
    }

    originalUpdate =
      typeof window.updateBlockLessonType === "function"
        ? window.updateBlockLessonType
        : null;

    window.updateBlockLessonType = function (block) {
      var explicitType;

      if (!block) {
        return;
      }

      explicitType = (block.getAttribute("data-lesson-type") || "").trim();
      if (
        block.getAttribute("data-block-id") &&
        explicitType &&
        explicitType !== "group"
      ) {
        syncLessonTypeClass(block, explicitType);
        return explicitType;
      }

      if (originalUpdate) {
        originalUpdate(block);
      } else {
        block.setAttribute("data-lesson-type", inferLessonType(getBlockSubject(block)));
      }

      syncLessonTypeClass(
        block,
        (block.getAttribute("data-lesson-type") || "").trim() || "group"
      );
      return block.getAttribute("data-lesson-type") || "group";
    };

    window.__schedgenExplicitLessonTypeUpdaterInstalled = true;
  }

  function syncLessonTypeClass(block, lessonType) {
    var normalizedType = (lessonType || "group").trim() || "group";

    if (!block) {
      return;
    }

    block.className = (block.className || "")
      .replace(/\slesson-type-(group|individual|nachhilfe|trial|veranstaltung)\b/g, "")
      .trim();
    block.classList.add("lesson-type-" + normalizedType);
    block.setAttribute("data-lesson-type", normalizedType);
  }

  function setLegacyDragPrevention(enabled) {
    if (
      typeof window.DragDropService !== "undefined" &&
      window.DragDropService &&
      typeof window.DragDropService.setPreventDrag === "function"
    ) {
      window.DragDropService.setPreventDrag(!!enabled);
    }
  }

  function releaseLegacyDragPrevention(delay) {
    if (managedLegacyDragReleaseTimer) {
      clearTimeout(managedLegacyDragReleaseTimer);
      managedLegacyDragReleaseTimer = null;
    }

    managedLegacyDragReleaseTimer = window.setTimeout(function () {
      setLegacyDragPrevention(false);
      managedLegacyDragReleaseTimer = null;
    }, typeof delay === "number" ? delay : 0);
  }

  function cancelLegacyResize(event) {
    if (typeof handleResizeMouseUp === "function" && window.isResizing) {
      try {
        handleResizeMouseUp(event || {});
      } catch (error) {
        console.warn("Failed to cancel legacy resize for managed block:", error);
      }
    }
  }

  function applyManagedBlockInteractivity(block, mode) {
    var canInteract;

    if (!block || !block.getAttribute("data-block-id")) {
      return;
    }

    canInteract =
      canInteractWithManagedBlock(block) &&
      !window.editDialogOpen &&
      !document.body.classList.contains("delete-mode");

    if (!canInteract) {
      block.removeAttribute("data-resize-hover");
      block.classList.remove("resizing");
      block.style.cursor = "default";
      return;
    }

    if (mode === "resize") {
      block.setAttribute("data-resize-hover", "1");
      block.style.cursor = "ns-resize";
      return;
    }

    block.removeAttribute("data-resize-hover");
    block.style.cursor = "move";
  }

  function refreshManagedBlockInteractivity(root) {
    var scope = root && root.querySelectorAll ? root : document;

    scope.querySelectorAll(".activity-block[data-block-id]").forEach(function (block) {
      applyManagedBlockInteractivity(block);
    });
  }

  function handleManagedPointerMove(event) {
    var block =
      event.target && event.target.closest
        ? event.target.closest(".activity-block[data-block-id]")
        : null;

    if (hoveredManagedBlock && hoveredManagedBlock !== block) {
      applyManagedBlockInteractivity(hoveredManagedBlock);
    }

    hoveredManagedBlock = block || null;
    if (!block) {
      return;
    }

    if (pendingResize && pendingResize.blockId === block.getAttribute("data-block-id")) {
      applyManagedBlockInteractivity(block, "resize");
      return;
    }
    if (activeDrag && activeDrag.block === block) {
      applyManagedBlockInteractivity(block, "move");
      return;
    }

    applyManagedBlockInteractivity(
      block,
      isInManagedResizeZone(block, event.clientY) ? "resize" : "move"
    );
  }

  function attachCreateDialogEnhancer() {
    if (document.body.__trialCreateEnhancerAttached) {
      return;
    }
    document.body.__trialCreateEnhancerAttached = true;

    new MutationObserver(function () {
      var form = document.getElementById("create-form");
      if (!form || form.__trialCreateEnhanced || form.__trialCreateEnhancing) {
        return;
      }
      enhanceCreateDialog(form);
    }).observe(document.body, { childList: true, subtree: true });

    enhanceCreateDialog(document.getElementById("create-form"));
  }

  function enhanceCreateDialog(form) {
    var enhancementSucceeded = false;
    var role;
    var buttonRow;
    var columnField;
    var anchor;
    var typeWrapper;
    var typeSelect = form ? form.querySelector("#new-lesson-type") : null;
    var typeHint = form ? form.querySelector("#create-lesson-type-hint") : null;
    var datesSection = form ? form.querySelector("#create-trial-dates-section, #create-event-dates-section") : null;
    var trialOption;
    var autoOption;

    if (!form || !window.TrialUI || form.__trialCreateEnhanced || form.__trialCreateEnhancing) {
      return;
    }
    form.__trialCreateEnhancing = true;
    form.setAttribute("autocomplete", "off");

    window.TrialUI.injectTrialStyles();
    role = currentRole();

    if (!typeSelect) {
      buttonRow = form.querySelector(".button-row");
      columnField = form.querySelector("#new-column");
      anchor = columnField && columnField.closest ? columnField.closest("label") : null;

      typeWrapper = document.createElement("label");
      typeWrapper.id = "create-lesson-type-wrapper";
      typeWrapper.textContent = "Тип занятия:";

      typeSelect = document.createElement("select");
      typeSelect.id = "new-lesson-type";
      typeSelect.style.marginTop = "5px";

      if (role === "organizer") {
        trialOption = document.createElement("option");
        trialOption.value = "trial";
        trialOption.textContent = "Пробное / разовое (trial)";
        typeSelect.appendChild(trialOption);
        typeSelect.value = "trial";
        typeSelect.disabled = true;
      } else {
        autoOption = document.createElement("option");
        autoOption.value = "";
        autoOption.textContent = "Авто (по предмету)";
        trialOption = document.createElement("option");
        trialOption.value = "trial";
        trialOption.textContent = "Пробное / разовое (trial)";
        typeSelect.appendChild(autoOption);
        typeSelect.appendChild(trialOption);
      }

      typeHint = document.createElement("small");
      typeHint.id = "create-lesson-type-hint";
      typeHint.style.marginTop = "6px";
      typeHint.style.color = "#51606b";
      typeHint.style.fontSize = "12px";
      typeHint.style.lineHeight = "1.4";

      typeWrapper.appendChild(typeSelect);
      typeWrapper.appendChild(typeHint);
      form.insertBefore(
        typeWrapper,
        anchor && anchor.parentNode === form ? anchor.nextSibling : buttonRow
      );
    }

    if (!datesSection) {
      datesSection = window.TrialUI.buildTrialDatesSection([]);
      datesSection.id = "create-trial-dates-section";
      form.insertBefore(datesSection, typeSelect.closest("label").nextSibling);
    }

    try {
      if (!typeSelect.__trialCreateBound) {
        typeSelect.__trialCreateBound = true;
        typeSelect.addEventListener("change", function () {
          syncCreateDialogTypeUi(form);
        });
      }

      ensureCreateLessonTypeOptions(form, typeSelect, role);
      syncCreateDialogTypeUi(form, role === "organizer");
      enhancementSucceeded = true;
    } finally {
      form.__trialCreateEnhancing = false;
      if (enhancementSucceeded) {
        form.__trialCreateEnhanced = true;
      }
    }
  }

  function ensureCreateLessonTypeOptions(form, typeSelect, role) {
    var eventOption;

    if (!form || !typeSelect) {
      return;
    }

    if (role === "event_manager") {
      typeSelect.textContent = "";
      eventOption = document.createElement("option");
      eventOption.value = EVENT_LESSON_TYPE;
      eventOption.textContent = "Veranstaltung";
      typeSelect.appendChild(eventOption);
      typeSelect.value = EVENT_LESSON_TYPE;
      typeSelect.disabled = true;
      return;
    }

    if (role === "admin" && !typeSelect.querySelector('option[value="' + EVENT_LESSON_TYPE + '"]')) {
      eventOption = document.createElement("option");
      eventOption.value = EVENT_LESSON_TYPE;
      eventOption.textContent = "Veranstaltung";
      typeSelect.appendChild(eventOption);
    }
  }

  function syncCreateDialogTypeUi(form, forceTrialColor) {
    var typeSelect = form ? form.querySelector("#new-lesson-type") : null;
    var typeHint = form ? form.querySelector("#create-lesson-type-hint") : null;
    var datesSection = form ? form.querySelector("#create-trial-dates-section, #create-event-dates-section") : null;
    var isTrial = !!(typeSelect && typeSelect.value === "trial");
    var isEvent = !!(typeSelect && typeSelect.value === EVENT_LESSON_TYPE);
    var ownerSelect;
    var subjectInput;
    var teacherInput;
    var studentsInput;
    var roomInput;

    if (!form || !typeSelect || !datesSection) {
      return;
    }

    if (isEvent) {
      datesSection.id = "create-event-dates-section";
      relabelDatesSection(datesSection, "Даты Veranstaltung (опционально):");
    } else {
      datesSection.id = "create-trial-dates-section";
      relabelDatesSection(datesSection, "Даты занятия:");
    }

    ownerSelect = ensureEventOwnerSelector(form);
    if (ownerSelect && ownerSelect.closest) {
      ownerSelect.closest("#event-owner-wrapper").style.display = isEvent ? "" : "none";
    }

    subjectInput = form.querySelector("#new-subject");
    teacherInput = form.querySelector("#new-teacher");
    studentsInput = form.querySelector("#new-students");
    roomInput = form.querySelector("#new-room");

    if (isEvent) {
      studentsInput = replaceInputWithoutAutocomplete(studentsInput, "Целевая аудитория");
      if (subjectInput) {
        subjectInput.value = EVENT_SUBJECT;
        subjectInput.readOnly = true;
      }
      if (teacherInput) {
        teacherInput.value = getSelectedEventAuthorName(form);
        teacherInput.readOnly = true;
      }
      if (studentsInput) {
        studentsInput.placeholder = "Целевая аудитория";
      }
      if (roomInput) {
        roomInput.placeholder = "0.04";
      }
      setCreateDialogColor(form, EVENT_DEFAULT_COLOR);
    } else {
      if (subjectInput) {
        subjectInput.readOnly = false;
      }
      if (teacherInput) {
        teacherInput.readOnly = false;
      }
    }

    datesSection.style.display = isTrial || isEvent ? "" : "none";
    if (typeHint) {
      typeHint.textContent =
        currentRole() === "organizer"
          ? "Организатор создаёт только trial-занятия. Ниже обязательно укажите даты проведения."
          : isEvent
            ? "Для Veranstaltung укажите свободный текст целевой аудитории; он не сохраняется в список групп. Даты можно оставить пустыми."
          : isTrial
            ? "Для trial-занятия ниже нужно указать одну или несколько дат проведения."
            : "Оставьте авто-режим для обычного индивидуального или группового занятия.";
    }

    if (isTrial) {
      maybeApplyCreateTrialColor(form, !!forceTrialColor);
    }
  }

  function maybeApplyCreateTrialColor(form, force) {
    var currentColor = (getFieldValue(form, "#color-value") || "").trim().toUpperCase();
    var regularDefault = defaultColor("group").toUpperCase();
    var trialDefault = defaultColor("trial").toUpperCase();

    if (!force && currentColor && currentColor !== regularDefault) {
      return;
    }

    setCreateDialogColor(form, trialDefault);
  }

  function setCreateDialogColor(form, color) {
    var colorValue = form ? form.querySelector("#color-value") : null;
    var colorPicker = form ? form.querySelector("#custom-color-picker") : null;

    if (colorValue) {
      colorValue.value = color;
    }
    if (colorPicker) {
      colorPicker.value = color;
    }
    if (form) {
      form.querySelectorAll(".color-option").forEach(function (option) {
        option.classList.toggle(
          "selected",
          (option.getAttribute("data-color") || "").toUpperCase() === color
        );
      });
    }
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

  function attachEditModeChangeListener() {
    if (document.__individualEditModeFlushAttached) {
      return;
    }
    document.__individualEditModeFlushAttached = true;
    document.addEventListener("schedgen:edit-mode-change", function (event) {
      if (event && event.detail && event.detail.enabled === false) {
        flushPendingRevision();
      }
    });
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
    document.addEventListener("mousedown", interceptManagedBlockPointerDown, true);
    document.addEventListener("dblclick", interceptManagedBlockDoubleClick, true);
    document.addEventListener("mousemove", handleManagedPointerMove, true);
    document.addEventListener("mousemove", handleManagedDragMove, true);
    document.addEventListener("mouseup", handleManagedDragEnd, true);
    document.addEventListener("mouseup", handleManagedResizeEnd);
  }

  function handleIndividualRevision(revision) {
    if (!revision) {
      return;
    }
    if (revision === individualRevision) {
      if (pendingIndividualRevision === revision) {
        pendingIndividualRevision = null;
        pendingRevisionNotice = null;
      }
      return;
    }
    if (!shouldDeferIndividualRefresh()) {
      pendingIndividualRevision = null;
      pendingRevisionNotice = null;
      refreshIndividualLayer();
      return;
    }
    pendingIndividualRevision = revision;
    if (pendingRevisionNotice === revision) {
      return;
    }
    pendingRevisionNotice = revision;
    showNotice(
      "Индивидуальные занятия обновлены на сервере. Завершите редактирование для синхронизации.",
      "warning",
      6000
    );
  }

  function flushPendingRevision() {
    var revision = pendingIndividualRevision;

    if (shouldDeferIndividualRefresh() || !revision) {
      return;
    }
    pendingIndividualRevision = null;
    pendingRevisionNotice = null;
    if (revision !== individualRevision) {
      refreshIndividualLayer();
    }
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

  function shouldDeferIndividualRefresh() {
    return !!(
      isInEditMode() ||
      (currentRole() === "event_manager" &&
        (eventMutationInFlight > 0 ||
          window.editDialogOpen ||
          activeDrag ||
          pendingDragStart ||
          pendingResize ||
          document.body.classList.contains("delete-mode")))
    );
  }

  function applyIndividualState(data) {
    var blocks = [];
    if (
      window.SchedGenEventManagerView &&
      typeof window.SchedGenEventManagerView.filterSchedulePayload === "function"
    ) {
      data = window.SchedGenEventManagerView.filterSchedulePayload(data);
    }
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
    pendingIndividualRevision = null;
    pendingRevisionNotice = null;

    removeIndividualBlocks();
    blocks.forEach(function (block) {
      renderIndividualBlock(block, true);
    });

    reapplyLessonTypeFilterAfterIndividualMutation();
    refreshManagedBlockInteractivity(document);
    notifySearchScheduleMutation();
  }

  function removeIndividualBlocks() {
    document
      .querySelectorAll(
        '.activity-block[data-block-id], .activity-block[data-lesson-type="individual"], .activity-block[data-lesson-type="nachhilfe"], .activity-block[data-lesson-type="trial"], .activity-block[data-lesson-type="veranstaltung"]'
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
    element.setAttribute("data-explicit-lesson-type", block.lesson_type || "individual");
    element.setAttribute("data-room", room);
    element.setAttribute("data-start-time", block.start_time || "");
    element.setAttribute("data-end-time", block.end_time || "");
    element.setAttribute("data-start-row", String(rows.start_row));
    element.setAttribute("data-row-span", String(rows.row_span));
    if (block.lesson_type === EVENT_LESSON_TYPE) {
      element.setAttribute("data-created-by", block.created_by || "");
      element.setAttribute("data-created-by-name", block.created_by_name || block.teacher || "");
      element.setAttribute("data-owner-kind", block.owner_kind || "");
      element.setAttribute("data-version", String(block.version || 1));
      if (Array.isArray(block.event_dates) && block.event_dates.length > 0) {
        element.setAttribute("data-event-dates", JSON.stringify(block.event_dates));
      }
    }
    element.style.backgroundColor = block.color || defaultColor(block.lesson_type);
    element.style.width = "100px";
    if (isDayHidden(day, container)) {
      element.style.display = "none";
    }

    if (typeof getContrastTextColor === "function") {
      element.style.color = getContrastTextColor(element.style.backgroundColor);
    }

    // Trial-specific: store dates in data attribute, apply expired style
    if (block.lesson_type === "trial") {
      var trialDates = Array.isArray(block.trial_dates) ? block.trial_dates : [];
      element.setAttribute("data-trial-dates", JSON.stringify(trialDates));
      if (window.TrialUI) {
        window.TrialUI.injectTrialStyles();
        if (typeof window.TrialUI.refreshTrialBlockAppearance === "function") {
          window.TrialUI.refreshTrialBlockAppearance(element);
        } else {
          window.TrialUI.applyTrialExpiredStyle(element, window.TrialUI.isTrialExpired(trialDates));
        }
      }
    }

    var contentLines = [
      "<strong>" + escapeHtml(block.subject || "") + "</strong>",
      escapeHtml(block.teacher || ""),
      escapeHtml(block.students || ""),
      escapeHtml(room),
      escapeHtml(timeText),
    ];

    // Show trial dates line in block body
    if (block.lesson_type === "trial" && Array.isArray(block.trial_dates) && block.trial_dates.length > 0) {
      var datesDisplay = block.trial_dates.map(function (d) {
        var p = d.split("-");
        return p.length === 3 ? p[2] + "." + p[1] + "." + p[0] : d;
      }).join(", ");
      contentLines.push("\uD83D\uDCC5 " + escapeHtml(datesDisplay));
    }

    element.innerHTML = contentLines.join("<br>");

    container.appendChild(element);
    attachIndividualBlockInteractions(element);
    applyManagedBlockInteractivity(element);

    if (!deferLayout) {
      refreshCompactRowsAfterIndividualMutation();
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
    if (!canInteractWithManagedBlock(block)) {
      return;
    }

    rect = block.getBoundingClientRect();
    if (event.clientY >= rect.bottom - 8) {
      return;
    }

    clientX = event.clientX;
    clientY = event.clientY;
    queueManagedDragStart(block, clientX, clientY);
    event.preventDefault();
  }

  function queueManagedDragStart(block, clientX, clientY) {
    clearPendingDragStart();
    pendingDragStart = {
      block: block,
      clientX: clientX,
      clientY: clientY,
      timer: window.setTimeout(function () {
        beginManagedDrag(block, clientX, clientY);
      }, 200),
    };
  }

  function interceptManagedBlockPointerDown(event) {
    var block =
      event.target && event.target.closest
        ? event.target.closest(".activity-block[data-block-id]")
        : null;

    if (!block || event.button !== 0 || !canInteractWithManagedBlock(block)) {
      return;
    }

    clearPendingDragStart();
    setLegacyDragPrevention(true);
    cancelLegacyResize(event);
    stopDomMutation(event);

    if (
      window.editDialogOpen ||
      document.body.classList.contains("delete-mode")
    ) {
      pendingResize = null;
      applyManagedBlockInteractivity(block);
      return;
    }

    if (isInManagedResizeZone(block, event.clientY)) {
      pendingResize = {
        blockId: block.getAttribute("data-block-id") || "",
        snapshot: captureBlockSnapshot(block),
      };
      pauseCompactRowsForManagedResize();
      applyManagedBlockInteractivity(block, "resize");
      return;
    }

    applyManagedBlockInteractivity(block, "move");
    queueManagedDragStart(block, event.clientX, event.clientY);
  }

  function interceptManagedBlockDoubleClick(event) {
    var block =
      event.target && event.target.closest
        ? event.target.closest(".activity-block[data-block-id]")
        : null;

    if (!block || !canInteractWithManagedBlock(block)) {
      return;
    }

    setLegacyDragPrevention(true);
    stopDomMutation(event);
    clearPendingDragStart();
    cancelManagedDrag(block);
    if (document.body.classList.contains("delete-mode")) {
      releaseLegacyDragPrevention(150);
      return;
    }
    openManagedEditDialog(block);
    releaseLegacyDragPrevention(300);
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
      !canInteractWithManagedBlock(block) ||
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
    pauseCompactRowsForManagedResize();
  }

  function handleManagedResizeEnd() {
    var resize = pendingResize;
    var block;

    if (!resize || !resize.blockId) {
      pendingResize = null;
      releaseLegacyDragPrevention();
      resumeCompactRowsAfterManagedResize(false);
      return;
    }
    pendingResize = null;
    block = document.querySelector(
      '.activity-block[data-block-id="' + cssEscape(resize.blockId) + '"]'
    );
    if (!block) {
      releaseLegacyDragPrevention();
      resumeCompactRowsAfterManagedResize(true);
      return;
    }

    try {
      persistChangedBlock(
      block,
      resize.snapshot,
      "Не удалось сохранить новую длительность занятия из-за ошибки сети."
    );
      finalizeManagedResize(block);
    } finally {
      resumeCompactRowsAfterManagedResize(true);
    }
  }
  function finalizeManagedResize(block) {
    applyManagedBlockInteractivity(block);
    releaseLegacyDragPrevention();
  }

  function isInManagedResizeZone(block, clientY) {
    var rect = block.getBoundingClientRect();
    return clientY >= rect.bottom - 6 && clientY <= rect.bottom + 2;
  }

  function beginManagedDrag(block, clientX, clientY) {
    var rect;

    if (
      !block ||
      !block.parentElement ||
      !canInteractWithManagedBlock(block)
    ) {
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
    pauseCompactRowsForManagedDrag();
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
    applyManagedBlockInteractivity(drag.block, "move");
    event.preventDefault();
  }

  function handleManagedDragEnd(event) {
    var drag = activeDrag;

    if (!drag) {
      clearPendingDragStart();
      releaseLegacyDragPrevention();
      return;
    }

    activeDrag = null;
    try {
      drag.block.style.opacity = "1";
      if (!drag.moved) {
        applyManagedBlockInteractivity(drag.block);
        releaseLegacyDragPrevention();
        return;
      }

      if (typeof BlockDropService !== "undefined" && BlockDropService) {
        BlockDropService.processBlockDrop(drag.block);
      } else if (typeof processBlockDrop === "function") {
        processBlockDrop(drag.block);
      }

      persistDraggedBlock(drag);
      applyManagedBlockInteractivity(drag.block);
      releaseLegacyDragPrevention();
      event.preventDefault();
    } finally {
      resumeCompactRowsAfterManagedDrag(true);
    }
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
      applyManagedBlockInteractivity(activeDrag.block);
    }
    activeDrag = null;
    releaseLegacyDragPrevention();
    resumeCompactRowsAfterManagedDrag(true);
  }

  function openManagedEditDialog(block) {
    if (block && !canCurrentRoleMutateBlock(block)) {
      alert(getMutationDeniedMessage("edit", block));
      return;
    }
    if (
      block &&
      currentRole() === "organizer" &&
      block.getAttribute("data-lesson-type") !== "trial"
    ) {
      alert("Организатор может редактировать только пробные/разовые занятия.");
      return;
    }
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
    form.setAttribute("autocomplete", "off");
    form.__editedBlock = block;
    if (blockId) {
      form.setAttribute("data-block-id", blockId);
    } else {
      form.removeAttribute("data-block-id");
    }
    activeEditedBlock = block;
    enhanceEditDialogForBlock(form, block);
  }

  function enhanceEditDialogForBlock(form, block) {
    var buttonRow;
    var datesSection;
    var subjectInput;
    var teacherInput;
    var studentsInput;
    var roomInput;
    var ownerNote;
    var ownerName;

    if (!form || !block || getBlockLessonType(block) !== EVENT_LESSON_TYPE || form.__eventEditEnhanced) {
      return;
    }
    form.__eventEditEnhanced = true;

    subjectInput = form.querySelector("#edit-subject");
    teacherInput = form.querySelector("#edit-teacher");
    studentsInput = form.querySelector("#edit-students");
    roomInput = form.querySelector("#edit-room");

    studentsInput = replaceInputWithoutAutocomplete(studentsInput, "Целевая аудитория");
    roomInput = replaceInputWithoutAutocomplete(roomInput, "0.04");

    if (subjectInput) {
      subjectInput.value = EVENT_SUBJECT;
      subjectInput.readOnly = true;
    }
    if (teacherInput) {
      teacherInput.value = block.getAttribute("data-created-by-name") || teacherInput.value || "";
      teacherInput.readOnly = true;
    }
    if (studentsInput) {
      studentsInput.placeholder = "Целевая аудитория";
    }

    buttonRow = form.querySelector(".button-row");
    if (window.TrialUI && buttonRow && !form.querySelector("#edit-event-dates-section")) {
      datesSection = window.TrialUI.buildTrialDatesSection(parseJsonArrayAttribute(block, "data-event-dates"));
      datesSection.id = "edit-event-dates-section";
      relabelDatesSection(datesSection, "Даты Veranstaltung (опционально):");
      form.insertBefore(datesSection, buttonRow);
    }

    ownerName = block.getAttribute("data-created-by-name") || block.getAttribute("data-created-by") || "";
    if (ownerName && buttonRow && !form.querySelector("#edit-event-owner-note")) {
      ownerNote = document.createElement("small");
      ownerNote.id = "edit-event-owner-note";
      ownerNote.className = "event-form-hint";
      ownerNote.textContent = "Владелец: " + ownerName + ". Владелец при редактировании не меняется.";
      form.insertBefore(ownerNote, buttonRow);
    }
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
        "data-trial-dates": block.getAttribute("data-trial-dates"),
        "data-event-dates": block.getAttribute("data-event-dates"),
        "data-created-by": block.getAttribute("data-created-by"),
        "data-created-by-name": block.getAttribute("data-created-by-name"),
        "data-owner-kind": block.getAttribute("data-owner-kind"),
        "data-version": block.getAttribute("data-version"),
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

    reapplyLessonTypeFilterAfterIndividualMutation();
    if (typeof ConflictDetector !== "undefined") {
      ConflictDetector.highlightConflicts();
    }
  }

  function buildBlockPayloadFromElement(block) {
    var lessonType = getBlockLessonType(block);
    if (
      lessonType === EVENT_LESSON_TYPE &&
      window.SchedGenEventManagerView &&
      typeof window.SchedGenEventManagerView.syncEventBlockFromRows === "function"
    ) {
      window.SchedGenEventManagerView.syncEventBlockFromRows(block);
    }
    var parts = (block.innerHTML || "").split(/<br\s*\/?>/i);
    var attrStart = (block.getAttribute("data-start-time") || "").trim();
    var attrEnd = (block.getAttribute("data-end-time") || "").trim();
    var timeText =
      lessonType === EVENT_LESSON_TYPE && attrStart && attrEnd
        ? attrStart + "-" + attrEnd
        : stripHtml(parts[4] || "").trim();
    var timeInfo = parseTimeRange(timeText);
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
      !(block.getAttribute("data-room") || stripHtml(parts[3] || "").trim()) ||
      !getBlockSubject(block)
    ) {
      return null;
    }

    var trialDatesRaw = block.getAttribute("data-trial-dates");
    var trialDates;
    try {
      trialDates = trialDatesRaw ? JSON.parse(trialDatesRaw) : undefined;
    } catch (e) {
      trialDates = undefined;
    }

    var payload = {
      building: (block.getAttribute("data-building") || "").trim(),
      day: (block.getAttribute("data-day") || "").trim(),
      room: (block.getAttribute("data-room") || stripHtml(parts[3] || "")).trim(),
      subject: lessonType === EVENT_LESSON_TYPE ? EVENT_SUBJECT : getBlockSubject(block).trim(),
      teacher:
        lessonType === EVENT_LESSON_TYPE
          ? block.getAttribute("data-created-by-name") || stripHtml(parts[1] || "").trim()
          : stripHtml(parts[1] || "").trim(),
      students: stripHtml(parts[2] || "").trim(),
      lesson_type: lessonType,
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: startRow >= 0 ? startRow : timeInfo.start_row,
      row_span: rowSpan >= 1 ? rowSpan : timeInfo.row_span,
      color: block.style.backgroundColor || defaultColor(lessonType),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
    if (lessonType === "trial" && Array.isArray(trialDates)) {
      payload.trial_dates = trialDates;
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      payload.room = normalizeEventRoom(payload.room, payload.building);
      payload.event_dates = parseJsonArrayAttribute(block, "data-event-dates");
      payload.expected_version = toInteger(block.getAttribute("data-version"), 0);
    }
    return payload;
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
    var isEventPayload;

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

    isEventPayload = payload.lesson_type === EVENT_LESSON_TYPE;
    if (isEventPayload) {
      beginEventMutation();
    }
    requestJson(
      (payload.lesson_type === EVENT_LESSON_TYPE ? "/api/events/" : "/api/blocks/") + encodeURIComponent(blockId),
      "PUT",
      payload
    ).then(
      function (result) {
        if (isEventPayload) {
          endEventMutation();
        }
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
        if (refreshIndividualLayerForCleanup(result)) {
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        removeBlockById(blockId);
        renderIndividualBlock(result.data.block, true);
        reapplyLessonTypeFilterAfterIndividualMutation();
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
    if (currentRole() === "event_manager") {
      return -1;
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
    var eventRows;

    if (
      currentRole() === "event_manager" &&
      window.SchedGenEventManagerView &&
      typeof window.SchedGenEventManagerView.resolveRowsForBlock === "function"
    ) {
      eventRows = window.SchedGenEventManagerView.resolveRowsForBlock(block);
      if (eventRows) {
        return eventRows;
      }
    }
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
      startMinutes: startMinutes,
      endMinutes: endMinutes,
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

    if (payload.lesson_type === EVENT_LESSON_TYPE) {
      stopDomMutation(event);
      if (!canUseEventEditor()) {
        alert("Недостаточно прав для создания Veranstaltung.");
        return;
      }
      beginEventMutation();
      requestJson("/api/events", "POST", payload).then(function (result) {
        endEventMutation();
        if (!result) {
          alert("Не удалось создать Veranstaltung из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          handleMutationError(result, "Недостаточно прав для создания Veranstaltung.");
          return;
        }
        if (resultRequiresIndividualRefresh(result)) {
          closeOverlay(form);
          refreshIndividualLayer();
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        closeOverlay(form);
        renderIndividualBlock(result.data.block, true);
        reapplyLessonTypeFilterAfterIndividualMutation();
        if (typeof ConflictDetector !== "undefined") {
          ConflictDetector.highlightConflicts();
        }
      });
      return;
    }

    if (payload.lesson_type === "group") {
      if (role === "editor") {
        stopDomMutation(event);
        alert("Недостаточно прав для создания этого типа занятия.");
      }
      return;
    }

    if (payload.lesson_type !== "trial" && role === "organizer") {
      stopDomMutation(event);
      alert("Организатор может создавать только пробные/разовые занятия.");
      return;
    }

    if (payload.day === "So" && payload.lesson_type !== "trial") {
      stopDomMutation(event);
      alert("Воскресенье доступно только для trial-занятий.");
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
      if (resultRequiresIndividualRefresh(result)) {
        closeOverlay(form);
        refreshIndividualLayer();
        return;
      }
      individualRevision = result.data.individual_revision || individualRevision;
      closeOverlay(form);
      renderIndividualBlock(result.data.block, true);
      reapplyLessonTypeFilterAfterIndividualMutation();
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

    if (currentLessonType === EVENT_LESSON_TYPE || payload.lesson_type === EVENT_LESSON_TYPE) {
      stopDomMutation(event);
      if (!blockId) {
        alert("Блок Veranstaltung не найден на сервере.");
        return;
      }
      if (!canUseEventEditor() || !canCurrentRoleMutateBlock(block)) {
        alert("Недостаточно прав для изменения Veranstaltung.");
        return;
      }
      beginEventMutation();
      requestJson("/api/events/" + encodeURIComponent(blockId), "PUT", payload).then(
        function (result) {
          endEventMutation();
          if (!result) {
            alert("Не удалось обновить Veranstaltung из-за ошибки сети.");
            return;
          }
          if (!result.ok) {
            handleMutationError(result, "Недостаточно прав для изменения Veranstaltung.");
            return;
          }
          if (resultRequiresIndividualRefresh(result)) {
            activeEditedBlock = null;
            closeOverlay(form);
            refreshIndividualLayer();
            return;
          }
          individualRevision = result.data.individual_revision || individualRevision;
          activeEditedBlock = null;
          closeOverlay(form);
          removeBlockById(blockId);
          renderIndividualBlock(result.data.block, true);
          reapplyLessonTypeFilterAfterIndividualMutation();
          if (typeof ConflictDetector !== "undefined") {
            ConflictDetector.highlightConflicts();
          }
        }
      );
      return;
    }

    if (currentLessonType !== "trial" && currentRole() === "organizer") {
      stopDomMutation(event);
      alert("Организатор может редактировать только пробные/разовые занятия.");
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
        if (resultRequiresIndividualRefresh(result)) {
          activeEditedBlock = null;
          closeOverlay(form);
          refreshIndividualLayer();
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        activeEditedBlock = null;
        closeOverlay(form);
        removeBlockById(blockId);
        renderIndividualBlock(result.data.block, true);
        reapplyLessonTypeFilterAfterIndividualMutation();
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

    if (!canCurrentRoleMutateBlock(block)) {
      stopDomMutation(event);
      alert(getMutationDeniedMessage("delete", block));
      return;
    }

    if (!blockId && lessonType === "group") {
      if (currentRole() === "editor") {
        stopDomMutation(event);
        alert("Недостаточно прав для удаления групповых занятий.");
      }
      return;
    }

    if (lessonType !== "trial" && currentRole() === "organizer") {
      stopDomMutation(event);
      alert("Организатор может удалять только пробные/разовые занятия.");
      return;
    }

    if (lessonType === EVENT_LESSON_TYPE) {
      stopDomMutation(event);
      if (!blockId) {
        alert("Блок Veranstaltung не найден на сервере.");
        return;
      }
      if (!canUseEventEditor()) {
        alert("Недостаточно прав для удаления Veranstaltung.");
        return;
      }
      info = describeBlock(block);
      if (
        !confirm(
          "Вы действительно хотите удалить Veranstaltung?\n\n" +
            "Здание: " +
            info.building +
            "\nДень: " +
            info.day +
            "\nЦелевая аудитория: " +
            info.students +
            "\nВремя: " +
            info.time
        )
      ) {
        return;
      }
      beginEventMutation();
      requestJson("/api/events/" + encodeURIComponent(blockId), "DELETE", {
        expected_version: toInteger(block.getAttribute("data-version"), 0),
      }).then(function (result) {
        endEventMutation();
        if (!result) {
          alert("Не удалось удалить Veranstaltung из-за ошибки сети.");
          return;
        }
        if (!result.ok) {
          handleMutationError(result, "Недостаточно прав для удаления Veranstaltung.");
          return;
        }
        if (refreshIndividualLayerForCleanup(result)) {
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        if (block.parentNode) {
          block.parentNode.removeChild(block);
        }
        refreshCompactRowsAfterIndividualMutation();
        showNotice("Veranstaltung удалена: " + info.time, "success");
      });
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
        if (refreshIndividualLayerForCleanup(result)) {
          return;
        }
        individualRevision = result.data.individual_revision || individualRevision;
        if (block.parentNode) {
          block.parentNode.removeChild(block);
        }
        refreshCompactRowsAfterIndividualMutation();
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
        refreshCompactRowsAfterIndividualMutation();
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

    if (columnHasEventBlocks(container, building, day, colIndex)) {
      alert(
        "Нельзя удалить кабинет " +
          room +
          ": он содержит Veranstaltung blocks."
      );
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

    if (currentRole() === "organizer" && columnHasNonTrialBlocks(container, building, day, colIndex)) {
      alert(
        "Нельзя удалить кабинет " +
          room +
          ": он содержит занятия других типов."
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
      if (resultRequiresIndividualRefresh(result)) {
        if (typeof removeColumn === "function") {
          removeColumn(building, day, colIndex);
        }
        refreshIndividualLayer();
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
    var resolvedType = resolveCreateLessonType(form);
    var subject = resolvedType === EVENT_LESSON_TYPE ? EVENT_SUBJECT : getFieldValue(form, "#new-subject");
    var teacher = resolvedType === EVENT_LESSON_TYPE ? getSelectedEventAuthorName(form) : getFieldValue(form, "#new-teacher");
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

    var createPayload = {
      building: building,
      day: day,
      room: resolvedType === EVENT_LESSON_TYPE ? normalizeEventRoom(room, building) : room,
      subject: subject,
      teacher: teacher,
      students: students,
      lesson_type: resolvedType,
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: timeInfo.start_row,
      row_span: timeInfo.row_span,
      color: color || defaultColor(resolvedType),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
    if (resolvedType === "trial" && window.TrialUI) {
      createPayload.trial_dates = collectCreateTrialDates(form);
    }
    if (resolvedType === EVENT_LESSON_TYPE) {
      createPayload.event_dates = collectCreateEventDates(form);
      createPayload.author_login = getSelectedEventAuthorLogin(form);
    }
    return createPayload;
  }

  function resolveCreateLessonType(form) {
    var typeSelectEl = form ? form.querySelector("#new-lesson-type") : null;
    var explicitType = typeSelectEl ? typeSelectEl.value : "";

    if (currentRole() === "event_manager" || explicitType === EVENT_LESSON_TYPE) {
      return EVENT_LESSON_TYPE;
    }
    if (currentRole() === "organizer" || explicitType === "trial") {
      return "trial";
    }
    return inferLessonType(getFieldValue(form, "#new-subject"));
  }

  function collectCreateTrialDates(form) {
    var datesSectionEl = form ? form.querySelector("#create-trial-dates-section") : null;
    return window.TrialUI ? window.TrialUI.collectTrialDates(datesSectionEl || form) : [];
  }

  function collectEditTrialDates(form) {
    var datesSectionEl = form ? form.querySelector("#edit-trial-dates-section") : null;
    return window.TrialUI ? window.TrialUI.collectTrialDates(datesSectionEl || form) : [];
  }

  function collectCreateEventDates(form) {
    var datesSectionEl = form ? form.querySelector("#create-event-dates-section, #create-trial-dates-section") : null;
    return window.TrialUI ? window.TrialUI.collectTrialDates(datesSectionEl || form) : [];
  }

  function collectEditEventDates(form) {
    var datesSectionEl = form ? form.querySelector("#edit-event-dates-section") : null;
    return window.TrialUI ? window.TrialUI.collectTrialDates(datesSectionEl || form) : [];
  }

  function parseJsonArrayAttribute(element, name) {
    var raw = element ? element.getAttribute(name) : "";
    if (!raw) {
      return [];
    }
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function normalizeEventRoom(room, building) {
    var normalized = (room || "").trim();
    if (building === "Villa" && normalized.length > 1 && normalized.charAt(0).toUpperCase() === "V") {
      return normalized.slice(1).trim();
    }
    if (building === "Kolibri" && normalized.length > 1 && normalized.charAt(0).toUpperCase() === "K") {
      return normalized.slice(1).trim();
    }
    return normalized;
  }

  function isEventRoom(building, room) {
    var rooms = EVENT_ROOM_SCOPE[building] || [];
    return rooms.indexOf(normalizeEventRoom(room, building)) !== -1;
  }

  function isQuarterHourTimeRange(timeInfo) {
    return !!(
      timeInfo &&
      timeInfo.startMinutes % 15 === 0 &&
      timeInfo.endMinutes % 15 === 0
    );
  }

  function isEventTimeInsideGrid(timeInfo) {
    if (
      !timeInfo ||
      !window.SchedGenEventManagerView ||
      typeof window.SchedGenEventManagerView.isTimeRangeInsideGrid !== "function"
    ) {
      return true;
    }
    return window.SchedGenEventManagerView.isTimeRangeInsideGrid(
      timeInfo.start_time,
      timeInfo.end_time
    );
  }

  function getSelectedEventAuthorLogin(form) {
    var ownerSelect = form ? form.querySelector("#event-author-login") : null;
    if (ownerSelect) {
      return (ownerSelect.value || "").trim();
    }
    return currentRole() === "admin" ? (window.CURRENT_USER || "") : "";
  }

  function getSelectedEventAuthorName(form) {
    var ownerSelect = form ? form.querySelector("#event-author-login") : null;
    var selected;
    if (ownerSelect && ownerSelect.selectedIndex >= 0) {
      selected = ownerSelect.options[ownerSelect.selectedIndex];
      return selected.getAttribute("data-display-name") || selected.textContent || "";
    }
    return window.DISPLAY_NAME || window.CURRENT_USER || "";
  }

  function ensureEventOwnerSelector(form) {
    var typeWrapper;
    var ownerWrapper;
    var select;
    var adminLogin;
    var adminName;

    if (!form || currentRole() !== "admin") {
      return null;
    }
    ownerWrapper = form.querySelector("#event-owner-wrapper");
    if (ownerWrapper) {
      return ownerWrapper.querySelector("#event-author-login");
    }

    adminLogin = window.CURRENT_USER || "";
    adminName = window.DISPLAY_NAME || adminLogin || "Admin";
    typeWrapper = form.querySelector("#create-lesson-type-wrapper");
    ownerWrapper = document.createElement("label");
    ownerWrapper.id = "event-owner-wrapper";
    ownerWrapper.className = "event-owner-wrapper";
    ownerWrapper.textContent = "Владелец Veranstaltung:";

    select = document.createElement("select");
    select.id = "event-author-login";
    appendEventOwnerOption(select, adminLogin, adminName, "admin");
    ownerWrapper.appendChild(select);

    var hint = document.createElement("small");
    hint.textContent = "Администратор может создать событие от своего имени или от имени event-manager.";
    ownerWrapper.appendChild(hint);

    form.insertBefore(ownerWrapper, typeWrapper && typeWrapper.nextSibling ? typeWrapper.nextSibling : form.querySelector(".button-row"));
    select.addEventListener("change", function () {
      syncCreateDialogTypeUi(form);
    });
    loadEventManagers().then(function (users) {
      users.forEach(function (user) {
        appendEventOwnerOption(select, user.login, user.display_name || user.login, "event_manager");
      });
      syncCreateDialogTypeUi(form);
    });
    return select;
  }

  function appendEventOwnerOption(select, login, displayName, role) {
    var option;
    if (!select || !login || select.querySelector('option[value="' + cssEscape(login) + '"]')) {
      return;
    }
    option = document.createElement("option");
    option.value = login;
    option.textContent = displayName || login;
    option.setAttribute("data-display-name", displayName || login);
    option.setAttribute("data-role", role || "");
    select.appendChild(option);
  }

  function loadEventManagers() {
    if (Array.isArray(eventManagers)) {
      return Promise.resolve(eventManagers);
    }
    if (eventManagersRequest) {
      return eventManagersRequest;
    }
    eventManagersRequest = requestJson("/api/users/event_managers").then(function (result) {
      if (!result || !result.ok || !Array.isArray(result.data && result.data.users)) {
        eventManagers = [];
        return eventManagers;
      }
      eventManagers = result.data.users;
      return eventManagers;
    });
    return eventManagersRequest;
  }

  function replaceInputWithoutAutocomplete(input, placeholder) {
    var clone;
    if (!input || input.getAttribute("data-event-plain-input") === "1") {
      return input;
    }
    clone = input.cloneNode(true);
    clone.setAttribute("autocomplete", "off");
    clone.setAttribute("data-event-plain-input", "1");
    if (placeholder) {
      clone.placeholder = placeholder;
    }
    input.parentNode.replaceChild(clone, input);
    return clone;
  }

  function relabelDatesSection(section, labelText) {
    var label = section ? section.querySelector("label") : null;
    if (label) {
      label.textContent = labelText;
    }
  }

  function buildEditPayload(form, block) {
    var building = getFieldValue(form, "#edit-building");
    var currentType = getBlockLessonType(block);
    var subject = currentType === EVENT_LESSON_TYPE ? EVENT_SUBJECT : getFieldValue(form, "#edit-subject");
    var teacher =
      currentType === EVENT_LESSON_TYPE
        ? (block.getAttribute("data-created-by-name") || getFieldValue(form, "#edit-teacher"))
        : getFieldValue(form, "#edit-teacher");
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

    var editResolvedType =
      currentType === EVENT_LESSON_TYPE
        ? EVENT_LESSON_TYPE
        : currentType === "trial"
          ? "trial"
          : inferLessonType(subject);

    var editPayload = {
      building: building,
      day: day,
      room: editResolvedType === EVENT_LESSON_TYPE ? normalizeEventRoom(room, building) : room,
      subject: subject,
      teacher: teacher,
      students: students,
      lesson_type: editResolvedType,
      start_time: timeInfo.start_time,
      end_time: timeInfo.end_time,
      start_row: timeInfo.start_row,
      row_span: timeInfo.row_span,
      color: block.style.backgroundColor || defaultColor(editResolvedType),
      col_index: colIndex >= 0 ? colIndex : undefined,
    };
    if (editResolvedType === "trial" && window.TrialUI) {
      var editDatesSection = form ? form.querySelector("#edit-trial-dates-section") : null;
      editPayload.trial_dates = window.TrialUI.collectTrialDates(editDatesSection || form);
    }
    if (editResolvedType === EVENT_LESSON_TYPE) {
      editPayload.event_dates = collectEditEventDates(form);
      editPayload.expected_version = toInteger(block.getAttribute("data-version"), 0);
    }
    return editPayload;
  }

  function getCreateValidationError(form) {
    var lessonType = resolveCreateLessonType(form);
    var timeInfo = parseTimeRange(getFieldValue(form, "#new-time").trim());
    var error = validateBlockInputs(
      getFieldValue(form, "#new-building"),
      getFieldValue(form, "#new-day"),
      getFieldValue(form, "#new-room").trim(),
      lessonType === EVENT_LESSON_TYPE ? EVENT_SUBJECT : getFieldValue(form, "#new-subject"),
      getFieldValue(form, "#new-time").trim()
    );

    if (error) {
      return error;
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      if (!canUseEventEditor()) {
        return "Недостаточно прав для создания Veranstaltung.";
      }
      if (!isEventRoom(getFieldValue(form, "#new-building"), getFieldValue(form, "#new-room").trim())) {
        return "Veranstaltung можно создать только в разрешённых event-кабинетах.";
      }
      if (!isEventTimeInsideGrid(timeInfo)) {
        return "Veranstaltung time is outside the visible event grid.";
      }
      if (!isQuarterHourTimeRange(timeInfo)) {
        return "Время Veranstaltung должно начинаться и заканчиваться на 15-минутной границе.";
      }
    }
    if (lessonType === "trial" && collectCreateTrialDates(form).length === 0) {
      return "Для trial-занятия нужно указать хотя бы одну дату проведения.";
    }
    if (getFieldValue(form, "#new-day") === "So" && lessonType !== "trial") {
      return "Воскресенье доступно только для trial-занятий.";
    }
    return null;
  }

  function getEditValidationError(form) {
    var editedBlock = resolveEditedBlock(form);
    var lessonType = editedBlock ? getBlockLessonType(editedBlock) : "";
    var timeInfo = parseTimeRange(getFieldValue(form, "#edit-time").trim());
    var error = validateBlockInputs(
      getFieldValue(form, "#edit-building"),
      "x",
      getFieldValue(form, "#edit-room").trim(),
      lessonType === EVENT_LESSON_TYPE ? EVENT_SUBJECT : getFieldValue(form, "#edit-subject"),
      getFieldValue(form, "#edit-time").trim()
    );

    if (error) {
      return error;
    }
    if (lessonType === EVENT_LESSON_TYPE) {
      if (!canUseEventEditor() || !canCurrentRoleMutateBlock(editedBlock)) {
        return "Недостаточно прав для изменения Veranstaltung.";
      }
      if (!isEventRoom(getFieldValue(form, "#edit-building"), getFieldValue(form, "#edit-room").trim())) {
        return "Veranstaltung можно сохранить только в разрешённых event-кабинетах.";
      }
      if (!isEventTimeInsideGrid(timeInfo)) {
        return "Veranstaltung time is outside the visible event grid.";
      }
      if (!isQuarterHourTimeRange(timeInfo)) {
        return "Время Veranstaltung должно начинаться и заканчиваться на 15-минутной границе.";
      }
    }
    if (
      editedBlock &&
      getBlockLessonType(editedBlock) === "trial" &&
      collectEditTrialDates(form).length === 0
    ) {
      return "Для trial-занятия нужно указать хотя бы одну дату проведения.";
    }
    return null;
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
    refreshIndividualLayerForCleanup(result);
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
    if (result.status === 409 && code === "EVENT_VERSION_CONFLICT") {
      alert("Veranstaltung уже изменена другим пользователем. Обновите расписание и повторите действие.");
      refreshIndividualLayer();
      return;
    }
    if (result.status === 409 && code === "EVENT_ROOM_CONFLICT") {
      alert("Кабинет уже занят в это время. Измените время или кабинет Veranstaltung.");
      return;
    }
    if (result.status === 423 && code === "SCHEDULE_MUTATION_BUSY") {
      alert("Расписание сейчас изменяется другим процессом. Повторите действие позже.");
      return;
    }
    if (result.status === 503 && code === "OCCUPANCY_UNAVAILABLE") {
      alert("Проверка занятости кабинетов временно недоступна. Veranstaltung не сохранена.");
      return;
    }
    if (result.status === 400 && error === "Forbidden lesson_type") {
      alert(forbiddenMessage);
      return;
    }
    if (result.status === 403 && code === "COLUMN_HAS_GROUP_LESSONS") {
      alert("Нельзя удалить кабинет: в опубликованном расписании есть групповые занятия.");
      return;
    }
    if (result.status === 403 && code === "COLUMN_HAS_NON_TRIAL_BLOCKS") {
      alert("Нельзя удалить кабинет: в колонке есть занятия, кроме trial.");
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
      students: stripHtml(parts[2] || ""),
      time: stripHtml(parts[4] || ""),
    };
  }

  function getBlockLessonType(block) {
    if (!block) {
      return "group";
    }
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

  function columnHasNonTrialBlocks(container, building, day, colIndex) {
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
        getBlockLessonType(block) !== "trial"
      );
    });
  }

  function columnHasEventBlocks(container, building, day, colIndex) {
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
        getBlockLessonType(block) === EVENT_LESSON_TYPE
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
    if (lessonType === "nachhilfe") return "#D8F0FF";
    if (lessonType === "trial") return "#E8F5E9";
    if (lessonType === EVENT_LESSON_TYPE) return EVENT_DEFAULT_COLOR;
    return "#FFF1BF";
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
