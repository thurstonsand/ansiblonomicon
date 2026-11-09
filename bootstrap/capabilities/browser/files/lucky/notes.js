// Notes are lines Sol writes after a notable search, for Lucky's page to show the next time a
// matching query comes up. Everything here is pure, so the page and the worker share it.

export const MESSAGE_LIMIT = 90;
export const EXPIRY_DAYS = { min: 1, max: 60 };
export const SHOWS = { min: 1, max: 20 };
export const REPEAT_MILESTONES = [3, 5, 10, 25, 50, 100, 250, 500];
const DAY = 24 * 60 * 60 * 1000;

// Each placeholder is filled locally when a note is shown, so its number stays true.
export const PLACEHOLDERS = {
  query_count: "times this query has been searched, counting the current search",
  week_count: "times this query has been searched in the last 7 days, counting the current search",
  days_since: "whole days since this query was last searched",
  last_host: "the site Lucky last sent this query to",
  regrets: "times Alt+Shift+K overruled Lucky's pick for this query",
  visits: "browser-history visits to last_host",
};

// The chip beside a note names what made its search notable, strongest reason first.
const CHIPS = [
  ["regret", "regret"],
  ["escaped", "fled"],
  ["chosen_by_hand", "hand picked"],
  ["new_destination", "new spot"],
  ["repeat_", "on repeat"],
  ["personal_best", "PB"],
];

export function chip(reasons) {
  return CHIPS.find(([reason]) => reasons.some((given) => given.startsWith(reason)))[1];
}

export function normalize(query) {
  return query.trim().toLowerCase().replace(/\s+/g, " ");
}

export function hostOf(url) {
  return new URL(url).hostname.replace(/^www\./, "");
}

export function placeholders(message) {
  return [...message.matchAll(/\{(\w+)\}/g)].map((match) => match[1]);
}

// A placeholder without a value, such as last_host for a query never landed, silences the note.
export function fill(message, values) {
  if (placeholders(message).some((name) => values[name] == null)) return null;
  return message.replace(/\{(\w+)\}/g, (_, name) => String(values[name]));
}

// Hours are local, start inclusive and end exclusive, wrapping past midnight when start > end.
export function inHours(hours, hour) {
  if (hours === null) return true;
  return hours.start < hours.end
    ? hour >= hours.start && hour < hours.end
    : hour >= hours.start || hour < hours.end;
}

export function matches(note, key, hour) {
  return new RegExp(note.match.query_regex, "i").test(key) && inHours(note.match.hours, hour);
}

export function live(note, now) {
  return note.expiresAt > now && note.shows < note.maxShows;
}

// What makes a search worth asking Sol about. `earlier` holds this query's previous searches.
export function notable(search, earlier) {
  const reasons = [];
  if (search.outcome === "escaped") reasons.push("escaped");
  if (search.outcome === "chosen") reasons.push("chosen_by_hand");
  if (search.pb) reasons.push("personal_best");
  if (REPEAT_MILESTONES.includes(earlier.length + 1)) reasons.push(`repeat_${earlier.length + 1}`);
  const lastLanded = earlier.findLast((previous) => previous.outcome === "landed");
  if (search.outcome === "landed" && lastLanded && lastLanded.pickHost !== search.pickHost) {
    reasons.push("new_destination");
  }
  return reasons;
}

// Returns why a proposed note is unusable, or null when it may be saved.
// `pastKeys` are the distinct normalized queries searched before, used to catch a matcher that is too broad.
export function rejection(proposed, { key, pastKeys }) {
  const { match, message } = proposed;
  let regex;
  try {
    regex = new RegExp(match.query_regex, "i");
  } catch (error) {
    return `query_regex does not compile: ${error.message}`;
  }
  if (message.length > MESSAGE_LIMIT) return `message is over ${MESSAGE_LIMIT} characters`;
  const unknown = placeholders(message).filter((name) => !(name in PLACEHOLDERS));
  if (unknown.length > 0) return `unknown placeholders: ${unknown.join(", ")}`;
  if (match.hours !== null && match.hours.start === match.hours.end) return "hours start and end are the same";
  if (!regex.test(key)) return `query_regex does not match the query that triggered it: ${key}`;
  const missed = proposed.should_match.filter((example) => !regex.test(normalize(example)));
  if (missed.length > 0) return `query_regex misses its should_match examples: ${missed.join(", ")}`;
  const caught = proposed.should_not_match.filter((example) => regex.test(normalize(example)));
  if (caught.length > 0) return `query_regex matches its should_not_match examples: ${caught.join(", ")}`;
  const others = pastKeys.filter((past) => past !== key);
  const broad = others.filter((past) => regex.test(past));
  if (broad.length > Math.max(3, Math.ceil(others.length * 0.05))) {
    return `query_regex matches ${broad.length} of ${others.length} other past queries`;
  }
  return null;
}

export function toNote(proposed, { searchId, reasons, now }) {
  return {
    createdAt: now,
    searchId,
    reasons,
    match: proposed.match,
    message: proposed.message,
    shouldMatch: proposed.should_match,
    shouldNotMatch: proposed.should_not_match,
    expiresAt: now + proposed.expires_in_days * DAY,
    maxShows: proposed.max_shows,
    shows: 0,
    status: "active",
  };
}

// The values a page note can use, from this query's earlier searches.
export function queryValues(earlier, now) {
  const last = earlier.at(-1);
  const lastLanded = earlier.findLast((search) => search.outcome === "landed");
  return {
    query_count: earlier.length + 1,
    week_count: earlier.filter((search) => search.at > now - 7 * DAY).length + 1,
    days_since: last ? Math.floor((now - last.at) / DAY) : null,
    last_host: lastLanded?.pickHost ?? null,
    regrets: earlier.filter((search) => search.regret).length,
  };
}

export const INSTRUCTIONS = `You are running inside Lucky, a browser extension that takes a search query, and sends the user directly to a website, no intermediate search results. In the interstitial while waiting for that to load, the user is shown the raw search results, a timer, and sometimes, rarely, a one-line note associated with the query, based on historical records. You are the author of that note, to be shown the NEXT time a matching query is searched.

Something notable just happened. Decide whether it deserves a note. A repeat, an escape, a regret usually does; a personal best alone rarely does. When there is nothing specific to say, return no notes: silence beats filler. A good note is specific, true, and points out something about this person's own searching that they would not have noticed. 

These messages should be written with a cheeky, irreverant, playful tone. Keep in mind that the user will have upwards of 2 seconds to read, so keep it concise. Never write a generic joke, pun, greeting, or motivational line, never restate the query, and don't repeat across notes.

Lucky checks each note against its own fields before saving it and drops any that contradicts itself, so make the matcher, the examples, and the message agree.`;

export const NOTES_SCHEMA = {
  type: "object",
  properties: {
    notes: {
      type: "array",
      items: {
        type: "object",
        properties: {
          match: {
            type: "object",
            properties: {
              query_regex: {
                type: "string",
                description:
                  "Runs case-insensitively against the trimmed, lowercased query. Make it exactly as broad as the observation: it must match the triggering query. Lucky rejects a matcher that would fire on more than a few of the person's other past queries.",
              },
              hours: {
                description:
                  "Local hours when the note may show, start inclusive and end exclusive, wrapping past midnight when start > end. Null unless the note is about the time of day.",
                anyOf: [
                  {
                    type: "object",
                    properties: {
                      start: { type: "integer", minimum: 0, maximum: 23 },
                      end: { type: "integer", minimum: 0, maximum: 23 },
                    },
                    required: ["start", "end"],
                    additionalProperties: false,
                  },
                  { type: "null" },
                ],
              },
            },
            required: ["query_regex", "hours"],
            additionalProperties: false,
          },
          message: {
            type: "string",
            description: `At most ${MESSAGE_LIMIT} characters. Write numbers and sites only as placeholders, which Lucky fills in when the note is shown: ${Object.entries(
              PLACEHOLDERS,
            )
              .map(([name, meaning]) => `{${name}} is ${meaning}`)
              .join("; ")}.`,
          },
          should_match: {
            type: "array",
            items: { type: "string" },
            minItems: 2,
            description: "Queries query_regex must match.",
          },
          should_not_match: {
            type: "array",
            items: { type: "string" },
            minItems: 2,
            description: "Near misses query_regex must not match.",
          },
          expires_in_days: { type: "integer", minimum: EXPIRY_DAYS.min, maximum: EXPIRY_DAYS.max },
          max_shows: {
            type: "integer",
            minimum: SHOWS.min,
            maximum: SHOWS.max,
            description: "How many times the note may show before it retires itself.",
          },
        },
        required: [
          "match",
          "message",
          "should_match",
          "should_not_match",
          "expires_in_days",
          "max_shows",
        ],
        additionalProperties: false,
      },
    },
    retire: {
      type: "array",
      items: { type: "integer" },
      description: "Ids of active notes that yours supersede or that are no longer true.",
    },
  },
  required: ["notes", "retire"],
  additionalProperties: false,
};

export function notesRequest(model, context) {
  return {
    model,
    instructions: INSTRUCTIONS,
    input: JSON.stringify(context),
    reasoning: { effort: "low" },
    text: { format: { type: "json_schema", name: "lucky_notes", strict: true, schema: NOTES_SCHEMA } },
  };
}

export async function writeNotes(model, context, key) {
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(notesRequest(model, context)),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(`OpenAI notes failed with ${response.status}: ${JSON.stringify(body)}`);
  if (body.status !== "completed") throw new Error(`OpenAI notes ended ${body.status}: ${JSON.stringify(body.incomplete_details)}`);
  const content = body.output.find((item) => item.type === "message").content[0];
  if (content.type === "refusal") throw new Error(`OpenAI notes refused: ${content.refusal}`);
  return JSON.parse(content.text);
}
