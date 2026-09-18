const blocks = JSON.parse(document.querySelector("#blocks-data").textContent);
const bufferDefaults = JSON.parse(document.querySelector("#buffer-defaults-data").textContent);
const dashboard = document.querySelector(".dashboard");
const form = document.querySelector("#block-form");
const showFormButton = document.querySelector("#show-block-form");
const showEverytimeImportButton = document.querySelector("#show-everytime-import");
const everytimeImportForm = document.querySelector("#everytime-import-form");
const sourceInput = document.querySelector("#source-input");
const heading = document.querySelector("#form-heading");
const recurringFields = document.querySelector("#recurring-fields");
const oneTimeFields = document.querySelector("#one-time-fields");
const cancelEdit = document.querySelector("#cancel-edit");
const cancelEditSecondary = document.querySelector("#cancel-edit-secondary");
const titles = { timetable: "시간표", manual: "일정", google_calendar: "구글 캘린더" };
const grid = document.querySelector("#week-grid");
const weekLabel = document.querySelector("#week-label");
const googleWeekLabel = document.querySelector("#google-week-label");
const calendarStartHourInput = document.querySelector("#calendar-start-hour");
const calendarEndHourInput = document.querySelector("#calendar-end-hour");
const calendarScroll = document.querySelector("#calendar-scroll");
const calendarDescription = document.querySelector("#calendar-description");
const bookmarkletDialog = document.querySelector("#bookmarklet-dialog");
const bookmarkletDialogKey = "fill4you.bookmarklet-dialog";
const recentlyRevokedBookmarkletKey = "fill4you.recently-revoked-bookmarklet";
const dashboardStateKey = "fill4you.dashboard-state";
const hourHeight = 44;
const minutesPerHour = 60;
let firstHour = Number(calendarStartHourInput.value);
let lastHour = Number(calendarEndHourInput.value);
let currentWeekStart = parseDate(dashboard.dataset.weekStart);
let highlightedBlockTimer;

function updateEditorVisibility(showForm) {
  form.hidden = !showForm;
  const canAdd = sourceInput.value === "timetable" || sourceInput.value === "manual";
  showFormButton.hidden = showForm || !canAdd;
  showEverytimeImportButton.hidden = showForm || sourceInput.value !== "timetable";
  if (showForm) everytimeImportForm.hidden = true;
}

function updateWeekdayFields() {
  const canSelectMultiple = form.action.endsWith("/blocks")
    && sourceInput.value === "timetable"
    && document.querySelector('input[name="schedule_type"]:checked').value === "recurring";
  document.querySelector("#multiple-weekdays-field").hidden = !canSelectMultiple;
  document.querySelector("#single-weekday-field").hidden = canSelectMultiple;
  document.querySelector("#weekday-input").disabled = canSelectMultiple;
}

function setScheduleType(type) {
  const recurring = type === "recurring";
  recurringFields.hidden = !recurring;
  oneTimeFields.hidden = recurring;
  recurringFields.querySelectorAll("input, select").forEach((input) => { input.required = recurring; });
  oneTimeFields.querySelectorAll("input").forEach((input) => { input.required = !recurring; });
}

function resetForm() {
  const selectedSource = sourceInput.value;
  form.action = "/blocks";
  form.reset();
  sourceInput.value = selectedSource;
  document.querySelector('input[name="schedule_type"][value="recurring"]').checked = true;
  setScheduleType("recurring");
  updateWeekdayFields();
  heading.textContent = selectedSource === "timetable" ? "수동으로 강의 추가" : `${titles[selectedSource]} 추가`;
  showFormButton.textContent = selectedSource === "timetable" ? "수동으로 강의 추가" : `${titles[selectedSource]} 추가`;
  document.querySelector("#save-button").textContent = "추가";
  const [beforeBuffer, afterBuffer] = bufferDefaults[selectedSource];
  document.querySelector("#before-buffer-input").value = beforeBuffer;
  document.querySelector("#after-buffer-input").value = afterBuffer;
  updateEditorVisibility(false);
}

function selectSource(source, moveFocus = false) {
  const tab = document.querySelector(`.source-tab[data-source="${source}"]`);
  if (!tab) return;
  sourceInput.value = source;
  document.querySelectorAll(".source-tab").forEach((item) => {
    const selected = item === tab;
    item.classList.toggle("is-active", selected);
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll("[data-source-list]").forEach((list) => {
    list.hidden = list.dataset.sourceList !== source;
  });
  resetForm();
  if (moveFocus) tab.focus();
}

function saveDashboardState() {
  try {
    sessionStorage.setItem(dashboardStateKey, JSON.stringify({
      source: sourceInput.value,
      weekStart: formatDate(currentWeekStart),
      startHour: calendarStartHourInput.value,
      endHour: calendarEndHourInput.value,
      calendarScrollLeft: calendarScroll.scrollLeft,
      pageScrollY: window.scrollY,
    }));
  } catch (_) { /* The dashboard remains usable when browser storage is unavailable. */ }
}

function readDashboardState() {
  try {
    const storedState = sessionStorage.getItem(dashboardStateKey);
    sessionStorage.removeItem(dashboardStateKey);
    return storedState ? JSON.parse(storedState) : null;
  } catch (_) {
    return null;
  }
}

function revealBlock(block) {
  selectSource(block.source);
  const item = document.querySelector(`.block-card[data-block-id="${block.id}"]`);
  if (!item) return;
  document.querySelectorAll(".block-card.is-highlighted").forEach((card) => card.classList.remove("is-highlighted"));
  window.clearTimeout(highlightedBlockTimer);
  item.scrollIntoView({ behavior: "smooth", block: "center" });
  item.classList.add("is-highlighted");
  highlightedBlockTimer = window.setTimeout(() => item.classList.remove("is-highlighted"), 2200);
}

function parseDate(dateValue) {
  const [year, month, day] = dateValue.split("-").map(Number);
  return new Date(year, month - 1, day, 12);
}

function formatDate(date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

function addDays(date, count) {
  const next = new Date(date);
  next.setDate(next.getDate() + count);
  return next;
}

function createDates(startDate) {
  return Array.from({ length: 7 }, (_, index) => addDays(startDate, index));
}

function minutesFromTime(value) {
  const [hour, minute] = value.slice(0, 5).split(":").map(Number);
  return hour * minutesPerHour + minute;
}

function blockSegmentOnDate(block, date) {
  const before = block.beforeBufferMinutes || 0;
  const after = block.afterBufferMinutes || 0;
  if (block.isRecurring) {
    for (const dayOffset of [-1, 0, 1]) {
      const blockDate = addDays(date, dayOffset);
      if (block.weekday !== (blockDate.getDay() + 6) % 7) continue;
      const actualStart = dayOffset * 24 * minutesPerHour + minutesFromTime(block.startTime);
      const actualEnd = dayOffset * 24 * minutesPerHour + minutesFromTime(block.endTime);
      const start = actualStart - before;
      const end = actualEnd + after;
      if (start < 24 * minutesPerHour && end > 0) return { start, end, actualStart, actualEnd };
    }
    return null;
  }
  const dayStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const eventStart = new Date(block.startsAt);
  const eventEnd = new Date(block.endsAt);
  const bufferedStart = new Date(eventStart);
  const bufferedEnd = new Date(eventEnd);
  bufferedStart.setMinutes(bufferedStart.getMinutes() - before);
  bufferedEnd.setMinutes(bufferedEnd.getMinutes() + after);
  const start = Math.round((bufferedStart - dayStart) / 60000);
  const end = Math.round((bufferedEnd - dayStart) / 60000);
  const actualStart = Math.round((eventStart - dayStart) / 60000);
  const actualEnd = Math.round((eventEnd - dayStart) / 60000);
  return start < 24 * minutesPerHour && end > 0
    ? { start, end, actualStart, actualEnd }
    : null;
}

function sourceLabel(source) {
  return { timetable: "시간표", manual: "직접 추가", google_calendar: "구글 캘린더" }[source];
}

function layoutSegments(segments) {
  const sorted = [...segments].sort((a, b) => a.start - b.start || b.end - a.end);
  const clusters = [];
  let cluster = [];
  let clusterEnd = -1;
  sorted.forEach((segment) => {
    if (cluster.length && segment.start >= clusterEnd) {
      clusters.push(cluster);
      cluster = [];
      clusterEnd = -1;
    }
    cluster.push(segment);
    clusterEnd = Math.max(clusterEnd, segment.end);
  });
  if (cluster.length) clusters.push(cluster);

  return clusters.flatMap((cluster) => {
    const columns = [];
    cluster.forEach((segment) => {
      let column = columns.findIndex((columnEnd) => columnEnd <= segment.start);
      if (column === -1) {
        column = columns.length;
        columns.push(segment.end);
      } else {
        columns[column] = segment.end;
      }
      segment.column = column;
    });
    return cluster.map((segment) => ({ ...segment, columns: columns.length }));
  });
}

function describeBlock(block, date, segment) {
  const dateText = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "long" }).format(date);
  const startsAt = segment.fullActualStart ?? segment.actualStart;
  const endsAt = segment.fullActualEnd ?? segment.actualEnd;
  const starts = `${String(Math.floor(startsAt / 60)).padStart(2, "0")}:${String(startsAt % 60).padStart(2, "0")}`;
  const ends = `${String(Math.floor(endsAt / 60)).padStart(2, "0")}:${String(endsAt % 60).padStart(2, "0")}`;
  return `${block.title}, ${sourceLabel(block.source)}, ${dateText} ${starts}–${ends}, 버퍼 전 ${block.beforeBufferMinutes}분 후 ${block.afterBufferMinutes}분`;
}

function applyBlockGeometry(item, dayIndex, column, columns, start, end) {
  item.style.left = `calc(4rem + ${dayIndex} * ((100% - 4rem) / 7) + ${column} * ((100% - 4rem) / 7 / ${columns}) + 3px)`;
  item.style.width = `calc((100% - 4rem) / 7 / ${columns} - 6px)`;
  item.style.top = `calc(44px + ${(start - firstHour * minutesPerHour) * (hourHeight / minutesPerHour)}px + 2px)`;
  item.style.height = `${Math.max((end - start) * (hourHeight / minutesPerHour) - 4, 6)}px`;
}

function renderBlock(segment, dayIndex) {
  const { block, date, start, end, actualStart, actualEnd, column, columns } = segment;
  const buffer = document.createElement("div");
  buffer.className = "preview-buffer";
  buffer.setAttribute("aria-hidden", "true");
  applyBlockGeometry(buffer, dayIndex, column, columns, start, end);
  grid.append(buffer);
  const visibleActualStart = Math.max(actualStart, firstHour * minutesPerHour);
  const visibleActualEnd = Math.min(actualEnd, lastHour * minutesPerHour);
  if (visibleActualStart >= visibleActualEnd) return;
  const item = document.createElement("button");
  item.type = "button";
  item.className = `preview-block source-${block.source}`;
  item.textContent = block.title;
  item.setAttribute("aria-label", describeBlock(block, date, segment));
  applyBlockGeometry(item, dayIndex, column, columns, visibleActualStart, visibleActualEnd);
  item.style.minHeight = "24px";
  item.addEventListener("click", () => {
    calendarDescription.textContent = describeBlock(block, date, segment);
    revealBlock(block);
  });
  grid.append(item);
}

function renderCalendar() {
  const dates = createDates(currentWeekStart);
  const dateFormatter = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", weekday: "short" });
  const rangeFormatter = new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" });
  const weekRange = `${rangeFormatter.format(dates[0])} – ${rangeFormatter.format(dates[6])}`;
  weekLabel.textContent = weekRange;
  googleWeekLabel.textContent = weekRange;
  grid.style.gridTemplateColumns = "4rem repeat(7, minmax(88px, 1fr))";
  grid.style.gridTemplateRows = `44px repeat(${lastHour - firstHour}, ${hourHeight}px)`;
  grid.innerHTML = '<div class="grid-corner" aria-hidden="true"></div>';
  dates.forEach((date, index) => {
    grid.insertAdjacentHTML("beforeend", `<div class="day-heading" role="columnheader" style="grid-column:${index + 2};grid-row:1">${dateFormatter.format(date)}</div>`);
  });
  for (let hour = firstHour; hour < lastHour; hour += 1) {
    const row = hour - firstHour + 2;
    const cells = dates.map((_, index) => `<div class="hour-cell" role="gridcell" aria-label="${hour}시" style="grid-column:${index + 2};grid-row:${row}"></div>`).join("");
    grid.insertAdjacentHTML("beforeend", `<div class="hour-label" style="grid-row:${row}">${String(hour).padStart(2, "0")}:00</div>${cells}`);
  }
  dates.forEach((date, index) => {
    const segments = blocks.map((block) => {
      const interval = blockSegmentOnDate(block, date);
      if (!interval) return null;
      const start = Math.max(interval.start, firstHour * minutesPerHour);
      const end = Math.min(interval.end, lastHour * minutesPerHour);
      return start < end ? {
        block, date, start, end,
        actualStart: interval.actualStart, actualEnd: interval.actualEnd,
        fullActualStart: interval.actualStart, fullActualEnd: interval.actualEnd,
      } : null;
    }).filter(Boolean);
    layoutSegments(segments).forEach((segment) => renderBlock(segment, index));
  });
}

function renderGoogleBlockList() {
  const weekDates = createDates(currentWeekStart);
  const googleItems = [...document.querySelectorAll("#google-calendar-panel .block-card")];
  let visibleItems = 0;
  googleItems.forEach((item) => {
    const block = blocks.find((entry) => entry.id === Number(item.dataset.blockId));
    const isInWeek = block && weekDates.some((date) => blockSegmentOnDate(block, date));
    item.hidden = !isInWeek;
    if (isInWeek) visibleItems += 1;
  });
  document.querySelector("#google-week-empty").hidden = visibleItems > 0;
}

function updateWeek() {
  renderCalendar();
  renderGoogleBlockList();
}

showFormButton.addEventListener("click", () => { updateEditorVisibility(true); updateWeekdayFields(); });
showEverytimeImportButton.addEventListener("click", () => {
  everytimeImportForm.hidden = false;
  showEverytimeImportButton.hidden = true;
  showFormButton.hidden = true;
});
document.querySelector("#cancel-everytime-import").addEventListener("click", () => {
  everytimeImportForm.hidden = true;
  updateEditorVisibility(false);
});
cancelEdit.addEventListener("click", resetForm);
cancelEditSecondary.addEventListener("click", resetForm);
document.querySelectorAll('input[name="schedule_type"]').forEach((radio) => radio.addEventListener("change", () => { setScheduleType(radio.value); updateWeekdayFields(); }));
document.querySelectorAll(".source-tab").forEach((tab) => {
  tab.addEventListener("click", () => selectSource(tab.dataset.source));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...document.querySelectorAll(".source-tab")];
    const index = tabs.indexOf(tab);
    const next = event.key === "Home" ? tabs[0] : event.key === "End" ? tabs.at(-1) : tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    selectSource(next.dataset.source, true);
  });
});
document.querySelectorAll(".buffer-settings-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const form = document.querySelector(`#${button.getAttribute("aria-controls")}`);
    const isOpen = !form.hidden;
    form.hidden = isOpen;
    button.setAttribute("aria-expanded", String(!isOpen));
  });
});
document.querySelectorAll(".edit-block").forEach((button) => button.addEventListener("click", () => {
  const block = blocks.find((item) => item.id === Number(button.dataset.blockId));
  sourceInput.value = block.source;
  updateEditorVisibility(true);
  form.action = `/blocks/${block.id}`;
  document.querySelector("#title-input").value = block.title;
  document.querySelector(`input[name="schedule_type"][value="${block.isRecurring ? "recurring" : "one_time"}"]`).checked = true;
  setScheduleType(block.isRecurring ? "recurring" : "one_time");
  updateWeekdayFields();
  document.querySelector("#weekday-input").value = block.weekday ?? 0;
  document.querySelector("#start-time-input").value = block.startTime ?? "";
  document.querySelector("#end-time-input").value = block.endTime ?? "";
  document.querySelector("#starts-at-input").value = block.startsAt ?? "";
  document.querySelector("#ends-at-input").value = block.endsAt ?? "";
  document.querySelector("#before-buffer-input").value = block.beforeBufferMinutes;
  document.querySelector("#after-buffer-input").value = block.afterBufferMinutes;
  heading.textContent = `${titles[block.source]} 수정`;
  document.querySelector("#save-button").textContent = "저장";
  document.querySelector("#title-input").focus();
}));
document.querySelectorAll("[data-confirm]").forEach((button) => button.addEventListener("click", (event) => { if (!window.confirm(button.dataset.confirm)) event.preventDefault(); }));
document.querySelector("#previous-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, -7); updateWeek(); });
document.querySelector("#next-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, 7); updateWeek(); });
document.querySelector("#current-week").addEventListener("click", () => { currentWeekStart = parseDate(dashboard.dataset.weekStart); updateWeek(); });
function updateCalendarHours(changedInput) {
  let selectedStart = Number(calendarStartHourInput.value);
  let selectedEnd = Number(calendarEndHourInput.value);
  if (selectedStart >= selectedEnd) {
    if (changedInput === calendarStartHourInput) {
      selectedEnd = selectedStart + 1;
      calendarEndHourInput.value = String(selectedEnd);
    } else {
      selectedStart = selectedEnd - 1;
      calendarStartHourInput.value = String(selectedStart);
    }
  }
  firstHour = selectedStart;
  lastHour = selectedEnd;
  renderCalendar();
}
calendarStartHourInput.addEventListener("change", () => updateCalendarHours(calendarStartHourInput));
calendarEndHourInput.addEventListener("change", () => updateCalendarHours(calendarEndHourInput));
document.querySelector("#google-previous-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, -7); updateWeek(); });
document.querySelector("#google-next-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, 7); updateWeek(); });
document.querySelector("#google-current-week").addEventListener("click", () => { currentWeekStart = parseDate(dashboard.dataset.weekStart); updateWeek(); });
document.querySelector("#open-bookmarklet-setup").addEventListener("click", () => bookmarkletDialog.showModal());
document.querySelector("#close-bookmarklet-setup").addEventListener("click", () => bookmarkletDialog.close());
bookmarkletDialog.addEventListener("click", (event) => { if (event.target === bookmarkletDialog) bookmarkletDialog.close(); });
bookmarkletDialog.querySelectorAll('form[method="post"]').forEach((submittedForm) => submittedForm.addEventListener("submit", () => {
  try { sessionStorage.setItem(bookmarkletDialogKey, "open"); } catch (_) { /* Setup still completes without browser storage. */ }
}));
bookmarkletDialog.querySelectorAll("[data-revoke-token-id]").forEach((button) => button.addEventListener("click", () => {
  try {
    const storedTokens = JSON.parse(sessionStorage.getItem(recentlyRevokedBookmarkletKey) || "[]");
    const tokenIds = Array.isArray(storedTokens) ? storedTokens : [storedTokens];
    if (!tokenIds.includes(button.dataset.revokeTokenId)) tokenIds.push(button.dataset.revokeTokenId);
    sessionStorage.setItem(recentlyRevokedBookmarkletKey, JSON.stringify(tokenIds));
  } catch (_) { /* The token is still revoked without browser storage. */ }
}));
let recentlyRevokedBookmarklets = [];
try {
  if (sessionStorage.getItem(bookmarkletDialogKey) === "open") {
    sessionStorage.removeItem(bookmarkletDialogKey);
    bookmarkletDialog.showModal();
  }
  const storedTokens = JSON.parse(sessionStorage.getItem(recentlyRevokedBookmarkletKey) || "[]");
  recentlyRevokedBookmarklets = Array.isArray(storedTokens) ? storedTokens : [storedTokens];
} catch (_) { /* The dialog remains available through its header action. */ }
if (recentlyRevokedBookmarklets.length) {
  const activeTokens = document.querySelector("#active-bookmarklet-tokens");
  recentlyRevokedBookmarklets.forEach((tokenId) => {
    const token = document.querySelector(`#revoked-bookmarklet-tokens [data-token-id="${tokenId}"]`);
    if (!token || !activeTokens) return;
    token.classList.add("is-recently-revoked");
    activeTokens.append(token);
  });
  [...activeTokens.children]
    .sort((first, second) => Number(second.dataset.tokenId) - Number(first.dataset.tokenId))
    .forEach((token) => activeTokens.append(token));
  document.querySelector("#active-bookmarklet-section").hidden = !activeTokens.children.length;
}
bookmarkletDialog.addEventListener("close", () => {
  if (!recentlyRevokedBookmarklets.length) return;
  const history = document.querySelector("#revoked-bookmarklet-tokens");
  recentlyRevokedBookmarklets.forEach((tokenId) => {
    const token = document.querySelector(`#active-bookmarklet-tokens [data-token-id="${tokenId}"]`);
    if (token && history) history.append(token);
  });
  if (history) [...history.children]
    .sort((first, second) => Number(second.dataset.tokenId) - Number(first.dataset.tokenId))
    .forEach((token) => history.append(token));
  document.querySelector("#active-bookmarklet-section").hidden = !document.querySelector("#active-bookmarklet-tokens").children.length;
  try { sessionStorage.removeItem(recentlyRevokedBookmarkletKey); } catch (_) { /* No stored state to clear. */ }
  recentlyRevokedBookmarklets = [];
});
document.querySelectorAll(".token-info-toggle").forEach((button) => button.addEventListener("click", () => {
  const details = document.querySelector(`#${button.getAttribute("aria-controls")}`);
  const isOpen = !details.hidden;
  details.hidden = isOpen;
  button.setAttribute("aria-expanded", String(!isOpen));
}));
document.querySelectorAll('form[method="post"]').forEach((submittedForm) => submittedForm.addEventListener("submit", () => {
  if (new URL(submittedForm.action, window.location.href).pathname !== "/auth/logout") saveDashboardState();
}));
const restoredState = readDashboardState();
if (restoredState?.weekStart) currentWeekStart = parseDate(restoredState.weekStart);
if (restoredState?.startHour && restoredState?.endHour) {
  calendarStartHourInput.value = restoredState.startHour;
  calendarEndHourInput.value = restoredState.endHour;
  updateCalendarHours(calendarStartHourInput);
}
if (restoredState?.source) selectSource(restoredState.source);
updateWeek();
if (restoredState) {
  calendarScroll.scrollLeft = Number(restoredState.calendarScrollLeft) || 0;
  requestAnimationFrame(() => window.scrollTo(0, Number(restoredState.pageScrollY) || 0));
}
