const blocks = JSON.parse(document.querySelector("#blocks-data").textContent);
const dashboard = document.querySelector(".dashboard");
const form = document.querySelector("#block-form");
const showFormButton = document.querySelector("#show-block-form");
const sourceInput = document.querySelector("#source-input");
const heading = document.querySelector("#form-heading");
const recurringFields = document.querySelector("#recurring-fields");
const oneTimeFields = document.querySelector("#one-time-fields");
const cancelEdit = document.querySelector("#cancel-edit");
const cancelEditSecondary = document.querySelector("#cancel-edit-secondary");
const titles = { timetable: "시간표", manual: "일정", google_calendar: "구글 캘린더" };
const grid = document.querySelector("#week-grid");
const weekLabel = document.querySelector("#week-label");
const calendarDescription = document.querySelector("#calendar-description");
const hourHeight = 44;
const minutesPerHour = 60;
const firstHour = 0;
const lastHour = 24;
let currentWeekStart = parseDate(dashboard.dataset.weekStart);
let highlightedBlockTimer;

function updateEditorVisibility(showForm) {
  form.hidden = !showForm;
  showFormButton.hidden = showForm || sourceInput.value !== "timetable" && sourceInput.value !== "manual";
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
  heading.textContent = `${titles[selectedSource]} 추가`;
  showFormButton.textContent = `${titles[selectedSource]} 추가`;
  document.querySelector("#save-button").textContent = "추가";
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
  if (block.isRecurring) {
    if (block.weekday !== (date.getDay() + 6) % 7) return null;
    return { start: minutesFromTime(block.startTime), end: minutesFromTime(block.endTime) };
  }
  const dateValue = formatDate(date);
  const startDate = block.startsAt.slice(0, 10);
  const endDate = block.endsAt.slice(0, 10);
  if (dateValue < startDate || dateValue > endDate) return null;
  const start = dateValue === startDate ? minutesFromTime(block.startsAt.slice(11)) : 0;
  const end = dateValue === endDate ? minutesFromTime(block.endsAt.slice(11)) : 24 * minutesPerHour;
  return start < end ? { start, end } : null;
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
  const starts = `${String(Math.floor(segment.start / 60)).padStart(2, "0")}:${String(segment.start % 60).padStart(2, "0")}`;
  const ends = `${String(Math.floor(segment.end / 60)).padStart(2, "0")}:${String(segment.end % 60).padStart(2, "0")}`;
  return `${block.title}, ${sourceLabel(block.source)}, ${dateText} ${starts}–${ends}`;
}

function renderBlock(segment, dayIndex) {
  const { block, date, start, end, column, columns } = segment;
  const item = document.createElement("button");
  item.type = "button";
  item.className = `preview-block source-${block.source}`;
  item.textContent = block.title;
  item.setAttribute("aria-label", describeBlock(block, date, segment));
  item.style.left = `calc(4rem + ${dayIndex} * ((100% - 4rem) / 7) + ${column} * ((100% - 4rem) / 7 / ${columns}) + 3px)`;
  item.style.width = `calc((100% - 4rem) / 7 / ${columns} - 6px)`;
  item.style.top = `calc(44px + ${start * (hourHeight / minutesPerHour)}px + 2px)`;
  item.style.height = `${Math.max((end - start) * (hourHeight / minutesPerHour) - 4, 24)}px`;
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
  weekLabel.textContent = `${rangeFormatter.format(dates[0])} – ${rangeFormatter.format(dates[6])}`;
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
      return interval ? { block, date, ...interval } : null;
    }).filter(Boolean);
    layoutSegments(segments).forEach((segment) => renderBlock(segment, index));
  });
}

showFormButton.addEventListener("click", () => updateEditorVisibility(true));
cancelEdit.addEventListener("click", resetForm);
cancelEditSecondary.addEventListener("click", resetForm);
document.querySelectorAll('input[name="schedule_type"]').forEach((radio) => radio.addEventListener("change", () => setScheduleType(radio.value)));
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
document.querySelectorAll(".edit-block").forEach((button) => button.addEventListener("click", () => {
  const block = blocks.find((item) => item.id === Number(button.dataset.blockId));
  sourceInput.value = block.source;
  updateEditorVisibility(true);
  form.action = `/blocks/${block.id}`;
  document.querySelector("#title-input").value = block.title;
  document.querySelector(`input[name="schedule_type"][value="${block.isRecurring ? "recurring" : "one_time"}"]`).checked = true;
  setScheduleType(block.isRecurring ? "recurring" : "one_time");
  document.querySelector("#weekday-input").value = block.weekday ?? 0;
  document.querySelector("#start-time-input").value = block.startTime ?? "";
  document.querySelector("#end-time-input").value = block.endTime ?? "";
  document.querySelector("#starts-at-input").value = block.startsAt ?? "";
  document.querySelector("#ends-at-input").value = block.endsAt ?? "";
  heading.textContent = `${titles[block.source]} 수정`;
  document.querySelector("#save-button").textContent = "저장";
  document.querySelector("#title-input").focus();
}));
document.querySelectorAll("[data-confirm]").forEach((button) => button.addEventListener("click", (event) => { if (!window.confirm(button.dataset.confirm)) event.preventDefault(); }));
document.querySelector("#previous-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, -7); renderCalendar(); });
document.querySelector("#next-week").addEventListener("click", () => { currentWeekStart = addDays(currentWeekStart, 7); renderCalendar(); });
document.querySelector("#current-week").addEventListener("click", () => { currentWeekStart = parseDate(dashboard.dataset.weekStart); renderCalendar(); });
renderCalendar();
