// Lucky's log: one record per search, the notes Sol wrote, and running totals for the splits.
// IndexedDB rather than chrome.storage, so a lookup reads one query's history, not the whole log.
import { hostOf, live } from "./notes.js";

const request = (pending) =>
  new Promise((resolve, reject) => {
    pending.onsuccess = () => resolve(pending.result);
    pending.onerror = () => reject(pending.error);
  });

export function open() {
  const opening = indexedDB.open("lucky", 2);
  opening.onupgradeneeded = ({ oldVersion }) => {
    const db = opening.result;
    if (oldVersion === 0) {
      const searches = db.createObjectStore("searches", { keyPath: "id", autoIncrement: true });
      searches.createIndex("key", "key");
      searches.createIndex("pickHost", "pickHost");
      db.createObjectStore("notes", { keyPath: "id", autoIncrement: true });
      db.createObjectStore("totals");
    }
    // Version 2 dropped result notes and gave every note the reasons behind its chip.
    if (oldVersion === 1) opening.transaction.objectStore("notes").clear();
  };
  return request(opening);
}

function transact(db, stores, mode, body) {
  const tx = db.transaction(stores, mode);
  const done = new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onerror = tx.onabort = () => reject(tx.error);
  });
  return Promise.all([body(tx), done]).then(([result]) => result);
}

const EMPTY_TOTALS = { searches: 0, kagi: null, total: null, last: null };
// Beating a best of a handful of runs says nothing, so a personal best counts only after this many.
export const PB_MIN_RUNS = 20;

export const average = (stat) => stat.sum / stat.n;

export function totals(db) {
  return transact(db, "totals", "readonly", async (tx) => {
    return (await request(tx.objectStore("totals").get("lucky"))) ?? EMPTY_TOTALS;
  });
}

export function getSearch(db, id) {
  return transact(db, "searches", "readonly", (tx) => request(tx.objectStore("searches").get(id)));
}

// Oldest first, since ids increase with time.
export function searchesFor(db, key) {
  return transact(db, "searches", "readonly", (tx) =>
    request(tx.objectStore("searches").index("key").getAll(key)),
  );
}

export function searchesTo(db, host) {
  return transact(db, "searches", "readonly", (tx) =>
    request(tx.objectStore("searches").index("pickHost").getAll(host)),
  );
}

export function distinctKeys(db) {
  return transact(
    db,
    "searches",
    "readonly",
    (tx) =>
      new Promise((resolve, reject) => {
        const keys = [];
        const cursor = tx.objectStore("searches").index("key").openKeyCursor(null, "nextunique");
        cursor.onsuccess = () => {
          if (!cursor.result) return resolve(keys);
          keys.push(cursor.result.key);
          cursor.result.continue();
        };
        cursor.onerror = () => reject(cursor.error);
      }),
  );
}

// Oldest first.
export function activeNotes(db, now) {
  return transact(db, "notes", "readonly", async (tx) => {
    const notes = await request(tx.objectStore("notes").getAll());
    return notes.filter((note) => note.status === "active" && live(note, now));
  });
}

const including = (stat, ms) => ({
  best: stat === null ? ms : Math.min(stat.best, ms),
  sum: (stat?.sum ?? 0) + ms,
  n: (stat?.n ?? 0) + 1,
});

// Stores a finished search, folds its splits into the totals, and counts the notes it showed.
export function record(db, search) {
  return transact(db, ["searches", "totals", "notes"], "readwrite", async (tx) => {
    const totalsStore = tx.objectStore("totals");
    const current = (await request(totalsStore.get("lucky"))) ?? EMPTY_TOTALS;
    const next = { ...current, searches: current.searches + 1 };
    if (search.decisionMs !== null) {
      const totalMs = search.searchMs + search.decisionMs;
      search.pb = current.total?.n >= PB_MIN_RUNS && totalMs < current.total.best;
      next.kagi = including(current.kagi, search.searchMs);
      next.total = including(current.total, totalMs);
      next.last = { totalMs, pb: search.pb };
    }
    totalsStore.put(next, "lucky");
    const notes = tx.objectStore("notes");
    for (const id of search.notesShown) {
      const note = await request(notes.get(id));
      notes.put({ ...note, shows: note.shows + 1 });
    }
    return request(tx.objectStore("searches").add(search));
  });
}

export function markRegret(db, id) {
  return transact(db, "searches", "readwrite", async (tx) => {
    const searches = tx.objectStore("searches");
    searches.put({ ...(await request(searches.get(id))), regret: true });
  });
}

// Saves the notes one Sol run produced, retires the ones it superseded, and logs the run on its search.
export function saveNotesRun(db, searchId, { notes, retire, run }) {
  return transact(db, ["notes", "searches"], "readwrite", async (tx) => {
    const store = tx.objectStore("notes");
    const created = [];
    for (const note of notes) created.push(await request(store.add(note)));
    for (const id of retire) {
      store.put({ ...(await request(store.get(id))), status: "retired", retiredBy: searchId });
    }
    const searches = tx.objectStore("searches");
    const search = await request(searches.get(searchId));
    searches.put({ ...search, notesRuns: [...search.notesRuns, { ...run, created }] });
    return created;
  });
}

export async function hostHistory(host) {
  const items = await chrome.history.search({ text: host, startTime: 0, maxResults: 10000 });
  const visited = items.filter((item) => URL.canParse(item.url) && hostOf(item.url) === host);
  return {
    visits: visited.reduce((sum, item) => sum + item.visitCount, 0),
    lastVisit: Math.max(0, ...visited.map((item) => item.lastVisitTime)),
  };
}
