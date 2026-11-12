# Tailscale

`terraform/tailscale/` owns the tailnet: the policy file in `policy.hujson`, DNS, tailnet settings, contacts, the `amp-orb` OAuth client, and the key expiry and subnet routes of the unattended machines. Edit the policy there, not in the admin console. It authenticates with the all-scope OAuth client in 1Password, which stays unmanaged so an apply can never revoke its own credential. Auth keys, API tokens, and personal devices stay out, since their owners rotate them. Each host's own tags and Tailscale SSH come from its `tailscale up` in the host reconcile.

```sh
mise run tailscale:plan    # tailscale:init and tailscale:apply for init and apply
```
