# Clawdbot Gateway for TrueNAS
# Based on: https://github.com/clawdbot/clawdbot/blob/main/docs/platforms/hetzner.md
#
# To add skills that require external binaries, add RUN commands below.
# Example:
#   RUN curl -L https://github.com/steipete/gog/releases/latest/download/gog_Linux_x86_64.tar.gz \
#     | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog

FROM node:22-bookworm

# Install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    socat \
    && rm -rf /var/lib/apt/lists/*

# === Add skill binaries here ===
# Uncomment and add binaries needed by your skills

# Gmail CLI (for gog skill)
# RUN curl -L https://github.com/steipete/gog/releases/latest/download/gog_Linux_x86_64.tar.gz \
#   | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog

# Google Places CLI (for goplaces skill)
# RUN curl -L https://github.com/steipete/goplaces/releases/latest/download/goplaces_Linux_x86_64.tar.gz \
#   | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/goplaces

# WhatsApp CLI (for wacli skill - alternative to Baileys)
# RUN curl -L https://github.com/steipete/wacli/releases/latest/download/wacli_Linux_x86_64.tar.gz \
#   | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/wacli

# GitHub CLI (for github skill)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y gh && rm -rf /var/lib/apt/lists/*

# Docker CLI (for librarian skill - spawning sandbox containers)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y docker-ce-cli && rm -rf /var/lib/apt/lists/*

# === End skill binaries ===

WORKDIR /app

# Clone Clawdbot source
ARG CLAWDBOT_VERSION=main
RUN git clone --depth 1 --branch ${CLAWDBOT_VERSION} https://github.com/clawdbot/clawdbot.git . \
    && rm -rf .git

# Install dependencies and build
RUN corepack enable
RUN pnpm install --frozen-lockfile
RUN pnpm build
RUN pnpm ui:install || true
RUN pnpm ui:build || true

# Create non-root user
RUN useradd -m -u 1000 node || true
RUN chown -R 1000:1000 /app

USER node
ENV NODE_ENV=production
ENV PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

EXPOSE 18789 18790

CMD ["node", "dist/index.js"]
