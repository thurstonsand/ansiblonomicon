# Containers

Docker plus one compose project per stack under `/etc/ansiblonomicon/containers/<stack>`, each declared as a `[bootstrap.compose.*]` resource in `mise.containers.toml` and ordered after `service:docker`. `finalize.py` fixes up the group memberships that package installation creates. Netdata reaches Docker only through the read-only socket proxy.

## DNS assertion

Docker writes each container's `/etc/resolv.conf` on the host at container **start** and bind-mounts it in; it never revisits the file afterwards. If the host had no nameserver at that moment, the container gets `nameserver 127.0.0.11` with `# NO EXTERNAL NAMESERVERS DEFINED`, the embedded resolver has nothing to forward to, and every external lookup returns SERVFAIL until someone restarts the container. Host-network containers get the same file with no nameserver line at all.

`check.py` asserts the outcome. For each running container it reads that host-side file, then queries its nameservers for `api.github.com` over UDP from inside the container's network namespace until one succeeds. It enters only the network namespace, so the host's Python does the asking and images without a shell or a resolver binary are still covered. Containers on `network_mode: none` are skipped; containers sharing a VPN namespace pass through that namespace's own resolver.

It runs on `mise pod042 containers --check`, at the end of a containers reconciliation, and on demand as `containers:check`.

The ordering that makes this hold at boot belongs to the network capability, not here: see `../network/README.md`.
