# Clawdbot on TrueNAS

Deploy [Clawdbot](https://github.com/clawdbot/clawdbot) as a Docker container on TrueNAS for 24/7 AI assistant access via WhatsApp, Telegram, Discord, Slack, Signal, and WebChat.

## Prerequisites

- TrueNAS with Docker support
- `personal` macvlan network configured (192.168.6.0/24 range)
- SSH access to TrueNAS

## Quick Start

### 1. Deploy via Ansible

```bash
uv run poe truenas -t clawdbot
```

Or deploy all stacks:

```bash
uv run poe truenas
```

### 2. Initial Onboarding (Manual - One Time)

SSH into TrueNAS and run the onboarding wizard:

```bash
cd /mnt/performance/docker/stacks/clawdbot

# Run onboarding (interactive)
docker compose run --rm clawdbot-gateway node dist/index.js onboard --no-install-daemon
```

When prompted:
- **Gateway bind**: `lan`
- **Gateway auth**: `token`
- **Gateway token**: (save this securely - you'll need it to access WebChat)
- **Tailscale exposure**: `Off` (unless you want remote access via Tailscale)
- **Install daemon**: `No` (Docker handles this)

### 3. Set Up Messaging Providers (Manual)

#### WhatsApp (QR Code Pairing)

```bash
docker compose run --rm clawdbot-gateway node dist/index.js providers login
```

Scan the QR code with WhatsApp on your phone.

#### Telegram Bot

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your bot token
3. Add the provider:

```bash
docker compose run --rm clawdbot-gateway node dist/index.js providers add --provider telegram --token YOUR_BOT_TOKEN
```

#### Discord Bot

1. Create a Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a bot and get the token
3. Add the provider:

```bash
docker compose run --rm clawdbot-gateway node dist/index.js providers add --provider discord --token YOUR_BOT_TOKEN
```

#### Slack Bot

See [Clawdbot Slack docs](https://docs.clawd.bot/providers/slack).

#### Signal

```bash
docker compose run --rm clawdbot-gateway node dist/index.js providers add --provider signal
```

### 4. Configure Model Authentication

Set up Claude API access:

```bash
docker compose run --rm clawdbot-gateway node dist/index.js auth
```

### 5. Start the Gateway

After onboarding, restart the container to apply config:

```bash
docker compose up -d clawdbot-gateway
```

## Access

### WebChat UI

Open in browser: `http://192.168.6.238:18789/`

Enter your gateway token when prompted.

### Health Check

```bash
docker compose exec clawdbot-gateway node dist/index.js health --token YOUR_TOKEN
```

### Logs

```bash
docker compose logs -f clawdbot-gateway
```

## Adding Skills with External Binaries

Skills that require external CLIs (like `gog` for Gmail) need those binaries baked into the Docker image. Edit `Dockerfile` to add them:

```dockerfile
# Gmail CLI
RUN curl -L https://github.com/steipete/gog/releases/latest/download/gog_Linux_x86_64.tar.gz \
  | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog
```

Then rebuild:

```bash
docker compose build --no-cache
docker compose up -d
```

## Remote Access (Optional)

### Via SSH Tunnel

From your laptop:

```bash
ssh -N -L 18789:192.168.6.238:18789 user@truenas
```

Then access WebChat at `http://127.0.0.1:18789/`

### Via Tailscale

If your NAS is on Tailscale, access directly via the Tailscale IP.

### Via Cloudflare Tunnel

Add to your `cloudflared` config to expose externally (with authentication).

## Persistent Data

| Path | Purpose |
|------|---------|
| `/mnt/performance/docker/clawdbot/clawdbot-gateway/.clawdbot` | Config, tokens, provider sessions |
| `/mnt/performance/docker/clawdbot/clawdbot-gateway/clawd` | Agent workspace |

## What Works on NAS

- WhatsApp, Telegram, Discord, Slack, Signal, MS Teams
- WebChat UI
- All cross-platform skills (~40 skills)
- Browser automation (headless Chromium)
- Scheduled tasks/cron
- Agent coding tasks
- **Librarian skill** (sandboxed coding environments)

## Librarian Skill - Sandboxed Coding Agents

The librarian skill spawns isolated Docker containers with OpenCode to work on any git repository. Containers persist for follow-up questions in the same session.

### Setup

1. Create `.env` file with API keys:

```bash
cd /mnt/performance/docker/stacks/clawdbot
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
EOF
```

2. Build the librarian sandbox image:

```bash
docker build -t clawdbot-librarian:local -f Dockerfile.librarian .
```

3. Restart gateway to pick up the env vars:

```bash
docker compose up -d
```

### Usage (via Clawdbot chat)

Ask Clawdbot to use the librarian:

```
"Use librarian to clone https://github.com/fastapi/fastapi and review the dependency injection system"
```

Or be explicit:

```
"librarian spawn --repo https://github.com/user/repo --task 'Add unit tests for auth module'"
```

### Commands

| Command | Description |
|---------|-------------|
| `librarian spawn --repo <url> --task "<task>"` | Create new sandbox |
| `librarian ask --session <id> "<question>"` | Follow-up in existing sandbox |
| `librarian logs --session <id>` | View OpenCode output |
| `librarian status --session <id>` | Check sandbox state |
| `librarian list` | List all active sandboxes |
| `librarian kill --session <id>` | Destroy sandbox |

### Session Persistence

- Each sandbox gets a unique session ID (e.g., `abc123`)
- Containers persist until explicitly killed
- Follow-up questions go to the same OpenCode instance
- Changes, commits, files all remain in the container

### Example Workflow

```bash
# Start a coding task
librarian spawn \
  --repo https://github.com/org/api \
  --task "Review security of auth endpoints"
# Returns: Session ID: x7k2m9

# Check progress
librarian logs --session x7k2m9

# Ask follow-up
librarian ask --session x7k2m9 "Now implement fixes for the top 3 issues"

# Get the commit
librarian ask --session x7k2m9 "Commit changes and show the diff"

# Clean up
librarian kill --session x7k2m9
```

### Resource Limits

- Memory: 2GB per sandbox
- CPU: 2 cores per sandbox
- Storage: Ephemeral (lost on kill)

See `skills/librarian/SKILL.md` for full documentation

## What Doesn't Work on NAS

- iMessage (requires macOS)
- Voice Wake / Push-to-talk (requires macOS audio)
- Apple-specific skills (Notes, Reminders, Bear, Things)
- macOS menu bar app

## Troubleshooting

### Container won't start

Check logs:

```bash
docker compose logs clawdbot-gateway
```

### WhatsApp session expired

Re-authenticate:

```bash
docker compose run --rm clawdbot-gateway node dist/index.js providers login
docker compose restart clawdbot-gateway
```

### Can't access WebChat

1. Verify container is running: `docker compose ps`
2. Check gateway is listening: `docker compose logs | grep listening`
3. Verify network connectivity to 192.168.6.238:18789

## Updating Clawdbot

```bash
cd /mnt/performance/docker/stacks/clawdbot
docker compose build --no-cache --build-arg CLAWDBOT_VERSION=main
docker compose up -d
```

Or specify a version/tag:

```bash
docker compose build --no-cache --build-arg CLAWDBOT_VERSION=v1.0.0
```

## References

- [Clawdbot GitHub](https://github.com/clawdbot/clawdbot)
- [Clawdbot Docs](https://docs.clawd.bot/)
- [Hetzner VPS Guide](https://github.com/clawdbot/clawdbot/blob/main/docs/platforms/hetzner.md) (basis for this setup)
