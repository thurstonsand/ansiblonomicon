---
name: cloudflare-ops
description: Guidance on how to observe Cloudflare resources. Use this before asking the Cloudflare MCP about workers, logs, or AI Gateway behavior.
---

# Cloudflare ops

Guidance for how to use the Cloudflare MCP for this project.

- For historical `aig` LLM traffic, ask about **AI Gateway logs** for gateway **`llms`**.
- For worker runtime/debug logs on **`aig`** or **`llms`**, ask about **Workers Observability**.
- For custom metrics only, ask about **Analytics Engine** datasets **`aig_events`** and **`llms_usage`**.
- Only use **worker tails** when you explicitly need a live stream.
- For actual live tails, use Wrangler from the worker directory:
  - `cd wrangler/aig && wrangler tail --format pretty`
  - `cd wrangler/llms && wrangler tail --format pretty`
  - `cd wrangler/hooks && wrangler tail --format pretty`

## Important repo facts

- `aig` forwards provider traffic through AI Gateway **`llms`**.
- `aig`, `llms`, and `hooks` are the relevant worker names in this repo.
- `aig_events` is **not** a full log store; it only has lightweight custom datapoints.
- `llms_usage` is usage analytics, not primary request logging.
- Tailing workers is usually the wrong first move when you want historical logs.

## Rule of thumb

- Want request history for `aig`? → **AI Gateway (`llms`)**
- Want edge/runtime logs? → **Workers Observability**
- Want counters/latency/tokens/custom metrics? → **Analytics Engine**
- Want live output right now? → **tail**
