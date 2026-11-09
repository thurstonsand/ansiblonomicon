import { decide, destination, quickAnswerUrl, RESULT_LIMIT, resultsUrl, route, search } from "./lucky.js";
import { chip, fill, hostOf, matches, normalize, placeholders, queryValues } from "./notes.js";
import { activeNotes, average, hostHistory, open, PB_MIN_RUNS, searchesFor, totals } from "./stats.js";
import { resultTags } from "./tags.js";

const LINGER_MS = 3000;
const SCALE_MIN_MS = 2000;

const { lucky, via, query } = route(new URLSearchParams(location.search).get("q") ?? "");
const at = Date.now();
const hour = new Date(at).getHours();
const controller = new AbortController();
const $ = (selector) => document.querySelector(selector);
const seconds = (ms) => (ms / 1000).toFixed(2);

// Times are milliseconds since the page opened, so the kagi split plus the decision is the total.
const log = {
  at,
  key: normalize(query),
  query,
  via,
  results: [],
  answer: null,
  pick: null,
  pickHost: null,
  rank: null,
  confidence: null,
  outcome: null,
  target: null,
  searchMs: null,
  decisionMs: null,
  pb: false,
  notesShown: [],
  tagsShown: [],
  regret: false,
  notesRuns: [],
  error: null,
};
let left = false;
// The race bar's average and scale, known once the totals load.
let race = { average: null, scale: SCALE_MIN_MS };

document.title = query;
$("#query").textContent = query;
$("#race .scale").textContent = `${seconds(race.scale)}s`;

function leave(outcome, target) {
  if (left) return;
  left = true;
  controller.abort();
  chrome.runtime.sendMessage({ type: "searched", search: { ...log, outcome, target } });
  location.replace(target);
}

addEventListener("keydown", (event) => {
  if (event.key === "Escape") leave("escaped", resultsUrl(query));
});

// Long queries shrink until they fit beside the magnifier.
function fitQuery() {
  const element = $("#query");
  let size = 104;
  while (element.scrollWidth > element.clientWidth && size > 40) {
    size -= 8;
    element.style.fontSize = `${size}px`;
  }
}

const position = (ms) => `${Math.min(100, (ms / race.scale) * 100)}%`;

function tick() {
  if (left || log.error) return;
  const elapsed = performance.now();
  const behind = race.average !== null && elapsed > race.average;
  document.body.classList.toggle("behind-pace", behind);
  $("#race .a").style.width = position(behind ? race.average : elapsed);
  $("#race .b").style.left = position(race.average ?? 0);
  $("#race .b").style.width = behind ? position(elapsed - race.average) : "0";
  $("#race .head").style.left = position(elapsed);
  const delta = $("#race .delta");
  delta.style.left = position(elapsed);
  delta.style.translate = elapsed / race.scale > 0.85 ? "-100% 0" : "";
  delta.textContent = behind ? `+${seconds(elapsed - race.average)} behind pace` : "";
  const [whole, fraction] = seconds(elapsed).split(".");
  $("#clock").innerHTML = `${whole}<small><i>.</i>${fraction}</small>`;
  requestAnimationFrame(tick);
}

function pace(ms, stat) {
  if (!stat) return "";
  if (stat.n >= PB_MIN_RUNS && ms < stat.best) return "gold";
  return ms < average(stat) ? "ahead" : "behind";
}

function showRace(current) {
  if (!current.total) return;
  race = { average: average(current.total), scale: SCALE_MIN_MS };
  const furthest = Math.max(race.average, current.last.totalMs) * 1.25;
  race.scale = Math.max(SCALE_MIN_MS, Math.ceil(furthest / 500) * 500);
  $("#race .scale").textContent = `${seconds(race.scale)}s`;
  $("#race .avg").textContent = `avg ${seconds(race.average)}`;
  $("#race .avg").style.left = position(race.average);
  $("#race .last").textContent = `last ${seconds(current.last.totalMs)}${current.last.pb ? " · PB" : ""}`;
  $("#race .last").style.left = position(current.last.totalMs);
}

async function recall() {
  const db = await open();
  const [current, earlier, notes] = await Promise.all([
    totals(db),
    searchesFor(db, log.key),
    activeNotes(db, at),
  ]);
  showRace(current);
  // Newest first, so a fresh note outranks an older one about the same query.
  const matching = notes.filter((note) => matches(note, log.key, hour)).reverse();
  return { current, earlier, values: queryValues(earlier, at), notes: matching };
}

async function showDeja({ values, notes }) {
  for (const note of notes) {
    const visits =
      placeholders(note.message).includes("visits") && values.last_host
        ? (await hostHistory(values.last_host)).visits
        : null;
    const line = fill(note.message, { ...values, visits });
    if (line) {
      const label = document.createElement("span");
      label.className = "chip rb";
      label.textContent = chip(note.reasons);
      $("#note").append(label, line);
      log.notesShown.push(note.id);
      return;
    }
  }
}

function showPending() {
  for (let index = 0; index < RESULT_LIMIT; index++) {
    const item = document.createElement("li");
    item.className = "pending";
    item.style.setProperty("--w", `${140 + ((index * 97) % 220)}px`);
    const number = document.createElement("span");
    number.className = "n";
    number.textContent = String(index + 1).padStart(2, "0");
    item.append(number);
    $("#results").append(item);
  }
}

function showResults(results) {
  const rows = [...$("#results").children];
  rows.slice(results.length).forEach((row) => row.remove());
  results.forEach((result, index) => {
    const host = hostOf(result.url);
    const item = rows[index];
    item.className = "filled";
    item.dataset.host = host;
    item.style.animationDelay = `${index * 25}ms`;
    const icon = document.createElement("img");
    icon.alt = "";
    icon.src = chrome.runtime.getURL(`/_favicon/?pageUrl=${encodeURIComponent(result.url)}&size=32`);
    const link = document.createElement("a");
    link.href = result.url;
    link.textContent = result.title;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      if (!document.body.classList.contains("lingering")) return;
      log.pick = result.url;
      log.pickHost = host;
      log.rank = index;
      leave("chosen", result.url);
    });
    const hostLabel = document.createElement("span");
    hostLabel.className = "host";
    hostLabel.textContent = host;
    const line = document.createElement("span");
    line.className = "line";
    line.append(link, hostLabel);
    item.append(icon, line);
  });
}

async function showTags(results, { earlier }) {
  const hosts = [...new Set(results.map((result) => hostOf(result.url)))];
  const histories = await Promise.all(hosts.map(hostHistory));
  const history = new Map(hosts.map((host, index) => [host, histories[index]]));
  const tags = resultTags(hosts, earlier, history, new Date(at).setHours(0, 0, 0, 0));
  for (const [host, text] of tags) {
    // Only a host's first result wears its tag.
    const item = $(`#results li[data-host="${CSS.escape(host)}"]`);
    const tag = document.createElement("span");
    tag.className = "tag rb";
    tag.textContent = text;
    item.querySelector(".line").append(tag);
    item.classList.add("tagged");
    log.tagsShown.push({ host, tag: text });
  }
}

async function go() {
  if (!lucky) {
    leave("bypassed", resultsUrl(query));
    return;
  }
  fitQuery();
  showPending();
  requestAnimationFrame(tick);
  setTimeout(() => document.body.classList.add("lingering"), LINGER_MS);
  const recalled = recall();
  const config = await fetch("config.json")
    .then((response) => response.json())
    .catch(() => {
      throw new Error("config.json is missing; run `mise browser` to render it");
    });
  const searching = search(query, config.kagi, controller.signal);
  // Notes, tags, and history only decorate the page: the search never waits on them, and a note
  // or tag counts as shown only when it was drawn before the page left.
  recalled.then(showDeja);
  const results = await searching;
  log.searchMs = Math.round(performance.now());
  log.results = results.map(({ url, title }) => ({ url, title }));
  if (results.length === 0) {
    leave("no_results", quickAnswerUrl(query));
    return;
  }
  const deciding = decide(query, results, config.openai, config.models.decide, controller.signal);
  showResults(results);
  recalled.then((memory) => {
    const kagi = $("#race .kagi");
    kagi.textContent = `kagi ${seconds(log.searchMs)}`;
    kagi.style.left = position(log.searchMs);
    kagi.className = `below kagi ${pace(log.searchMs, memory.current.kagi)}`;
    return showTags(results, memory);
  });
  const answer = await deciding;
  log.decisionMs = Math.round(performance.now()) - log.searchMs;
  log.answer = answer;
  const target = destination(query, answer);
  if (answer.type === "choice") {
    log.pick = answer.choice;
    log.confidence = answer.confidence;
    const rank = results.findIndex((result) => result.url === answer.choice);
    log.rank = rank === -1 ? null : rank;
  }
  const landed = target === log.pick;
  if (landed) log.pickHost = hostOf(target);
  leave(landed ? "landed" : "quick_answer", target);
}

go().catch((error) => {
  if (controller.signal.aborted) return;
  log.error = String(error.message ?? error);
  chrome.runtime.sendMessage({ type: "searched", search: { ...log, outcome: "error" } });
  $("#status").textContent = log.error;
  document.body.classList.add("lingering");
  throw error;
});
