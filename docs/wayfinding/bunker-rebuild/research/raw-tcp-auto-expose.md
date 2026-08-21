# Raw TCP auto-expose for Incus agent instances

> Research only. This bounds the raw-TCP choices for `pascal` and `w-<project>` on pod042's private Incus bridge. It does not choose the platform policy.

## What the HTTP decision does not provide

The settled Caddy convention can derive an HTTP upstream from `<port>.<instance>.thurstons.house` because HTTP carries a Host header. Raw TCP does not. “Automatic” can mean materially different things:

- **No per-service state**: an agent may bind any port and a client can reach the instance address and port. This requires an L3 path, not a name-routing proxy.
- **No per-service server configuration, but a client command**: a general tunnel or SSH transport carries a chosen local port to a chosen instance port.
- **One generated gateway rule per service**: an endpoint has a name and Access policy, but an origin mapping still has to be declared. This is not the desired zero-config path.
- **One rule per instance**: all ports for that instance become reachable through its own address. This is close enough for durable `pascal`, but worker lifecycle still needs address/DNS allocation.

The following assumes an Incus CIDR deliberately distinct from every home/admin LAN CIDR. It must not reuse a common home range: Cloudflare documents that an overlapping local CIDR leaves a WARP client unable to reach the private application.[^warp-cidr]

## Capability matrix

| Option | Protocols covered | What “automatic” means | Local / external fit | Authentication and client requirements | Moving parts and limit |
| --- | --- | --- | --- | --- | --- |
| **Admin-only L3 route to the Incus CIDR** | Every IP protocol and port the host/Incus firewall permits. | Truly no per-service gateway state: connect to `<instance IP>:<port>`. Private DNS can add stable names. | **Best local fit.** A router route to the private bridge via pod042, plus an admin-to-bridge firewall allowance, gives Macs and iPhones ordinary LAN reachability. It is not an Internet exposure. | LAN/admin-tier and each service's own auth. No Cloudflare Access. | One network route and firewall policy; Incus address/DNS lifecycle. It preserves ticket 13's no-new-public-port boundary. |
| **Cloudflare WARP private-network route** | Every TCP/UDP protocol; Gateway can proxy TCP/UDP and optionally ICMP.[^warp-cidr] | No per-service server or hostname config: route the whole Incus CIDR and connect to the same instance IP/port. | **Best remote fit; usable locally too.** WARP carries the bridge CIDR through Cloudflare even while on the home LAN. | Cloudflare One Client enrollment on each Mac/iPhone, WARP login policy, split-tunnel inclusion, then Gateway allow rules. This is Zero Trust identity/Gateway enforcement, rather than a browser Access session per service. | Tunnel must have L3 reachability to the bridge; route, WARP routing, split tunnel, and Gateway policy are durable control-plane state. A broad CIDR grant needs a default-deny Gateway policy. |
| **`cloudflared access tcp` published application** | Any TCP stream, including plaintext. | A hostname-to-one-`tcp://origin:port` ingress mapping remains per service, unless a wildcard maps every name to the same gateway. The user still starts a local forward. | External only in practice; it is needless on the LAN. | A terminal-capable client runs `cloudflared access tcp --hostname … --url localhost:PORT`, receives browser SSO/Access, then points the client at localhost. It is not browser-rendered TCP. | Existing tunnel plus DNS, ingress, and Access app/policy. Cloudflare explicitly requires `cloudflared` on both host and client.[^access-tcp] Its arbitrary-TCP documentation provides no iOS client workflow, so it is not the mobile raw-client path. |
| **Caddy layer4 TLS/SNI gateway** | Direct TLS clients that send SNI; selected protocol-aware handling. Not plaintext or generic STARTTLS. | A wildcard DNS/certificate plus an SNI-derived upstream can reduce gateway declarations, but service discovery still has to turn `(instance, service)` into an IP and port. | Can serve local traffic and, behind a `cloudflared` TCP ingress, external traffic. | Service authentication remains service-specific. TLS clients must send the expected SNI and validate the certificate. | Custom Caddy build, experimental plugin, TLS/certificate choices, and a safe dynamic-upstream design. It does not create a universal TCP router. |
| **Incus network forward / proxy device** | Network forward: whole external address or chosen TCP/UDP ports. Proxy device: TCP/UDP and Unix-socket combinations.[^incus-forward][^incus-proxy] | A network forward with a default target makes all ports of one allocated address reach one instance: one object per instance, not per service. Proxy devices and port-specific forwards are per port. | Local only unless separately routed or tunnelled. | LAN firewall plus service auth; no Access. | Per-instance listen address/forward and instance address stability. Useful where an instance needs its own LAN-facing address; not an arbitrary-worker auto-publisher. |
| **SSH `ProxyJump` + `LocalForward`** | Any TCP service. | Nothing is published. The user chooses a local listening port and remote instance port for the session. | Works locally through pod042; externally if the existing SSH Access path reaches pod042. | Existing SSH authentication (and any existing Cloudflare SSH Access client path). `ProxyJump` reaches the target through pod042; `LocalForward` transports a local TCP port over that channel.[^openssh] | Chezmoi can make host aliases and common forwards painless, but every ad-hoc service still needs a forward/session. It remains the conservative baseline. |

## Caddy layer4: useful, but not a general solution

[`mholt/caddy-l4`](https://github.com/mholt/caddy-l4) is an experimental, non-official Caddy app; its upstream README says to expect breaking changes. It can match a TLS ClientHello SNI name, proxy raw bytes, terminate TLS, and coexist with Caddy's HTTP and TLS apps.[^caddy-l4] Its upstream module list includes `l4tls` and `l4postgres`, but no MySQL or Redis protocol handler.[^caddy-modules]

The image presently declared here, `ghcr.io/caddybuilds/caddy-cloudflare`, builds the Cloudflare DNS and IP modules, not `mholt/caddy-l4`.[^caddy-cloudflare-image] A candidate must build one Caddy binary with the existing DNS/IP modules *and* `github.com/mholt/caddy-l4`. Caddy-L4 can use Caddy's certificate manager, so the existing DNS-01 wildcard capability can furnish a certificate when Caddy terminates TLS. But `*.thurstons.house` does not cover the two-label HTTP-style name `5432.pascal.thurstons.house`; it needs a wildcard such as `*.pascal.thurstons.house`, or a certificate for each exact name.[^wildcard-depth] That is per-instance certificate lifecycle state, even though DNS-01 makes issuance practical. TLS passthrough does **not** furnish a certificate to the backend: it must present one valid for the name itself.

### Client/protocol boundary

| Client/protocol | Is SNI usable for Caddy-L4 routing? | Why |
| --- | --- | --- |
| Generic direct TLS client | **Only if it sends SNI before application bytes.** | SNI lives in the first TLS ClientHello. A client pointed at an IP, or configured without `servername`, supplies no routing key. |
| `psql` / libpq 14+ | **Not with the generic TLS matcher in classic mode.** | PostgreSQL 14 added libpq SNI and current libpq defaults `sslsni=1`.[^libpq-sni] But the normal PostgreSQL flow first sends an eight-byte `SSLRequest`; only after the server returns `S` does it send ClientHello.[^postgres-protocol] Libpq says an SSL-aware proxy needs `sslnegotiation=direct` unless it understands that handshake; `direct` arrived in PostgreSQL 17, requires `sslmode=require` or stronger, and requires the `postgresql` ALPN protocol. Thus it is an explicit PG17+ connection-string/server opt-in, not automatic routing for the PG14 client. |
| PostgreSQL through `l4postgres` | **Protocol-aware, but not transparent SNI passthrough.** | The actual `postgres` matcher recognizes `SSLRequest`, and `postgres_tls` returns `S` so a following L4 TLS handler can terminate the ClientHello.[^caddy-postgres] Its upstream documentation says proxy integration for re-originating classic PostgreSQL TLS is still a follow-up. It can instead route after termination using PostgreSQL startup fields, which is policy/configuration rather than name-derived auto-exposure. |
| `redis-cli` | **Yes, when explicit.** | Upstream `redis-cli` supports `--tls` and `--sni <host>`; use both and make the SNI hostname the routing name.[^redis-cli] `--tls` alone is insufficient evidence that a given Redis client sends the desired SNI. |
| MySQL `mysql` client | **No, not through a generic first-byte TLS/SNI matcher.** | Current MySQL supports opt-in client-side SNI via `--tls-sni-servername` / `MYSQL_OPT_TLS_SNI_SERVERNAME`.[^mysql-sni] But its protocol has the server send the initial handshake before the client may send its SSL connection request.[^mysql-sni] Caddy-L4 has no MySQL preamble module, so it cannot reach that later ClientHello to select a backend. |
| `mongosh --tls` with a hostname | **Yes for current mongosh's Node driver, subject to normal TLS setup.** | Mongosh uses the upstream Node driver. That driver sets TLS `servername` to a non-IP `host` when unset, then calls `tls.connect()` for TLS.[^mongosh-sni] This is a direct TLS handshake; an IP URI suppresses that default. |
| Plaintext Redis/Postgres/MySQL, or a STARTTLS-style upgrade | **No.** | There is no SNI and no universal hostname field for the gateway to inspect. PostgreSQL and MySQL demonstrate why a TLS upgrade after protocol bytes needs a protocol-specific handler. |

For the cooperative direct-TLS subset, Caddy-L4 does have a genuinely compact shape: its upstream dynamic-upstream example proxies `{l4.tls.server_name}:443` (or an SNI-regexp capture), so a bridge DNS view and a fixed port can produce one route for many instances.[^caddy-dynamic] The port still has to be fixed or encoded/captured in the name, and the certificate-depth issue above remains. A layer4 listener sharing Caddy's HTTPS port must be a listener wrapper, not a second process binding `:443`; otherwise it collides with the HTTP app.[^caddy-combining]

So Caddy-L4 is a narrowly useful future enhancement for named, direct-TLS workloads. It should be a separately tested opt-in, not the substrate for arbitrary agent services. PostgreSQL's preliminary `SSLRequest` is handled upstream, but its practical route requires TLS termination and changes the upstream TLS contract. That is the opposite of zero configuration.

## Cloudflared TCP published applications

Cloudflare documents arbitrary TCP as a tunnel ingress such as `tcp://localhost:7870`, protected by an Access policy.[^access-tcp] The client-side command creates a localhost listener; the application then connects to that listener, and `cloudflared` opens a browser for SSO when needed. It is a sound externally protected endpoint for a deliberately named database, but carries client-side friction that SSH does not eliminate.

A wildcard does not make an origin automatic. Cloudflared's own ingress matcher accepts `*.example.com` and routes every matching hostname to the **same** configured service.[^cloudflared-wildcard] Cloudflare Access supports wildcard application domains as well.[^access-wildcard] Therefore one wildcard DNS record, wildcard Access application, and `*.pascal… → tcp://caddy:PORT` rule are technically possible. They still provide only one fixed origin port; the outer Cloudflare hostname is not translated into an arbitrary instance/port. A second router—such as the constrained Caddy-L4 design above—must do that work, and must have a usable protocol routing key.

## WARP private-network routing

This is the one candidate that changes the question from “how does a proxy select a service?” to “can the client route to the bridge?” Cloudflare documents private-network routes as exposing both HTTP and non-HTTP resources, and says WARP sends a connection to the routed IP/hostname through Cloudflare and down the tunnel.[^cloudflare-private-network] The documented CIDR setup is:

1. Enable WARP routing for the existing tunnel and add the Incus bridge CIDR route. The tunnel connector needs an L3 route to that bridge; placing `cloudflared` in Docker must not accidentally remove that reachability.
2. Enroll the Mac and iPhone Cloudflare One Clients. Cloudflare documents browser/CLI enrollment for macOS and URL/QR enrollment for iOS.[^warp-enrollment] The existing `warp_login` Access application supplies the right policy boundary for this.
3. Add only the bridge CIDR to an **Include** split-tunnel profile, or carefully subtract it from the default private-range exclusions. Cloudflare notes that RFC1918 traffic is excluded by default, so this step is required.[^warp-cidr]
4. Enable Gateway TCP (and UDP if wanted), then place a high-priority admin allow rule ahead of a catch-all block for the bridge CIDR. By default, every enrolled device can connect to a routed private network; Cloudflare recommends Gateway filtering by identity/device posture.[^warp-cidr]
5. Provide stable private names only as a usability layer: Cloudflare supports private DNS, but direct IP plus port already proves the no-per-service property.[^warp-cidr]

The pinned provider is Cloudflare v4.52.7. Its deprecated legacy `cloudflare_tunnel_route`, `cloudflare_tunnel_virtual_network`, and `cloudflare_split_tunnel` resources cover the route, an overlapping-CIDR virtual network if needed, and split-tunnel state; v4 also supplies the `zero_trust_*` aliases carried forward by the current provider.[^tf-v4-split][^tf-v5-route] This is a provider upgrade/migration consideration, not a reason to make state manual.

### Being on the home LAN

An isolated bridge CIDR prevents the documented address-overlap failure. With WARP connected and the bridge CIDR included, a home-LAN device will deliberately hairpin that destination through Cloudflare and back to pod042; it remains functional but now depends on the WARP/tunnel path. With WARP disconnected, the proposed router route gives the direct local path. Do not assume a split-tunnel profile dynamically prefers local routing when at home: validate route precedence, reconnect behavior, and iPhone behavior in a spike before promising that ergonomic refinement.

## Incus and SSH baseline

Incus network forwards are first-class on managed bridge networks. A forward can assign a default target address for all traffic, or port map TCP/UDP; it therefore can expose every port of one instance behind one address.[^incus-forward] A proxy device is attached to an instance and forwards declared listen/connect endpoints; it supports TCP, UDP, and Unix sockets and can NAT to a dynamically addressed instance.[^incus-proxy] Both are useful implementation tools, especially the one-forward-per-instance shape, but neither is a Cloudflare Access boundary and neither eliminates instance lifecycle state.

SSH remains the immediate answer because it is universal and already has a chezmoi-managed configuration surface. For example, one foreground/background session can be `ssh -N -L 5432:10.42.0.17:5432 pod042`, then `psql` targets `localhost:5432`; a `ProxyJump` target can make the SSH hop itself transparent. OpenSSH specifies that `LocalForward` transports a local TCP listener to a remote host/port, while `ProxyJump` makes the SSH connection through the jump host.[^openssh] Its cost is honest: select a port and keep a session alive for each ad-hoc service.

## Recommended shape to take to the map writer

Keep **SSH forwarding as the immediately usable baseline**. Do not make Caddy-L4 or published `cloudflared access tcp` the generic raw-TCP plane: their routing works only for a subset of TLS clients and either needs per-service origin state or an additional fragile router.

For the desired near-zero configuration shape, investigate **one admin-only L3 route to the distinct Incus bridge CIDR for local devices, paired with a WARP CIDR route plus default-deny Gateway policy for remote devices**. Both paths then address the same instance IP and arbitrary port; agents only start the service. The required durable state is per network, device, and instance-address/DNS lifecycle—not per service. Incus whole-address forwards are a viable alternative if router routing is unacceptable, but add one object per instance and should not be confused with free exposure.

This is a recommendation to spike, not the final platform decision. The spike should prove: a Mac and iPhone reach plaintext TCP, direct TLS, PostgreSQL, and UDP where wanted; WARP works away from home and on the home LAN; a worker's removal revokes reachability; and Gateway denies a non-admin enrolled device. Only then decide whether the local L3 route and WARP profile become declared platform state.

## Primary sources

[^caddy-l4]: [mholt/caddy-l4 README](https://github.com/mholt/caddy-l4/blob/master/README.md)
[^caddy-modules]: [mholt/caddy-l4 module tree](https://github.com/mholt/caddy-l4/tree/master/modules)
[^caddy-cloudflare-image]: [CaddyBuilds/caddy-cloudflare Dockerfile](https://github.com/CaddyBuilds/caddy-cloudflare/blob/main/Dockerfile)
[^wildcard-depth]: [Caddy `tls` directive: DNS challenge enables wildcard certificates](https://caddyserver.com/docs/caddyfile/directives/tls) and [RFC 6125 §6.4.3](https://www.rfc-editor.org/rfc/rfc6125#section-6.4.3)
[^caddy-dynamic]: [Caddy-L4 TLS SNI dynamic upstream example](https://github.com/mholt/caddy-l4/blob/master/docs/examples/tls_sni_dynamic_upstreams.md)
[^caddy-combining]: [Caddy-L4 combining-apps example](https://github.com/mholt/caddy-l4/blob/master/docs/examples/combining_apps.md)
[^caddy-postgres]: [Caddy-L4 PostgreSQL TLS handler](https://github.com/mholt/caddy-l4/blob/master/docs/handlers/postgres_tls.md) and [PostgreSQL matcher](https://github.com/mholt/caddy-l4/blob/master/modules/l4postgres/matcher.go)
[^libpq-sni]: [PostgreSQL 14 release notes](https://www.postgresql.org/docs/release/14.0/) and [libpq connection parameters](https://www.postgresql.org/docs/current/libpq-connect.html)
[^postgres-protocol]: [PostgreSQL protocol flow: SSL session encryption](https://www.postgresql.org/docs/14/protocol-flow.html)
[^redis-cli]: [Redis CLI source](https://github.com/redis/redis/blob/unstable/src/redis-cli.c) and [Redis CLI documentation](https://redis.io/docs/latest/develop/tools/cli/)
[^mysql-sni]: [MySQL's upstream SNI feature record](https://bugs.mysql.com/bug.php?id=84849)
[^mongosh-sni]: [MongoDB Node driver TLS connection code](https://github.com/mongodb/node-mongodb-native/blob/main/src/cmap/connect.ts) and [mongosh Node-driver service provider](https://github.com/mongodb-js/mongosh/tree/main/packages/service-provider-node-driver)
[^access-tcp]: [Cloudflare Access arbitrary TCP](https://developers.cloudflare.com/cloudflare-one/applications/non-http/arbitrary-tcp/)
[^cloudflared-wildcard]: [cloudflared ingress hostname matching](https://github.com/cloudflare/cloudflared/blob/master/ingress/ingress.go)
[^access-wildcard]: [Cloudflare's Access wildcard application announcement](https://blog.cloudflare.com/access-wildcard-and-multi-hostname/)
[^cloudflare-private-network]: [Cloudflare private networks](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/private-net/) and [Connect with cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/private-net/cloudflared/)
[^warp-enrollment]: [Cloudflare One Client manual deployment](https://developers.cloudflare.com/cloudflare-one/connections/connect-devices/warp/deployment/manual-deployment/)
[^warp-cidr]: [Cloudflare: connect an IP/CIDR](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/private-net/cloudflared/connect-cidr/)
[^tf-v4-split]: [Cloudflare provider v4.52.7 resource registration](https://github.com/cloudflare/terraform-provider-cloudflare/blob/v4.52.7/internal/sdkv2provider/provider.go), [`cloudflare_split_tunnel`](https://registry.terraform.io/providers/cloudflare/cloudflare/4.52.7/docs/resources/split_tunnel), and [virtual network](https://registry.terraform.io/providers/cloudflare/cloudflare/4.52.7/docs/resources/tunnel_virtual_network)
[^tf-v5-route]: [Cloudflare provider `cloudflare_zero_trust_tunnel_cloudflared_route`](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/zero_trust_tunnel_cloudflared_route)
[^incus-forward]: [Incus network forwards](https://linuxcontainers.org/incus/docs/main/howto/network_forwards/)
[^incus-proxy]: [Incus proxy devices](https://linuxcontainers.org/incus/docs/main/reference/devices_proxy/)
[^openssh]: [OpenSSH `ssh_config(5)`](https://man.openbsd.org/ssh_config)
