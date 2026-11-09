export const RESULT_LIMIT = 10;
export const CONFIDENCE_THRESHOLD = 0.5;
export const ESCAPE_PREFIX = ",";
export const SHOW_RESULTS = "show_results";

export const INSTRUCTIONS = `The user typed this query into their browser's address bar and pressed Enter. Instead of a results page, they will be taken straight to the page you choose.
Choose the result they most likely meant to visit. For a site, product, or tool, that is its official page. For a question, it is the page that answers it best.
Choose ${SHOW_RESULTS} when no result is a good destination or the query needs several sources compared.`;

export const SHOW_RESULTS_DESCRIPTION =
  "Show the full search results list instead of picking one page.";

// `via` names why a search skips Lucky: the escape prefix, a Kagi bang, a trailing "?", or no query.
export function route(query) {
  const trimmed = query.trim();
  if (trimmed.startsWith(ESCAPE_PREFIX)) {
    return { lucky: false, via: "escape", query: trimmed.slice(ESCAPE_PREFIX.length).trim() };
  }
  // Kagi bangs, such as !w or !gh, already name their destination,
  // and a trailing "?" already asks Kagi for its Quick Answer.
  if (/(^|\s)![^\s!]/.test(trimmed)) return { lucky: false, via: "bang", query: trimmed };
  if (trimmed.endsWith("?")) return { lucky: false, via: "question", query: trimmed };
  if (trimmed === "") return { lucky: false, via: "empty", query: trimmed };
  return { lucky: true, via: "lucky", query: trimmed };
}

export function resultsUrl(query) {
  const url = new URL("https://kagi.com/search");
  url.searchParams.set("q", query);
  url.searchParams.set("lucky", "off");
  return url.href;
}

// A trailing "?" makes Kagi open its Quick Answer above the results.
export function quickAnswerUrl(query) {
  return resultsUrl(`${query}?`);
}

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };

// Kagi highlights matched terms with <strong> and similar markup, and escapes the text as HTML.
export const stripTags = (html) =>
  html
    .replace(/<[^>]*>/g, "")
    .replace(/&(#x[\da-f]+|#\d+|\w+);/gi, (entity, name) => {
      if (name[0] !== "#") return ENTITIES[name.toLowerCase()] ?? entity;
      return String.fromCodePoint(name[1].toLowerCase() === "x" ? parseInt(name.slice(2), 16) : Number(name.slice(1)));
    });

export async function search(query, key, signal) {
  const response = await fetch("https://kagi.com/api/v1/search", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: RESULT_LIMIT }),
    signal,
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(`Kagi search failed with ${response.status}: ${JSON.stringify(body)}`);
  const results = new Map();
  for (const item of body.data.search ?? []) {
    if (!results.has(item.url)) {
      results.set(item.url, {
        url: item.url,
        title: stripTags(item.title),
        snippet: stripTags(item.snippet ?? ""),
      });
    }
  }
  return [...results.values()];
}

export function decisionRequest(model, query, results) {
  return {
    model,
    input: `Address bar query: ${query}`,
    questions: [
      {
        type: "choice",
        name: "destination",
        instructions: INSTRUCTIONS,
        choices: [
          ...results.map((result) => ({
            value: result.url,
            description: `${result.title}\n${result.snippet}`,
          })),
          { value: SHOW_RESULTS, description: SHOW_RESULTS_DESCRIPTION },
        ],
      },
    ],
  };
}

export async function decide(query, results, key, model, signal) {
  const response = await fetch("https://api.openai.com/v1/decisions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(decisionRequest(model, query, results)),
    signal,
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(`OpenAI decision failed with ${response.status}: ${JSON.stringify(body)}`);
  return body.answers[0];
}

export function destination(query, answer) {
  const confident = answer.type === "choice" && answer.confidence >= CONFIDENCE_THRESHOLD;
  return confident && answer.choice !== SHOW_RESULTS ? answer.choice : quickAnswerUrl(query);
}
