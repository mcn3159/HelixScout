"use strict";

const state = {
  data: null,
  kind: "all",
  source: "all",
  sort: "score",
  query: "",
  view: "all",
  hideDemos: false,
  draftPenalties: [],
  draftMinScore: 0,
  feedbackId: null,
  pollTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[character]));
}

function safeURL(value = "") {
  if (!String(value).trim()) return "#";
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch (_) {
    return "#";
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* handled below */ }
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

async function loadDashboard({ quiet = false } = {}) {
  try {
    state.data = await api("/api/dashboard");
    renderAll();
    const running = state.data.latest_scan?.status === "running";
    setScanning(running);
    if (running) schedulePoll();
  } catch (error) {
    if (!quiet) showToast(error.message, true);
  }
}

function renderAll() {
  if (!state.data) return;
  renderSources();
  renderMetrics();
  renderCards();
  renderDemoNotice();
  $("#savedNavCount").textContent = state.data.stats.saved || 0;
}

function renderSources() {
  const errorMap = new Map((state.data.latest_scan?.errors || []).map(error => [error.source, error.message]));
  const errors = new Set(errorMap.keys());
  const scanTime = state.data.latest_scan?.finished_at || state.data.latest_scan?.started_at;
  const active = state.data.sources.filter(source => source.configured).length;
  $("#sourceCount").textContent = `${active}/3`;
  $("#sourceList").innerHTML = state.data.sources.map(source => {
    const healthy = source.configured && !errors.has(source.source);
    const label = source.source === "x" ? "X / Twitter" : titleCase(source.source);
    const status = errors.has(source.source) ? `error · ${relativeDate(scanTime)}` : (source.configured ? "ready" : "setup");
    const note = errorMap.get(source.source) ? `${source.note} · Error from scan ${formatTimestamp(scanTime)}: ${errorMap.get(source.source)}` : source.note;
    return `<div class="source-row" title="${escapeHTML(note)}"><i class="${healthy ? "online" : ""}"></i><span>${escapeHTML(label)}</span><small>${status}</small></div>`;
  }).join("");
}

function renderMetrics() {
  const visibleBase = state.data.opportunities.filter(item => !state.hideDemos || !item.is_demo);
  const newItems = visibleBase.filter(item => item.status === "new").length;
  const strong = visibleBase.filter(item => item.status !== "dismissed" && item.score >= 60).length;
  const events = visibleBase.filter(item => item.status !== "dismissed" && item.kind === "event").length;
  const saved = visibleBase.filter(item => item.status === "saved").length;
  $("#newMetric").textContent = newItems;
  $("#matchMetric").textContent = strong;
  $("#eventMetric").textContent = events;
  $("#savedMetric").textContent = saved;
}

function filteredItems() {
  const minimum = Number(state.data.preferences.min_score || 0);
  let items = state.data.opportunities.filter(item => {
    if (item.status === "dismissed") return false;
    if (state.view === "saved" && item.status !== "saved") return false;
    if (state.kind !== "all" && item.kind !== state.kind) return false;
    if (state.source !== "all" && item.source !== state.source) return false;
    if (state.hideDemos && item.is_demo) return false;
    if (item.score < minimum) return false;
    if (state.query) {
      const haystack = `${item.title} ${item.organization} ${item.description} ${item.location} ${(item.topics || []).join(" ")}`.toLowerCase();
      if (!haystack.includes(state.query.toLowerCase())) return false;
    }
    return true;
  });
  items.sort((a, b) => state.sort === "newest"
    ? new Date(b.posted_at) - new Date(a.posted_at)
    : b.score - a.score || new Date(b.posted_at) - new Date(a.posted_at));
  return items;
}

function renderCards() {
  const items = filteredItems();
  $("#resultSummary").textContent = `${items.length} ${items.length === 1 ? "signal" : "signals"} · ranked by fit`;
  $("#cards").innerHTML = items.map(cardTemplate).join("");
  $("#emptyState").classList.toggle("hidden", items.length > 0);
}

function cardTemplate(item) {
  const scoreColor = item.score >= 65 ? "var(--mint)" : item.score >= 40 ? "var(--gold)" : "#b5aaa1";
  const sourceLabel = item.source === "x" ? "X / Twitter" : titleCase(item.source);
  const org = item.organization || item.author || "Independent post";
  const where = item.location ? `<span>${escapeHTML(item.location)}</span>` : "";
  const tags = (item.topics || []).slice(0, 4).map(topic => `<span class="tag">${escapeHTML(topic)}</span>`);
  const penaltyReasons = (item.score_reasons || []).filter(reason => reason.points < 0);
  tags.push(...penaltyReasons.slice(0, 2).map(reason => `<span class="tag penalty">− ${escapeHTML(reason.label)}</span>`));
  const reasons = (item.score_reasons || []).map(reason => `<span class="reason-chip ${reason.points < 0 ? "negative" : ""}">${reason.points > 0 ? "+" : ""}${reason.points} ${escapeHTML(reason.label)}</span>`).join("");
  const sourceClass = ["linkedin", "x", "bluesky", "import"].includes(item.source) ? item.source : "import";
  const link = safeURL(item.url);
  return `
    <article class="opportunity-card" data-id="${item.id}">
      <div class="score-panel">
        <div class="score-ring" style="--score:${item.score};--ring:${scoreColor}"><strong>${item.score}</strong></div>
        <span>Match</span>
      </div>
      <div class="card-content">
        <div class="card-meta">
          <span class="source-badge source-${sourceClass}">${escapeHTML(sourceLabel)}</span>
          <span class="kind-badge">${escapeHTML(item.kind)}</span>
          ${item.is_demo ? '<span class="demo-badge">Demo</span>' : ""}
          <span class="meta-date">${relativeDate(item.posted_at)}</span>
        </div>
        <h3>${escapeHTML(item.title)}</h3>
        <p class="org-line">${escapeHTML(org)}${where}</p>
        <p class="description">${escapeHTML(item.description || "Open the original post for details.")}</p>
        <div class="tags">${tags.join("")}</div>
      </div>
      <div class="card-actions">
        <button class="save-button ${item.status === "saved" ? "saved" : ""}" data-action="save" aria-label="${item.status === "saved" ? "Remove from saved" : "Save opportunity"}"><svg><use href="#i-bookmark"></use></svg>${item.status === "saved" ? "Saved" : "Save"}</button>
        ${link !== "#" ? `<a href="${escapeHTML(link)}" target="_blank" rel="noopener noreferrer"><svg><use href="#i-external"></use></svg>Open</a>` : ""}
        <button class="not-for-me" data-action="feedback">Not for me</button>
      </div>
      ${reasons ? `<details class="reason-details"><summary>Why this score</summary><div class="reason-grid">${reasons}</div></details>` : ""}
    </article>`;
}

function renderDemoNotice() {
  const hasDemo = state.data.opportunities.some(item => item.is_demo);
  $("#demoNotice").classList.toggle("hidden", !hasDemo || state.hideDemos);
}

function titleCase(value) {
  return String(value || "").replace(/\b\w/g, letter => letter.toUpperCase());
}

function relativeDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 14) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "at an unknown time";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

async function changeStatus(id, status) {
  try {
    const payload = await api(`/api/opportunities/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
    const index = state.data.opportunities.findIndex(item => item.id === id);
    if (index >= 0) state.data.opportunities[index] = payload.opportunity;
    state.data.stats = payload.stats;
    renderAll();
  } catch (error) { showToast(error.message, true); }
}

async function runScan() {
  setScanning(true);
  try {
    await api("/api/scan", { method: "POST", body: "{}" });
    showToast("Scan started — each source will report independently");
    schedulePoll(true);
  } catch (error) {
    setScanning(false);
    showToast(error.message, true);
  }
}

function setScanning(isScanning) {
  const button = $("#scanButton");
  button.classList.toggle("scanning", isScanning);
  button.disabled = isScanning;
  button.querySelector("span").textContent = isScanning ? "Scanning…" : "Run scan";
}

function schedulePoll(immediate = false) {
  clearTimeout(state.pollTimer);
  state.pollTimer = setTimeout(async () => {
    const previous = state.data?.latest_scan?.id;
    await loadDashboard({ quiet: true });
    const latest = state.data?.latest_scan;
    if (latest?.status === "running") {
      schedulePoll();
    } else {
      setScanning(false);
      if (latest && latest.id !== previous) {
        const total = Object.values(latest.totals || {}).reduce((sum, count) => sum + count, 0);
        showToast(latest.errors?.length ? `Scan finished with ${total} results and ${latest.errors.length} source issue(s)` : `Scan complete — ${total} results processed`);
      }
    }
  }, immediate ? 150 : 1800);
}

function openPreferences() {
  state.draftPenalties = structuredClone(state.data.preferences.penalties || []);
  state.draftMinScore = Number(state.data.preferences.min_score || 0);
  renderPreferences();
  $("#preferenceDrawer").classList.add("open");
  $("#preferenceDrawer").setAttribute("aria-hidden", "false");
  $("#overlay").classList.add("open");
  document.body.style.overflow = "hidden";
}

function closePreferences() {
  $("#preferenceDrawer").classList.remove("open");
  $("#preferenceDrawer").setAttribute("aria-hidden", "true");
  if (!$(".sidebar").classList.contains("open")) $("#overlay").classList.remove("open");
  document.body.style.overflow = "";
}

function renderPreferences() {
  $("#scoreFloor").value = state.draftMinScore;
  $("#scoreFloorValue").textContent = state.draftMinScore;
  const active = new Set(state.draftPenalties.map(item => item.phrase));
  $("#suggestions").innerHTML = (state.data.preferences.suggestions || []).filter(item => !active.has(item)).map(item => `<button data-suggestion="${escapeHTML(item)}">+ ${escapeHTML(item)}</button>`).join("");
  $("#penaltyList").innerHTML = state.draftPenalties.length
    ? state.draftPenalties.map((item, index) => `<div class="penalty-item"><strong>${escapeHTML(item.phrase)}</strong><span>−${item.weight}</span><button data-remove-penalty="${index}" aria-label="Remove ${escapeHTML(item.phrase)}"><svg><use href="#i-x"></use></svg></button></div>`).join("")
    : `<p style="margin:3px 0;color:#929b97;font-size:10px">No active penalties. Your results are ranked only by positive fit.</p>`;
}

function addDraftPenalty(phrase, weight = 15) {
  phrase = String(phrase || "").trim().toLowerCase().replace(/\s+/g, " ");
  if (!phrase) return;
  const existing = state.draftPenalties.find(item => item.phrase === phrase);
  if (existing) existing.weight = Number(weight);
  else state.draftPenalties.push({ phrase, weight: Number(weight) });
  $("#penaltyPhrase").value = "";
  renderPreferences();
}

async function savePreferences() {
  const button = $("#savePreferences");
  button.disabled = true;
  try {
    const payload = await api("/api/preferences", {
      method: "PUT",
      body: JSON.stringify({ penalties: state.draftPenalties, min_score: state.draftMinScore }),
    });
    state.data = payload.dashboard;
    closePreferences();
    renderAll();
    showToast("Preferences saved — every opportunity was rescored");
  } catch (error) { showToast(error.message, true); }
  finally { button.disabled = false; }
}

function openFeedback(id) {
  state.feedbackId = id;
  const item = state.data.opportunities.find(opportunity => opportunity.id === id);
  const text = `${item.title} ${item.description}`.toLowerCase();
  const candidates = ["internship", "postdoc", "unpaid", "sales", "remote only", "director", "academic", "senior"];
  const matches = candidates.filter(candidate => text.includes(candidate));
  const stop = new Set(["scientist", "science", "biology", "computational", "senior", "applications", "open", "with", "from", "this", "that"]);
  const titleTerms = item.title.toLowerCase().match(/[a-z][a-z-]{4,}/g) || [];
  const options = [...new Set([...matches, ...titleTerms.filter(term => !stop.has(term)).slice(0, 3)])].slice(0, 5);
  $("#feedbackOptions").innerHTML = options.map(option => `<button data-feedback-phrase="${escapeHTML(option)}">Lower “${escapeHTML(option)}”</button>`).join("");
  $("#customFeedback").value = "";
  $("#feedbackModal").classList.add("open");
  $("#feedbackModal").setAttribute("aria-hidden", "false");
}

function closeFeedback() {
  $("#feedbackModal").classList.remove("open");
  $("#feedbackModal").setAttribute("aria-hidden", "true");
  state.feedbackId = null;
}

async function penalizeAndDismiss(phrase) {
  phrase = String(phrase || "").trim().toLowerCase();
  if (!phrase || !state.feedbackId) return;
  const penalties = structuredClone(state.data.preferences.penalties || []);
  const existing = penalties.find(item => item.phrase === phrase);
  if (existing) existing.weight = Math.max(existing.weight, 20);
  else penalties.push({ phrase, weight: 20 });
  const id = state.feedbackId;
  closeFeedback();
  try {
    await api(`/api/opportunities/${id}`, { method: "PATCH", body: JSON.stringify({ status: "dismissed" }) });
    const payload = await api("/api/preferences", { method: "PUT", body: JSON.stringify({ penalties, min_score: state.data.preferences.min_score || 0 }) });
    state.data = payload.dashboard;
    renderAll();
    showToast(`“${phrase}” now ranks lower`);
  } catch (error) { showToast(error.message, true); }
}

async function importFile(file) {
  if (!file) return;
  const format = file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
  try {
    const content = await file.text();
    const payload = await api("/api/import", { method: "POST", body: JSON.stringify({ format, content }) });
    state.data = payload.dashboard;
    closePreferences();
    renderAll();
    showToast(`${payload.imported} opportunities imported and scored`);
  } catch (error) { showToast(error.message, true); }
  $("#importFile").value = "";
}

let toastTimeout;
function showToast(message, error = false) {
  const toast = $("#toast");
  toast.querySelector("p").textContent = message;
  toast.querySelector("span").style.background = error ? "#f0a08f" : "#9ed1c0";
  toast.classList.add("show");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove("show"), 3600);
}

function resetFilters() {
  state.kind = "all"; state.source = "all"; state.query = ""; state.view = "all";
  $("#searchInput").value = ""; $("#sourceFilter").value = "all";
  $$(".tabs button").forEach(button => button.classList.toggle("active", button.dataset.kind === "all"));
  $$(".nav-item[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === "all"));
  renderCards();
}

function bindEvents() {
  $("#scanButton").addEventListener("click", runScan);
  $("#searchInput").addEventListener("input", event => { state.query = event.target.value.trim(); renderCards(); });
  $("#sourceFilter").addEventListener("change", event => { state.source = event.target.value; renderCards(); });
  $("#sortFilter").addEventListener("change", event => { state.sort = event.target.value; renderCards(); });
  $$(".tabs button").forEach(button => button.addEventListener("click", () => {
    state.kind = button.dataset.kind;
    $$(".tabs button").forEach(item => item.classList.toggle("active", item === button));
    renderCards();
  }));
  $$(".nav-item[data-view]").forEach(button => button.addEventListener("click", () => {
    state.view = button.dataset.view;
    $$(".nav-item[data-view]").forEach(item => item.classList.toggle("active", item === button));
    renderCards();
    $(".sidebar").classList.remove("open"); $("#overlay").classList.remove("open");
  }));
  $("#cards").addEventListener("click", event => {
    const action = event.target.closest("[data-action]");
    if (!action) return;
    const card = action.closest("[data-id]");
    const id = Number(card.dataset.id);
    const item = state.data.opportunities.find(opportunity => opportunity.id === id);
    if (action.dataset.action === "save") changeStatus(id, item.status === "saved" ? "new" : "saved");
    if (action.dataset.action === "feedback") openFeedback(id);
  });
  [$("#navPreferences"), $("#quickPreferences")].forEach(button => button.addEventListener("click", openPreferences));
  [$("#closeDrawer"), $("#cancelPreferences")].forEach(button => button.addEventListener("click", closePreferences));
  $("#overlay").addEventListener("click", () => { closePreferences(); $(".sidebar").classList.remove("open"); $("#overlay").classList.remove("open"); });
  $("#addPenalty").addEventListener("click", () => addDraftPenalty($("#penaltyPhrase").value, $("#penaltyWeight").value));
  $("#penaltyPhrase").addEventListener("keydown", event => { if (event.key === "Enter") addDraftPenalty(event.target.value, $("#penaltyWeight").value); });
  $("#suggestions").addEventListener("click", event => { const button = event.target.closest("[data-suggestion]"); if (button) addDraftPenalty(button.dataset.suggestion, 15); });
  $("#penaltyList").addEventListener("click", event => { const button = event.target.closest("[data-remove-penalty]"); if (button) { state.draftPenalties.splice(Number(button.dataset.removePenalty), 1); renderPreferences(); } });
  $("#scoreFloor").addEventListener("input", event => { state.draftMinScore = Number(event.target.value); $("#scoreFloorValue").textContent = state.draftMinScore; });
  $("#savePreferences").addEventListener("click", savePreferences);
  $("#importButton").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", event => importFile(event.target.files[0]));
  [$("#closeFeedback")].forEach(button => button.addEventListener("click", closeFeedback));
  $("#feedbackModal").addEventListener("click", event => { if (event.target === $("#feedbackModal")) closeFeedback(); });
  $("#feedbackOptions").addEventListener("click", event => { const button = event.target.closest("[data-feedback-phrase]"); if (button) penalizeAndDismiss(button.dataset.feedbackPhrase); });
  $("#penalizeCustom").addEventListener("click", () => penalizeAndDismiss($("#customFeedback").value));
  $("#dismissOnly").addEventListener("click", async () => { const id = state.feedbackId; closeFeedback(); if (id) { await changeStatus(id, "dismissed"); showToast("Opportunity dismissed"); } });
  $("#hideDemos").addEventListener("click", () => { state.hideDemos = true; renderAll(); });
  $("#emptyReset").addEventListener("click", resetFilters);
  $("#mobileMenu").addEventListener("click", () => { $(".sidebar").classList.add("open"); $("#overlay").classList.add("open"); });
  document.addEventListener("keydown", event => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) { event.preventDefault(); $("#searchInput").focus(); }
    if (event.key === "Escape") { closePreferences(); closeFeedback(); $(".sidebar").classList.remove("open"); }
  });
}

bindEvents();
loadDashboard();
