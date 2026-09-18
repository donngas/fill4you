const blocks = JSON.parse(document.querySelector("#blocks-data").textContent);
const dashboard = document.querySelector(".dashboard");
const form = document.querySelector("#block-form");
const sourceInput = document.querySelector("#source-input");
const heading = document.querySelector("#form-heading");
const recurringFields = document.querySelector("#recurring-fields");
const oneTimeFields = document.querySelector("#one-time-fields");
const cancelEdit = document.querySelector("#cancel-edit");
const titles = { timetable: "시간표", manual: "직접 추가", google_calendar: "Google Calendar" };

function setScheduleType(type) {
  const recurring = type === "recurring";
  recurringFields.hidden = !recurring;
  oneTimeFields.hidden = recurring;
  recurringFields.querySelectorAll("input, select").forEach((input) => { input.required = recurring; });
  oneTimeFields.querySelectorAll("input").forEach((input) => { input.required = !recurring; });
}

function resetForm() {
  form.action = "/blocks";
  form.reset();
  document.querySelector('input[name="schedule_type"][value="recurring"]').checked = true;
  setScheduleType("recurring");
  heading.textContent = `${titles[sourceInput.value]} 추가`;
  document.querySelector("#save-button").textContent = "추가";
  cancelEdit.hidden = true;
}

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
    form.hidden = source === "google_calendar";
  });
});
document.querySelectorAll(".edit-block").forEach((button) => {
  button.addEventListener("click", () => {
    const block = blocks.find((item) => item.id === Number(button.dataset.blockId));
    sourceInput.value = block.source;
    form.hidden = false;
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

function blockOccursOnDate(block, date) {
  if (block.isRecurring) return block.weekday === (date.getDay() + 6) % 7;
  return block.startsAt.slice(0, 10) === formatDate(date);
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
    blocks.filter((block) => blockOccursOnDate(block, date)).forEach((block) => renderBlock(block, index));
  });
}

function renderBlock(block, dayIndex) {
  const [startHourValue, startMinute] = block.startTime.split(":").map(Number);
  const [endHourValue, endMinute] = block.endTime.split(":").map(Number);
  const start = (startHourValue - startHour) * minutesPerHour + startMinute;
  const duration = (endHourValue * minutesPerHour + endMinute) - (startHourValue * minutesPerHour + startMinute);
  if (start < 0 || start >= (endHour - startHour) * minutesPerHour || duration <= 0) return;
  const item = document.createElement("div");
  item.className = `preview-block source-${block.source}`;
  item.style.left = `calc(4rem + ${dayIndex} * 8rem + .25rem)`;
  item.style.top = `calc(2.75rem + ${start * (hourHeight / minutesPerHour)}px)`;
  item.style.height = `${Math.min(duration, (endHour - startHour) * minutesPerHour - start) * (hourHeight / minutesPerHour)}px`;
  item.textContent = block.title;
  grid.append(item);
}

loadMoreButton.addEventListener("click", () => {
  const nextDate = new Date(dates.at(-1));
  nextDate.setDate(nextDate.getDate() + 1);
  dates = dates.concat(createDates(formatDate(nextDate), 14));
  renderCalendar();
  calendarScroll.scrollLeft = calendarScroll.scrollWidth;
});

renderCalendar();
