// Result tags are short labels Lucky computes from its own log and browser history.
import { hostOf } from "./notes.js";

export const TAG_LIMIT = 2;
const BENCH_MIN_SEARCHES = 3;
const REGULAR_VISITS = 20;

const resultHosts = (search) => new Set(search.results.map((result) => hostOf(result.url)));

// `earlier` holds this query's previous searches, `history` maps a host to its browser-history
// { visits, lastVisit }, and `dayStart` is local midnight. Returns host → tag, strongest first.
export function resultTags(hosts, earlier, history, dayStart) {
  const searched = earlier.filter((search) => search.results.length > 0);
  const landings = new Map();
  for (const search of earlier) {
    if (search.outcome === "landed") landings.set(search.pickHost, (landings.get(search.pickHost) ?? 0) + 1);
  }
  const [usual, usualCount] = [...landings].reduce((best, entry) => (entry[1] > best[1] ? entry : best), [null, 0]);
  const rules = [
    ["the usual", (host) => host === usual && usualCount >= 2],
    ["regretted", (host) => earlier.some((search) => search.regret && search.pickHost === host)],
    ["your pick", (host) => earlier.some((search) => search.outcome === "chosen" && search.pickHost === host)],
    [
      "benched",
      (host) =>
        searched.length >= BENCH_MIN_SEARCHES &&
        searched.every((search) => resultHosts(search).has(host) && search.pickHost !== host),
    ],
    ["regular", (host) => history.get(host).visits >= REGULAR_VISITS],
    ["new face", (host) => searched.length >= 2 && searched.every((search) => !resultHosts(search).has(host))],
    ["seen today", (host) => history.get(host).lastVisit >= dayStart],
  ];
  const tagged = [];
  for (const host of new Set(hosts)) {
    const rank = rules.findIndex(([, applies]) => applies(host));
    if (rank !== -1) tagged.push({ host, rank });
  }
  tagged.sort((a, b) => a.rank - b.rank);
  return new Map(tagged.slice(0, TAG_LIMIT).map(({ host, rank }) => [host, rules[rank][0]]));
}
