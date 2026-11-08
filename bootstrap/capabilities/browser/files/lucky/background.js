import { resultsUrl } from "./lucky.js";

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== "show-results") return;
  const key = `tab:${tab.id}`;
  const { [key]: last } = await chrome.storage.session.get(key);
  if (last) await chrome.tabs.update(tab.id, { url: resultsUrl(last.query) });
});

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove(`tab:${tabId}`));
