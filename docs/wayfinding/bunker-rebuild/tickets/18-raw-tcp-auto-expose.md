---
status: closed
type: research
blocked-by: []
---

# Raw TCP auto-expose for agent instances

## Question

Ticket 07 settled HTTP: `<port>.<instance>.thurstons.house` through caddy, and a seeded follow-up for wildcard Cloudflare Access exposure. Raw TCP (postgres, redis, anything without a Host header) fell through: `postgres://` carries no hostname, so name-based routing needs either TLS SNI or a tunnel client.

Sketch what it would take for arbitrary TCP services started on pascal or workers (incus private bridge behind host pod042) to be auto-reachable:

- **Locally** from admin-tier devices, without per-service configuration.
- **Externally** behind Cloudflare Access.

Candidates to bound, primary sources only: caddy `layer4` SNI routing (mholt/caddy-l4 — which clients actually send SNI: libpq, redis, mysql, mongo?); `cloudflared` arbitrary-TCP tunnels (`tcp://` ingress + `cloudflared access tcp` client side); Cloudflare WARP private-network routing (route the incus bridge subnet through the tunnel — every port, every protocol, no per-service anything); plain ssh forwarding ergonomics as the baseline to beat. Anything else needs a primary source and a reason.

Output: `research/raw-tcp-auto-expose.md` — capability matrix, what "automatic" can actually mean per option, and a recommended shape (may combine options for local vs external). Decision stays with the map's writer.

## Resolution

Researched 2026-08-21. [Raw TCP auto-expose research](../research/raw-tcp-auto-expose.md) bounds the candidates with primary sources. It recommends taking an admin-only route to the distinct Incus bridge CIDR plus Cloudflare WARP CIDR routing and default-deny Gateway policy to a spike, while retaining SSH forwarding as the baseline. Caddy-L4 and published `cloudflared access tcp` are bounded as opt-ins, not the generic raw-TCP plane. The map writer retains the final decision.
