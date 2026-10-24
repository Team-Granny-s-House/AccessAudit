// SkyRail demo site: broken copy (deliberately inaccessible). Fictional data; nothing can be booked.
const TRAINS = {
  "2101": { name: "SkyRail Swift 2101", depart: "06:10", arrive: "14:25", fare: "₹1,845" },
  "2207": { name: "SkyRail Night Rider 2207", depart: "16:40", arrive: "08:05 +1", fare: "₹2,310" },
  "2315": { name: "SkyRail Coastal 2315", depart: "21:15", arrive: "11:50 +1", fare: "₹1,560" },
};

// Results: filter button
const filterBtn = document.getElementById("filter-btn");
const filterNote = document.getElementById("filter-note");
if (filterBtn && filterNote) {
  filterBtn.addEventListener("click", () => {
    const open = filterBtn.getAttribute("aria-expanded") === "true";
    filterBtn.setAttribute("aria-expanded", String(!open));
    filterNote.hidden = open;
  });
}

const chips = Array.from(document.querySelectorAll(".date-chip"));
const dateLabel = document.getElementById("date-label");
function pickDate(chip) {
  chips.forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
  if (dateLabel) dateLabel.textContent = chip.textContent;
}
// Results: date strip. BARRIER: Tab and Shift+Tab are caught and cycle focus
// between the chips, so a keyboard user can never leave the strip.
chips.forEach((chip, i) => {
  chip.addEventListener("click", () => pickDate(chip));
  chip.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const next = e.shiftKey ? (i - 1 + chips.length) % chips.length : (i + 1) % chips.length;
    chips[next].focus();
  });
});

// Results: Select goes to the review page
document.querySelectorAll(".select-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const picked = chips.find((c) => c.getAttribute("aria-pressed") === "true");
    const params = new URLSearchParams({ train: btn.dataset.train, date: picked ? picked.textContent : "" });
    location.href = "review.html?" + params;
  });
});

// Review: show the chosen train
const summary = document.getElementById("trip-summary");
if (summary) {
  const params = new URLSearchParams(location.search);
  const train = TRAINS[params.get("train")] || TRAINS["2101"];
  for (const key of Object.keys(train)) {
    const cell = summary.querySelector(`[data-field="${key}"]`);
    if (cell) cell.textContent = train[key];
  }
  const date = summary.querySelector('[data-field="date"]');
  if (date && params.get("date")) date.textContent = params.get("date");
}

// Review: Pay now never books anything
const payBtn = document.getElementById("pay-btn");
const payStatus = document.getElementById("pay-status");
if (payBtn && payStatus) {
  payBtn.addEventListener("click", () => { payStatus.textContent = "Demo only, nothing was booked"; });
}
