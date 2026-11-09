import assert from "node:assert/strict";
import { test } from "node:test";

import { resultTags } from "./files/lucky/tags.js";

const DAY_START = 1_000_000;
const quiet = { visits: 0, lastVisit: 0 };
const searched = (hosts, outcome, pickHost, regret = false) => ({
  results: hosts.map((host) => ({ url: `https://${host}/page` })),
  outcome,
  pickHost,
  regret,
});
const history = (entries) => new Map(entries);

test("the most-landed site is the usual, and a site Lucky sent you to and you overruled is regretted", () => {
  const earlier = [
    searched(["a.io", "b.io"], "landed", "a.io"),
    searched(["a.io", "b.io"], "landed", "b.io", true),
    searched(["a.io", "b.io"], "landed", "a.io"),
  ];
  const tags = resultTags(["b.io", "a.io"], earlier, history([["a.io", quiet], ["b.io", quiet]]), DAY_START);
  assert.deepEqual([...tags], [["a.io", "the usual"], ["b.io", "regretted"]]);
});

test("a site in every past result list that Lucky never picked is benched, and outranks a new face", () => {
  const earlier = [
    searched(["a.io", "b.io"], "landed", "a.io"),
    searched(["a.io", "b.io"], "landed", "a.io"),
    searched(["a.io", "b.io"], "escaped", null),
  ];
  const tags = resultTags(
    ["a.io", "b.io", "c.io"],
    earlier,
    history([["a.io", quiet], ["b.io", quiet], ["c.io", quiet]]),
    DAY_START,
  );
  assert.deepEqual([...tags], [["a.io", "the usual"], ["b.io", "benched"]]);
});

test("at most two tags show, strongest first, one per site", () => {
  const tags = resultTags(
    ["a.io", "b.io", "c.io"],
    [searched(["x.io"], "chosen", "c.io")],
    history([
      ["a.io", { visits: 3, lastVisit: DAY_START }],
      ["b.io", { visits: 20, lastVisit: DAY_START - 1 }],
      ["c.io", { visits: 50, lastVisit: DAY_START }],
    ]),
    DAY_START,
  );
  assert.deepEqual([...tags], [["c.io", "your pick"], ["b.io", "regular"]]);
});

test("a first search tags nothing from the log", () => {
  const tags = resultTags(["a.io"], [], history([["a.io", { visits: 19, lastVisit: DAY_START - 1 }]]), DAY_START);
  assert.equal(tags.size, 0);
});
