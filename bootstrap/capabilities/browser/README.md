# Browser

Owns Lucky, a Chrome extension that turns address-bar searches into an AI "I'm Feeling Lucky": the query goes to Kagi's Search API, OpenAI's Decisions API picks the result you most likely meant, and the tab goes straight there.

Run `mise browser`, or `mise omarchy -t browser` on no9-type-s. It renders `files/lucky/keys.json` from `KAGI_API_KEY` and `OPENAI_API_KEY` with mode `0600`; Git ignores it. Chrome loads the extension unpacked from the checkout, so a reconcile only needs to render the keys. pod042 registers the task for its desktop Chromium, outside its full reconcile.

## Install in a Chrome profile

1. On Mac and Windows, Lucky's `chrome_settings_overrides` makes Kagi the default search engine, with Kagi's autosuggest. Chrome supports that key on no other platform: on Linux it lists it as a manifest error and ignores it, so set Kagi as the default by hand with `https://kagi.com/search?q=%s` as its URL.
2. Open `chrome://extensions/`, enable **Developer mode**, choose **Load unpacked**, and select `bootstrap/capabilities/browser/files/lucky` in the checkout. The manifest's `key` pins the ID to `plnpnoncepmnejjhhmbkjhccfegdlecn`.
3. After editing the source, use the extension's **Reload** button.

## How it decides

A `declarativeNetRequest` rule redirects top-level navigations to `kagi.com/search` into `go.html`, except those started from a Kagi page and those carrying `lucky=off`. `go.html` searches Kagi, asks one Decisions `choice` question over the results plus a `show_results` option, and replaces itself with the pick, so Back returns to the page before the search. Each tab's last query, results, answer, and timings stay in `chrome.storage.session` under `tab:<id>`.

When the pick is unclear (no results, `show_results`, a refusal, or confidence below `CONFIDENCE_THRESHOLD`), Lucky opens Kagi with a `?` appended to the query, which triggers Kagi's Quick Answer above the results. A query that starts with `,`, contains a Kagi bang, or already ends in `?` goes to Kagi unchanged, as do Esc on the interstitial and Alt+Shift+K on the page Lucky chose. An API failure stays on the interstitial with the error.

`lucky.js` holds the tunables: the prompt, model, result count, confidence threshold, and escape prefix. Search uses Kagi's v1 API with the Kagi item's `v1 apikey`. v1's page extraction is left off: it added 2–8 seconds per search.
