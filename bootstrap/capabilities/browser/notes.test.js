import assert from "node:assert/strict";
import { test } from "node:test";

import { chip, fill, inHours, notable, queryValues, rejection } from "./files/lucky/notes.js";

const DAY = 24 * 60 * 60 * 1000;

const note = (overrides) => ({
  match: { query_regex: "^home ?assistant\\b", hours: null },
  message: "{query_count} searches and counting.",
  should_match: ["Home Assistant", "homeassistant docs"],
  should_not_match: ["home depot", "assistant to the regional manager"],
  expires_in_days: 14,
  max_shows: 3,
  ...overrides,
});
const context = {
  key: "home assistant",
  pastKeys: ["home assistant", "jaguar", "mise docs", "react hooks"],
};

test("a matcher that holds up against its examples and the past is accepted", () => {
  assert.equal(rejection(note({}), context), null);
});

test("a matcher must behave the way its own examples say", () => {
  assert.match(
    rejection(note({ should_not_match: ["home assistant cloud", "home depot"] }), context),
    /should_not_match examples: home assistant cloud/,
  );
  assert.match(
    rejection(note({ should_match: ["hass", "home assistant"] }), context),
    /misses its should_match examples: hass/,
  );
  assert.match(
    rejection(note({ match: { query_regex: "^hass$", hours: null }, should_match: ["hass", "HASS"] }), context),
    /does not match the query that triggered it/,
  );
});

test("a matcher may fire on a few other past queries, but not more", () => {
  // 40 other queries allow max(3, 5% of 40) = 3 matches.
  const others = (hits) => [
    ...Array.from({ length: hits }, (_, i) => `home assistant ${i}`),
    ...Array.from({ length: 40 - hits }, (_, i) => `query ${i}`),
  ];
  const broad = note({ should_not_match: ["home depot", "assistant"] });
  assert.equal(rejection(broad, { ...context, pastKeys: ["home assistant", ...others(3)] }), null);
  assert.match(
    rejection(broad, { ...context, pastKeys: ["home assistant", ...others(4)] }),
    /matches 4 of 40 other past queries/,
  );
});

test("a note's chip names the strongest reason its search was notable", () => {
  assert.equal(chip(["personal_best", "repeat_5"]), "on repeat");
  assert.equal(chip(["repeat_3", "escaped"]), "fled");
  assert.equal(chip(["personal_best"]), "PB");
});

test("only known placeholders may appear, so every number is filled locally", () => {
  assert.match(rejection(note({ message: "{streak} days in a row." }), context), /unknown placeholders: streak/);
});

test("a regex that does not compile is rejected rather than thrown", () => {
  assert.match(
    rejection(note({ match: { query_regex: "(home", hours: null } }), context),
    /does not compile/,
  );
});

test("hours wrap past midnight", () => {
  assert.equal(inHours({ start: 23, end: 5 }, 2), true);
  assert.equal(inHours({ start: 23, end: 5 }, 5), false);
  assert.equal(inHours({ start: 9, end: 17 }, 9), true);
  assert.equal(inHours({ start: 9, end: 17 }, 17), false);
});

test("a note with a placeholder that has no value stays silent", () => {
  assert.equal(fill("Last time: {last_host}.", { last_host: null }), null);
  assert.equal(fill("Last time: {last_host}.", { last_host: "docs.rs" }), "Last time: docs.rs.");
});

test("query values count the current search and only landed picks", () => {
  const now = 100 * DAY;
  const earlier = [
    { at: now - 10 * DAY, outcome: "landed", pickHost: "old.example", regret: true },
    { at: now - 3 * DAY, outcome: "landed", pickHost: "docs.rs", regret: false },
    { at: now - 2 * DAY, outcome: "escaped", pickHost: null, regret: false },
  ];
  assert.deepEqual(queryValues(earlier, now), {
    query_count: 4,
    week_count: 3,
    days_since: 2,
    last_host: "docs.rs",
    regrets: 1,
  });
});

test("a search is notable at a repeat milestone or when it lands somewhere new", () => {
  const landed = (host) => ({ outcome: "landed", pickHost: host, pb: false });
  assert.deepEqual(notable(landed("a.example"), [landed("a.example"), landed("a.example")]), ["repeat_3"]);
  assert.deepEqual(notable(landed("a.example"), [landed("a.example")]), []);
  assert.deepEqual(notable(landed("b.example"), [landed("a.example")]), ["new_destination"]);
});
