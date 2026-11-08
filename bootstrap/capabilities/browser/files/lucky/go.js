import { decide, destination, quickAnswerUrl, resultsUrl, route, search } from "./lucky.js";

const { lucky, query } = route(new URLSearchParams(location.search).get("q") ?? "");
const controller = new AbortController();

document.title = query;
document.querySelector("#query").textContent = query;

addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  controller.abort();
  location.replace(resultsUrl(query));
});

async function go() {
  if (!lucky) {
    location.replace(resultsUrl(query));
    return;
  }
  const keys = await fetch("keys.json")
    .then((response) => response.json())
    .catch(() => {
      throw new Error("keys.json is missing; run `mise browser` to render it");
    });
  const started = performance.now();
  const results = await search(query, keys.kagi, controller.signal);
  const searched = performance.now();
  if (results.length === 0) {
    location.replace(quickAnswerUrl(query));
    return;
  }
  const answer = await decide(query, results, keys.openai, controller.signal);
  const target = destination(query, answer);
  const tab = await chrome.tabs.getCurrent();
  await chrome.storage.session.set({
    [`tab:${tab.id}`]: {
      query,
      results,
      answer,
      target,
      searchMs: Math.round(searched - started),
      decisionMs: Math.round(performance.now() - searched),
    },
  });
  location.replace(target);
}

go().catch((error) => {
  if (controller.signal.aborted) return;
  document.querySelector("#status").textContent = String(error.message ?? error);
  document.body.classList.add("failed");
  throw error;
});
