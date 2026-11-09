# Browser

Owns Lucky, a Chrome extension that turns address-bar searches into an AI "I'm Feeling Lucky": the query goes to Kagi's Search API, OpenAI's Decisions API picks the result you most likely meant, and the tab goes straight there.

Run `mise browser`, or `mise omarchy -t browser` on no9-type-s. It renders `files/lucky/config.json` with mode `0600`; Git ignores it. The file holds `KAGI_API_KEY`, `OPENAI_API_KEY`, and the OpenAI models from `agent-harness/models.yml`: `gpt_luna` makes the decision and `gpt_sol` writes notes. Chrome loads the extension unpacked from the checkout, so a reconcile only needs to render the config. pod042 registers the task for its desktop Chromium, outside its full reconcile.

## Install in a Chrome profile

1. On Mac and Windows, Lucky's `chrome_settings_overrides` makes Kagi the default search engine, with Kagi's autosuggest. Chrome supports that key on no other platform: on Linux it lists it as a manifest error and ignores it, so set Kagi as the default by hand with `https://kagi.com/search?q=%s` as its URL.
2. Open `chrome://extensions/`, enable **Developer mode**, choose **Load unpacked**, and select `bootstrap/capabilities/browser/files/lucky` in the checkout. The manifest's `key` pins the ID to `plnpnoncepmnejjhhmbkjhccfegdlecn`.
3. After editing the source, use the extension's **Reload** button. Reload also grants permissions the manifest adds, such as the `history` and `favicon` permissions Lucky's notes use.

## How it decides

A `declarativeNetRequest` rule redirects top-level navigations to `kagi.com/search` into `go.html`, except those started from a Kagi page and those carrying `lucky=off`. `go.html` searches Kagi, asks one Decisions `choice` question over the results plus a `show_results` option, and replaces itself with the pick, so Back returns to the page before the search. Each tab's last query and its search's log id stay in `chrome.storage.session` under `tab:<id>`, for Alt+Shift+K and Lucky's toolbar button, which both send the tab to Kagi's plain results and mark the search a regret.

When the pick is unclear (no results, `show_results`, a refusal, or confidence below `CONFIDENCE_THRESHOLD`), Lucky opens Kagi with a `?` appended to the query, which triggers Kagi's Quick Answer above the results. A query that starts with `,`, contains a Kagi bang, or already ends in `?` goes to Kagi unchanged, as do Esc on the interstitial and Alt+Shift+K or the toolbar button on the page Lucky chose. An API failure stays on the interstitial with the error.

`lucky.js` holds the tunables: the prompt, result count, confidence threshold, and escape prefix. Search uses Kagi's v1 API with the Kagi item's `apikey`. v1's page extraction is left off: it added 2–8 seconds per search.

## The interstitial

The page lives for one or two seconds, so it shows only what exists early, and holds its final layout from the first frame. The query is set large like a search box being typed into. Under it, a note's line appears when one matches, behind a chip that names what made its search notable: `regret`, `fled`, `hand picked`, `new spot`, `on repeat`, or `PB`. A race bar runs from zero, marking the average and the previous run; past the average it turns into red stripes and reads "behind pace", and a split marks when Kagi answered, gold for a personal best, green ahead of its average, red behind. The big clock in the corner matches the bar's colour.

The result list fills placeholder rows about half a second in, each with its site's favicon. `tags.js` labels up to two of them from Lucky's log and browser history, strongest first: `the usual`, `regretted`, `your pick`, `benched` (in every past result list, never picked), `regular` (20+ history visits), `new face`, and `seen today`. After three seconds the list works as a fallback results page; clicking an entry overrides Lucky.

## Stats and notes

`stats.js` keeps Lucky's log in the extension's IndexedDB, named `lucky`:

- `searches` holds one record per search. Each record has the query and how it was routed, the results, the decision, the pick and its rank, and the outcome: `landed`, `quick_answer`, `no_results`, `escaped`, `chosen`, `bypassed`, or `error`. It also has the Kagi split and decision times since the page opened, and the notes shown. A search is marked `regret` when Alt+Shift+K overrules it. Every notes run made for it is logged too, with its full context, Sol's reply, and each rejection's reason.
- `notes` holds what Sol wrote.
- `totals` holds the running averages and bests behind the splits. A personal best counts only after 20 timed runs.

The page sends its record to the service worker as it leaves, so nothing waits on the log. `notes.js` decides when a search is worth asking about: a repeat milestone, an escape, a hand-picked result, a regret, a familiar query landing somewhere new, or a personal best. The worker then calls the Responses API in the background, using Structured Outputs with a strict JSON schema.

A note is data, not code. It has a case-insensitive `query_regex` over the normalized query, optional local hours,, and the reasons that triggered it, for its chip. It also has a message, an expiry, a show limit, and `should_match` and `should_not_match` examples. The worker keeps a note only if:

- its regex compiles;
- it matches the triggering query and every `should_match` example, and none of the `should_not_match` examples;
- it fires on no more than 5% of other past queries, with a minimum of three;
- its message uses only the placeholders in `PLACEHOLDERS`.

Those placeholders are filled locally when the note is shown, so a count stays true and a note whose value is missing stays silent. Sol can retire the active notes that a new one supersedes.

Inspect the log from the service worker's DevTools in `chrome://extensions`, through **Application → IndexedDB → lucky**.
