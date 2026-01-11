#!/bin/bash
set -euo pipefail

# Librarian Sandbox Entrypoint
# Clones repo, starts tmux session, runs OpenCode with task

REPO="${LIBRARIAN_REPO:-}"
BRANCH="${LIBRARIAN_BRANCH:-}"
TASK="${LIBRARIAN_TASK:-}"
SESSION_NAME="${LIBRARIAN_SESSION:-main}"
MODEL="${LIBRARIAN_MODEL:-claude-sonnet-4-20250514}"

# Validate required vars
if [[ -z "$REPO" ]]; then
    echo "ERROR: LIBRARIAN_REPO is required" >&2
    exit 1
fi

if [[ -z "$TASK" ]]; then
    echo "ERROR: LIBRARIAN_TASK is required" >&2
    exit 1
fi

echo "==> Cloning repository: $REPO"
cd /workspace

# Clone the repo
if [[ -n "$BRANCH" ]]; then
    git clone --depth 1 --branch "$BRANCH" "$REPO" repo 2>&1 || git clone "$REPO" repo
else
    git clone --depth 1 "$REPO" repo 2>&1
fi

cd repo

# Show repo info
echo "==> Repository cloned to /workspace/repo"
echo "    Branch: $(git branch --show-current)"
echo "    Commit: $(git rev-parse --short HEAD)"
echo ""

# Configure git for commits
git config user.email "librarian@clawdbot.local"
git config user.name "Librarian (Clawdbot)"

# Start tmux session
echo "==> Starting tmux session: $SESSION_NAME"
tmux new-session -d -s "$SESSION_NAME" -c /workspace/repo

# Send the OpenCode command to tmux
echo "==> Running OpenCode with task..."
echo "    Model: $MODEL"
echo "    Task: $TASK"
echo ""

# Use opencode in print mode for the initial task
# The tmux session allows follow-up interaction
tmux send-keys -t "$SESSION_NAME" "opencode --model $MODEL --print \"$TASK\"" Enter

# Keep container alive - tmux server runs in foreground
echo "==> Sandbox ready. Container will stay running for follow-up commands."
echo "    Session: $SESSION_NAME"
echo "    Workspace: /workspace/repo"
echo ""

# Wait for tmux session (keeps container alive)
# This blocks until the tmux server exits
exec tmux attach-session -t "$SESSION_NAME" 2>/dev/null || tail -f /dev/null
