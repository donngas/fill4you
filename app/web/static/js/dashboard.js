const blocks = JSON.parse(document.querySelector("#blocks-data").textContent);
const dashboard = document.querySelector(".dashboard");
const form = document.querySelector("#block-form");
const showFormButton = document.querySelector("#show-block-form");
const sourceInput = document.querySelector("#source-input");
const heading = document.querySelector("#form-heading");
const recurringFields = document.querySelector("#recurring-fields");
const oneTimeFields = document.querySelector("#one-time-fields");
const cancelEdit = document.querySelector("#cancel-edit");
const titles = { timetable: "시간표", manual: "직접 추가", google_calendar: "Google Calendar" };

function updateEditorVisibility(showForm) {
  form.hidden = !showForm;
  showFormButton.hidden = showForm || sourceInput.value === "google_calendar";
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
  cancelEdit.hidden = true;
  updateEditorVisibility(false);
}

showFormButton.addEventListener("click", () => updateEditorVisibility(true));

document.querySelectorAll('input[name="schedule_type"]').forEach((radio) => {
  radio.addEventListener("change", () => setScheduleType(radio.value));
});
document.querySelectorAll(".source-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const source = tab.dataset.source;
    sourceInput.value = source;
    document.querySelectorAll(".source-tab").forEach((item) => item.classList.toggle("is-active", item === tab));
    document.querySelectorAll("[data-source-list]").forEach((list) => { list.hidden = list.dataset.sourceList !== source; });
    resetForm();
  });
});
document.querySelectorAll(".edit-block").forEach((button) => {
  button.addEventListener("click", () => {
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
    cancelEdit.hidden = false;
  });
});
cancelEdit.addEventListener("click", resetForm);

const calendarScroll = document.querySelector("#calendar-scroll");
const grid = document.querySelector("#week-grid");
const loadMoreButton = document.querySelector("#load-more-dates");
const collapseTwoWeeksButton = document.querySelector("#collapse-two-weeks");
const collapseAllDatesButton = document.querySelector("#collapse-all-dates");
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
const hourHeight = 56;
const minutesPerHour = 60;
const startHour = 8;
const endHour = 23;
let dates = createDates(dashboard.dataset.weekStart, 14);

function parseDate(dateValue) {
  const [year, month, day] = dateValue.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function createDates(startDate, count) {
  const first = parseDate(startDate);
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(first);
    date.setDate(first.getDate() + index);
    return date;
  });
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

function renderCalendar() {
  grid.style.gridTemplateColumns = `4rem repeat(${dates.length}, 8rem)`;
  grid.style.gridTemplateRows = `2.75rem repeat(${endHour - startHour}, ${hourHeight}px)`;
  grid.innerHTML = '<div class="grid-corner"></div>';
  dates.forEach((date, index) => {
    const label = `${date.getMonth() + 1}/${date.getDate()} (${weekdays[date.getDay()]})`;
    grid.insertAdjacentHTML("beforeend", `<div class="day-heading" style="grid-column:${index + 2};grid-row:1">${label}</div>`);
  });
  for (let hour = startHour; hour < endHour; hour += 1) {
    const row = hour - startHour + 2;
    const cells = dates.map((_, index) => `<div class="hour-cell" style="grid-column:${index + 2};grid-row:${row}"></div>`).join("");
    grid.insertAdjacentHTML("beforeend", `<div class="hour-label" style="grid-row:${row}">${String(hour).padStart(2, "0")}:00</div>${cells}`);
  }
  dates.forEach((date, index) => {
    blocks.forEach((block) => {
      const segment = blockSegmentOnDate(block, date);
      if (segment) renderBlock(block, index, segment);
    });
  });
  const canCollapse = dates.length > 14;
  collapseTwoWeeksButton.disabled = !canCollapse;
  collapseAllDatesButton.disabled = !canCollapse;
}

function renderBlock(block, dayIndex, segment) {
  const visibleStart = startHour * minutesPerHour;
  const visibleEnd = endHour * minutesPerHour;
  const start = Math.max(segment.start, visibleStart);
  const end = Math.min(segment.end, visibleEnd);
  if (start >= end) return;
  const item = document.createElement("div");
  item.className = `preview-block source-${block.source}`;
  item.style.left = `calc(4rem + ${dayIndex} * 8rem + .25rem)`;
  item.style.top = `calc(2.75rem + ${(start - visibleStart) * (hourHeight / minutesPerHour)}px)`;
  item.style.height = `${(end - start) * (hourHeight / minutesPerHour)}px`;
  item.textContent = block.title;
  grid.append(item);
}

loadMoreButton.addEventListener("click", () => {
  const previousScrollLeft = calendarScroll.scrollLeft;
  const nextDate = new Date(dates.at(-1));
  nextDate.setDate(nextDate.getDate() + 1);
  dates = dates.concat(createDates(formatDate(nextDate), 14));
  renderCalendar();
  calendarScroll.scrollLeft = previousScrollLeft;
});

collapseTwoWeeksButton.addEventListener("click", () => {
  if (dates.length <= 14) return;
  dates = dates.slice(0, -14);
  renderCalendar();
});

collapseAllDatesButton.addEventListener("click", () => {
  dates = dates.slice(0, 14);
  renderCalendar();
});

renderCalendar();
