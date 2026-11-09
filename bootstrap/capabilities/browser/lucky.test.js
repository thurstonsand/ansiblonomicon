import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CONFIDENCE_THRESHOLD,
  destination,
  resultsUrl,
  route,
  SHOW_RESULTS,
  stripTags,
} from "./files/lucky/lucky.js";

test("the escape prefix sends the rest of the query to plain results", () => {
  assert.deepEqual(route("  ,react hooks "), { lucky: false, via: "escape", query: "react hooks" });
});

test("Kagi bangs pass through untouched, wherever they sit", () => {
  assert.deepEqual(route("!w mount everest"), { lucky: false, via: "bang", query: "!w mount everest" });
  assert.deepEqual(route("ansiblonomicon !gh"), { lucky: false, via: "bang", query: "ansiblonomicon !gh" });
});

test("an exclamation mark that is not a bang stays lucky", () => {
  assert.deepEqual(route("yahoo!"), { lucky: true, via: "lucky", query: "yahoo!" });
  assert.deepEqual(route("wow !! nice"), { lucky: true, via: "lucky", query: "wow !! nice" });
});

test("a confident pick is the destination; anything else asks Kagi's Quick Answer", () => {
  const pick = (choice, confidence) => ({ type: "choice", choice, confidence, probabilities: [] });
  const quickAnswer = "https://kagi.com/search?q=q%3F&lucky=off";
  assert.equal(
    destination("q", pick("https://a.example/", CONFIDENCE_THRESHOLD)),
    "https://a.example/",
  );
  assert.equal(
    destination("q", pick("https://a.example/", CONFIDENCE_THRESHOLD - 0.01)),
    quickAnswer,
  );
  assert.equal(destination("q", pick(SHOW_RESULTS, 0.99)), quickAnswer);
  assert.equal(destination("q", { type: "refusal", name: "destination" }), quickAnswer);
});

test("a trailing question mark goes straight to Kagi's Quick Answer", () => {
  assert.deepEqual(route("how tall is everest? "), { lucky: false, via: "question", query: "how tall is everest?" });
  assert.deepEqual(route("is ? a wildcard"), { lucky: true, via: "lucky", query: "is ? a wildcard" });
});

test("the results page carries the marker that lets it past the redirect", () => {
  assert.equal(resultsUrl("a&b c"), "https://kagi.com/search?q=a%26b+c&lucky=off");
});

test("result titles lose Kagi's markup and HTML escaping", () => {
  assert.equal(
    stripTags("All Of <strong>Jaguar</strong>&#39;s Models &amp; SUVs &#x2014; &lt;b&gt; &nbsp;"),
    "All Of Jaguar's Models & SUVs — <b> &nbsp;",
  );
});
