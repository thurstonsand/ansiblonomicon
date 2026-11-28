---
name: publishing-public-files
description: Publishes files at public URLs. Use for links that should stay available over time or be accessible to other people.
---

# Publishing public files

Run the bundled `scripts/public-file add FILE [NAME]` to publish under `https://thurstons.house/f/` and print the verified URL. Omit `NAME` for a random prefix, or provide a short name such as `wallpaper.jpg`. Existing names are never overwritten.

- Shares expire at the origin after 24 hours by default. Use `add --ttl 2h FILE [NAME]` for a different lifetime or `add --forever FILE [NAME]` to keep a file until manually removed.
- Use `arm URL 2h` to start or reset an existing share's timer, `disarm URL` to cancel expiry, or `remove URL` to take it down now.

Anyone with the URL can open it. If immediate edge removal is requested, use `cloudflare-ops` to purge that exact URL after removing the origin file.
