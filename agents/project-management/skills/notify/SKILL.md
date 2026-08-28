---
name: notify
description: Send a push notification to Thurston's phone. Use when he asks to be notified of something while he is away from the terminal.
---

# Notify

```sh
<skill-dir>/scripts/notify.sh [--url <link>] "<body>"
```

The body carries the event, up to 2000 characters, and may also arrive on stdin. `--url` sets what opens when the notification is tapped, so pass one whenever there is somewhere to go: a PR, a failed CI run, a dashboard.
