export const RESULT_LIMIT = 10;
export const MODEL = "gpt-6-luna";
export const CONFIDENCE_THRESHOLD = 0.5;
export const ESCAPE_PREFIX = ",";
export const SHOW_RESULTS = "show_results";

export const INSTRUCTIONS = `The user typed this query into their browser's address bar and pressed Enter. Instead of a results page, they will be taken straight to the page you choose.
Choose the result they most likely meant to visit. For a site, product, or tool, that is its official page. For a question, it is the page that answers it best.
Choose ${SHOW_RESULTS} when no result is a good destination or the query needs several sources compared.`;

export const SHOW_RESULTS_DESCRIPTION =
  "Show the full search results list instead of picking one page.";

export function route(query) {
  const trimmed = query.trim();
  if (trimmed.startsWith(ESCAPE_PREFIX)) {
    return { lucky: false, query: trimmed.slice(ESCAPE_PREFIX.length).trim() };
  }
  // Kagi bangs, such as !w or !gh, already name their destination,
  // and a trailing "?" already asks Kagi for its Quick Answer.
  const hasBang = /(^|\s)![^\s!]/.test(trimmed);
  return { lucky: trimmed !== "" && !hasBang && !trimmed.endsWith("?"), query: trimmed };
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

// Kagi highlights matched terms with <strong> and similar markup.
const stripTags = (html) => html.replace(/<[^>]*>/g, "");

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

export function decisionRequest(query, results) {
  return {
    model: MODEL,
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

export async function decide(query, results, key, signal) {
  const response = await fetch("https://api.openai.com/v1/decisions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(decisionRequest(query, results)),
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
