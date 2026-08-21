# Alerting platform landscape

The Bunker needs two distinct services. A **push channel** carries an event already known to be bad: restic failure, a zed/smartd event, a failed health probe, or an agent report. A **dead-man monitor** owns an expected schedule outside the Bunker and alerts when a success check-in never arrives. A push channel alone cannot detect a job that never starts.

This research evaluates only those two roles. It does not select the stack; [ticket 12](../tickets/12-alerting-decision.md) owns the decision and the required spike.

## Constraints that change the answer

A local notification service can carry a local failure, but it cannot observe the Bunker's power, kernel, network, or its own process failure. Put the dead-man state on a hosted service, or on a separately operated machine. For this single-host build, self-hosting the monitor on the Bunker defeats the case that matters most.

Every surveyed producer can use a small HTTP request. That is the right common denominator for `systemd` services, timers, cron, zed hooks, smartd hooks, and agent scripts: give each producer a secret URL through systemd credentials, make an explicit failure non-zero, and do not turn notification failure into a successful backup or scrub. The later spike should prove the exact systemd wrapper, including its network-failure behavior.

## Capability comparison

| Candidate | Role and delivery | Bunker-down coverage | iPhone and sender ergonomics | Operational cost |
| --- | --- | --- | --- | --- |
| [Hark](https://hark.ryan.ceo/docs) | Hosted webhook-to-iPhone channel; one-shot notifications, approvals, and Live Activities | Only when paired with an external monitor | Purpose-built iPhone app; JSON `POST` to a secret URL; `harkctl` is also for coding agents | No server to run. Free: one phone / 10,000 notifications per month; Pro: $8/month. Public docs describe hosted use, not self-hosting. |
| [Pushover](https://pushover.net/api) | Hosted push channel | Only when paired with an external monitor | HTTPS form/JSON `POST`; its iOS client explicitly uses APNs for instant delivery | No server to run; $4.99 one-time individual licence per platform, then 10,000 messages/month included. |
| [ntfy](https://docs.ntfy.sh/publish/) hosted | Hosted HTTP pub/sub push channel | Yes for a scheduled heartbeat sent to hosted ntfy, but its built-in dead-man pattern is a custom timer rather than a monitoring service | Native iOS app; plain `PUT`/`POST`, titles, priorities, tags, actions, and scheduled messages | Free public service has unreserved topics; paid hosted plans are $6/$12/$25 monthly. |
| [ntfy](https://docs.ntfy.sh/install/) self-hosted | Self-hosted HTTP pub/sub push channel | No when it runs on the Bunker | Same simple HTTP publisher. For instant iOS delivery, the server must forward poll requests to an upstream APNs-connected ntfy server. | A binary/container, state, TLS/access control, upgrades, backups, and an external dependency for iOS instant delivery. |
| [Gotify](https://gotify.net/docs/pushmsg) | Self-hosted REST/WebSocket message server | No when local | `curl -F` with an application token is simple. The official project documents an Android app, not an iOS client. | Small server with persistent state, TLS, upgrades, and no first-party iPhone path. |
| [Healthchecks.io](https://healthchecks.io/docs/) hosted | Scheduled-task/dead-man monitor | Yes: expected check-ins and state live off-host | A `GET` ping URL, with `/start`, `/fail`, or an exit-status suffix; integrations send the alert | Hobbyist tier: 20 checks free; Business: 100 checks for $20/month. No host service to maintain. |
| [Healthchecks.io](https://healthchecks.io/docs/self_hosted/) self-hosted | Same dead-man model | No when local | Same ping protocol | Its documented production components include Django, PostgreSQL or MySQL, SMTP, a durable `sendalerts` process, and database backups. Excess machinery for this single host. |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) push monitor | Self-hosted uptime dashboard and heartbeat monitor | No when local | A generated Push URL takes heartbeats; it can notify through Pushover, Gotify, Discord, and 90+ services | A Docker/Node service, persistent local data, UI configuration, updates, and its own availability to monitor. Useful only if a dashboard is wanted or it lives elsewhere. |
| [Apprise](https://github.com/caronc/apprise) | CLI/library fan-out to many notification backends | No; it is not a monitor | One command and a declarative config can route to Discord, Gotify, ntfy, Pushover, and others | Adds Python, endpoint configuration, and another failure boundary. Useful only after there is a real multi-destination requirement. |
| [Discord webhook](https://discord.com/developers/docs/resources/webhook) | Channel-message transport | No | Simple credential-bearing webhook `POST`; Discord handles client delivery | No new service, but no task schedule, missed-run state, alert lifecycle, or host-down detection. |

Prices and limits are the published figures accessed 2026-08-19. They are not a total cost of ownership: the maintenance column is the relevant cost for this build.

## Findings by role

### Push channels

**Hark** is the most direct fit for iPhone-first agent reports. Its [Notification API](https://hark.ryan.ceo/docs) accepts a secret webhook URL and returns the number of push requests accepted by Expo; that count is not a device-read or on-device-delivery acknowledgement. It has idempotency keys, an iPhone inbox, and optional approval/yes-no/text prompts and Live Activities. Those prompt features are useful for a resident coding agent, while zed, smartd, and restic need only a one-shot JSON `POST`. Its free tier covers one iPhone and 10,000 events/month; [Pro](https://hark.ryan.ceo/pricing) costs $8/month for multiple phones, routing, interaction, and higher limits. The tradeoff is accepting a small hosted service as the sole push provider. Ticket 12 should test a failure, a recovery, an agent approval, and a phone that has been idle.

**Pushover** is the deliberately narrow hosted alternative. Its [Message API](https://pushover.net/api#messages) is a required HTTPS `POST`, supports priority, sound, acknowledgement-oriented emergency messages, and returns HTTP failures for invalid input. Its [iOS client](https://pushover.net/clients) uses APNs for instant delivery. An individual iPhone/iPad licence is [a $4.99 one-time purchase](https://pushover.net/pricing), with no individual subscription and 10,000 messages/month. It is a clean, direct endpoint for all Bunker producers, but it has none of Hark's agent interaction or Live Activity surface.

**ntfy** is the FOSS HTTP alternative. The [hosted service](https://ntfy.sh/) accepts a simple `curl -d` publish; the publisher can set priority, tags, title, actions, and a scheduled delivery. The [iOS app](https://docs.ntfy.sh/subscribe/phone/) can subscribe to hosted or self-hosted topics. A hosted ntfy topic can implement a dead-man switch by continually moving a scheduled message into the future; the [official example](https://docs.ntfy.sh/publish/#updating-scheduled-notifications) shows that exact pattern. It is viable, but it makes the owner responsible for a correct repeating/update timer and offers less explicit task history and schedule configuration than Healthchecks.

Self-hosting ntfy does not improve Bunker-outage coverage when the server is on the Bunker. It also does not make iOS delivery entirely local: [ntfy's configuration documentation](https://docs.ntfy.sh/config/#ios-instant-notifications) requires a self-hosted server to forward poll requests to an APNs-connected upstream for instant iOS notifications. It is a reasonable future service if private local pub/sub becomes useful, not the simple answer to this ticket.

**Gotify** is similarly pleasant to publish to—its [official curl example](https://gotify.net/docs/pushmsg) needs only the application token, title, message, and priority—but it is a poor fit for an iPhone-first operator. The [official project site](https://gotify.net/) lists an Android client and the server repository lists Android as its mobile app. Third-party iOS arrangements are outside this primary-source survey and add an extra relay to operate.

A bare **Discord webhook** remains a useful comparison baseline. Discord describes webhooks as a low-effort way to post a message to a channel without a bot user. Its execute endpoint can format a message, but it has no model of an expected run, late run, down-to-up transition, or escalation. Code must create those semantics itself, and the channel is not a dedicated incident/phone-delivery contract. Retaining Discord as a secondary observability copy is possible, but it should not be the dead-man mechanism.

### Dead-man monitors

Hosted **Healthchecks.io** is purpose-built for the backup case. It stays quiet while pings arrive, transitions a check from late to down after its schedule and grace period, then sends its configured integrations. A job can ping `.../start`, normal success, or `.../<exit-status>`: [a start with no later success](https://healthchecks.io/docs/measuring_script_run_time/) becomes down after the grace period, while [a non-zero exit status](https://healthchecks.io/docs/signaling_failures/) reports failure immediately. That covers both restic failure and the more dangerous "timer never ran" case with the same check.

The hosted Hobbyist plan's 20 checks is enough for the known workload: a Bunker-alive heartbeat, restic, scrub, SMART test, service probes, and agent loop. It can route its down and recovery transitions through a push provider. In particular, Healthchecks' own [webhook integration source](https://github.com/healthchecks/healthchecks/blob/master/hc/integrations/webhook/templates/webhook_form.html) documents independent up/down `POST`/`PUT` requests, arbitrary request bodies and headers, and retries. That can produce Hark's JSON webhook directly; the spike must prove the final payload and recovery notification.

Self-hosted Healthchecks and **Uptime Kuma Push monitors** both provide the right heartbeat concept but the wrong placement if they live on the Bunker. Healthchecks explicitly warns that a production instance needs running alert dispatch and ongoing database maintenance. Uptime Kuma's [source](https://github.com/louislam/uptime-kuma/blob/master/server/model/monitor.js) marks a Push monitor down when no heartbeat arrives in its configured window, and its [official example](https://github.com/louislam/uptime-kuma/tree/master/extra/push-examples/bash-curl) is just a curl loop. It can become attractive on a separately managed node if an uptime dashboard and HTTP/TCP/DNS checks are subsequently wanted. On this host it is an additional container and UI that disappears with the system it is supposed to report on.

### Fan-out

**Apprise** deliberately normalizes the APIs of a large list of services and its CLI can load URLs from a config file and send one notification to several destinations. That makes it a good escape hatch if the selected standard must later deliver to both a phone channel and Discord/email. It does not determine whether the job ran, and it makes every producer depend on local Python/configuration plus the fan-out's failure behavior. A single chosen HTTP endpoint is simpler today; introduce Apprise only when the second destination is real.

## Shortlist for the follow-up decision

These are the viable options for ticket 12, not a final selection.

1. **Hark + hosted Healthchecks.io — recommended pairing to spike.** Hark gives the owner a native iPhone channel designed for webhooks and agent interaction, while Healthchecks owns the schedule off-host and can post Hark down/up events. It has no Bunker-resident service and both free tiers cover the expected scale. Tradeoff: two small hosted services and Hark is iPhone-only; prove the exact Healthchecks-to-Hark payload, failure/recovery behavior, idle-phone delivery, and an agent approval before adopting it.
2. **Pushover + hosted Healthchecks.io — conservative iOS pairing.** Same external dead-man boundary and equally straightforward producer calls, with explicit APNs delivery and a small one-time phone licence. It trades away Hark's agent approvals, Live Activities, and richer agent-facing surface for a narrower conventional push API.
3. **Hosted ntfy + hosted Healthchecks.io — FOSS HTTP pairing.** Keep ntfy hosted so a Bunker outage cannot take down the channel, and let Healthchecks provide the first-class missed-run state. This is the most flexible self-hosting path later, but self-hosting now would add maintenance and compromise the outage case; iOS delivery behavior and notification policy need the same phone spike as the other options.

All three should use the same producer contract: explicit failure event to the push channel where prompt reporting matters, plus a Healthchecks start/success/failure check-in for scheduled jobs. zed and smartd can emit direct event pushes; a periodic host/service probe can be represented as a Healthchecks heartbeat so its silence is also visible. The ticket 12 spike should verify that the notification wrapper fails loudly enough to leave diagnostics, without masking the original restic, ZFS, SMART, or service failure.

## Primary sources

- [ntfy documentation and hosted pricing](https://ntfy.sh/), [publish API](https://docs.ntfy.sh/publish/), [iOS/self-hosting configuration](https://docs.ntfy.sh/config/#ios-instant-notifications)
- [Gotify documentation](https://gotify.net/docs/), [server repository](https://github.com/gotify/server)
- [Pushover Message API](https://pushover.net/api), [iOS client](https://pushover.net/clients), [pricing](https://pushover.net/pricing)
- [Hark API documentation](https://hark.ryan.ceo/docs), [pricing](https://hark.ryan.ceo/pricing)
- [Healthchecks.io documentation](https://healthchecks.io/docs/), [pricing](https://healthchecks.io/pricing/), [self-hosting documentation](https://healthchecks.io/docs/self_hosted/), [source](https://github.com/healthchecks/healthchecks)
- [Uptime Kuma repository](https://github.com/louislam/uptime-kuma)
- [Apprise repository](https://github.com/caronc/apprise)
- [Discord webhook API](https://discord.com/developers/docs/resources/webhook)
