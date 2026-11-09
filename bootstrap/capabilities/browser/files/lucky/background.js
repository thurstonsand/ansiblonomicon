import { resultsUrl } from "./lucky.js";
import { hostOf, notable, rejection, toNote, writeNotes } from "./notes.js";
import {
  activeNotes,
  average,
  distinctKeys,
  getSearch,
  markRegret,
  open,
  record,
  saveNotesRun,
  searchesFor,
  searchesTo,
  totals,
  hostHistory,
} from "./stats.js";

const dbReady = open();

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.type === "searched") remember(message.search, sender.tab.id);
});

chrome.commands.onCommand.addListener((command, tab) => {
  if (command === "show-results") overrule(tab);
});
chrome.action.onClicked.addListener(overrule);

// Sends the tab to Kagi's results for the search Lucky last landed it on, and marks that search a regret.
async function overrule(tab) {
  const key = `tab:${tab.id}`;
  const { [key]: last } = await chrome.storage.session.get(key);
  if (!last) return;
  await chrome.storage.session.remove(key);
  await chrome.tabs.update(tab.id, { url: resultsUrl(last.query) });
  const db = await dbReady;
  await markRegret(db, last.searchId);
  const search = await getSearch(db, last.searchId);
  const earlier = (await searchesFor(db, search.key)).filter((other) => other.id < search.id);
  await annotate(db, search, earlier, ["regret"]);
}

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(`tab:${tabId}`));

async function remember(search, tabId) {
  const db = await dbReady;
  const id = await record(db, search);
  // Only a page Lucky chose can be overruled, and only once.
  if (search.outcome === "landed") {
    await chrome.storage.session.set({ [`tab:${tabId}`]: { query: search.query, searchId: id } });
  }
  if (search.via !== "lucky") return;
  const earlier = (await searchesFor(db, search.key)).filter((other) => other.id < id);
  const reasons = notable(search, earlier);
  if (reasons.length > 0) await annotate(db, { ...search, id }, earlier, reasons);
}

// Asks Sol whether a notable search deserves notes for next time, then keeps the ones that hold up.
async function annotate(db, search, earlier, reasons) {
  const started = Date.now();
  const config = await fetch("config.json").then((response) => response.json());
  const [toSite, pastKeys, active, current, history] = await Promise.all([
    search.pickHost ? searchesTo(db, search.pickHost) : [],
    distinctKeys(db),
    activeNotes(db, started),
    totals(db),
    search.pickHost ? hostHistory(search.pickHost) : null,
  ]);
  const context = {
    reasons,
    local_time: new Date(search.at).toString(),
    search: {
      query: search.query,
      outcome: search.outcome,
      regret: search.regret,
      pick_host: search.pickHost,
      pick_rank: search.rank,
      confidence: search.confidence,
      kagi_ms: search.searchMs,
      total_ms: search.decisionMs === null ? null : search.searchMs + search.decisionMs,
      personal_best: search.pb,
      results: search.results.map((result) => ({ host: hostOf(result.url), title: result.title })),
    },
    this_query_searches: earlier.length + 1,
    this_query_before: earlier.slice(-20).map((other) => ({
      when: new Date(other.at).toString(),
      outcome: other.outcome,
      pick_host: other.pickHost,
      regret: other.regret,
    })),
    pick_host_from_lucky: {
      searches: toSite.length,
      queries: [...new Set(toSite.map((other) => other.key))].slice(-20),
    },
    pick_host_history_visits: history?.visits ?? null,
    lucky: {
      searches: current.searches,
      average_total_ms: current.total && Math.round(average(current.total)),
      best_total_ms: current.total?.best ?? null,
    },
    active_notes: active.slice(-30).map((note) => ({
      id: note.id,
      match: note.match,
      message: note.message,
      shows: note.shows,
      max_shows: note.maxShows,
    })),
  };
  const run = { at: started, model: config.models.notes, reasons, context };
  let reply;
  try {
    reply = await writeNotes(config.models.notes, context, config.openai);
  } catch (error) {
    const failed = { ...run, ms: Date.now() - started, error: String(error.message ?? error) };
    await saveNotesRun(db, search.id, { notes: [], retire: [], run: failed });
    throw error;
  }
  const notes = [];
  const rejected = [];
  for (const proposed of reply.notes) {
    const reason = rejection(proposed, { key: search.key, pastKeys });
    if (reason) rejected.push({ proposed, reason });
    else notes.push(toNote(proposed, { searchId: search.id, reasons, now: Date.now() }));
  }
  const activeIds = new Set(active.map((note) => note.id));
  const retire = reply.retire.filter((id) => activeIds.has(id));
  await saveNotesRun(db, search.id, {
    notes,
    retire,
    run: { ...run, ms: Date.now() - started, reply, rejected },
  });
}
