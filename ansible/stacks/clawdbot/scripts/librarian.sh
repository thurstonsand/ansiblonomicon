#!/bin/bash
set -euo pipefail

# Librarian - Manage sandboxed coding environments
# Usage: librarian.sh <command> [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_IMAGE="${LIBRARIAN_IMAGE:-clawdbot-librarian:local}"
CONTAINER_PREFIX="clawdbot_librarian_"
DEFAULT_MODEL="claude-sonnet-4-20250514"
DEFAULT_MEM="2g"
DEFAULT_CPUS="2"

# Generate random session ID
generate_session_id() {
    head -c 6 /dev/urandom | base64 | tr -dc 'a-z0-9' | head -c 8
}

# Get container name from session ID
container_name() {
    echo "${CONTAINER_PREFIX}${1}"
}

# Check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^$(container_name "$1")$"
}

# Check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^$(container_name "$1")$"
}

# === COMMANDS ===

cmd_spawn() {
    local repo="" branch="" task="" session="" model="$DEFAULT_MODEL"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --repo) repo="$2"; shift 2 ;;
            --branch) branch="$2"; shift 2 ;;
            --task) task="$2"; shift 2 ;;
            --session) session="$2"; shift 2 ;;
            --model) model="$2"; shift 2 ;;
            *) echo "Unknown option: $1" >&2; exit 1 ;;
        esac
    done

    if [[ -z "$repo" ]]; then
        echo "ERROR: --repo is required" >&2
        exit 1
    fi

    if [[ -z "$task" ]]; then
        echo "ERROR: --task is required" >&2
        exit 1
    fi

    # Generate session ID if not provided
    if [[ -z "$session" ]]; then
        session=$(generate_session_id)
    fi

    local cname
    cname=$(container_name "$session")

    # Check if session already exists
    if container_exists "$session"; then
        echo "ERROR: Session '$session' already exists. Use 'librarian ask' for follow-ups or 'librarian kill' first." >&2
        exit 1
    fi

    echo "==> Spawning sandbox: $session"
    echo "    Repo: $repo"
    [[ -n "$branch" ]] && echo "    Branch: $branch"
    echo "    Model: $model"
    echo "    Task: $task"
    echo ""

    # Build image if needed
    if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${SANDBOX_IMAGE}$"; then
        echo "==> Building sandbox image..."
        docker build -t "$SANDBOX_IMAGE" -f "${SCRIPT_DIR}/../Dockerfile.librarian" "${SCRIPT_DIR}/.."
    fi

    # Run the sandbox container
    docker run -d \
        --name "$cname" \
        --memory="$DEFAULT_MEM" \
        --cpus="$DEFAULT_CPUS" \
        -e "LIBRARIAN_REPO=$repo" \
        -e "LIBRARIAN_BRANCH=${branch:-}" \
        -e "LIBRARIAN_TASK=$task" \
        -e "LIBRARIAN_SESSION=main" \
        -e "LIBRARIAN_MODEL=$model" \
        -e "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}" \
        -e "OPENAI_API_KEY=${OPENAI_API_KEY:-}" \
        -e "GITHUB_TOKEN=${GITHUB_TOKEN:-}" \
        "$SANDBOX_IMAGE" \
        > /dev/null

    echo "==> Sandbox started!"
    echo ""
    echo "Session ID: $session"
    echo "Container:  $cname"
    echo ""
    echo "Commands:"
    echo "  librarian logs --session $session        # View OpenCode output"
    echo "  librarian ask --session $session \"...\"  # Send follow-up"
    echo "  librarian status --session $session      # Check status"
    echo "  librarian kill --session $session        # Destroy sandbox"
}

cmd_ask() {
    local session="" question=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session) session="$2"; shift 2 ;;
            *) question="$1"; shift ;;
        esac
    done

    if [[ -z "$session" ]]; then
        echo "ERROR: --session is required" >&2
        exit 1
    fi

    if [[ -z "$question" ]]; then
        echo "ERROR: Question/task is required" >&2
        exit 1
    fi

    if ! container_running "$session"; then
        echo "ERROR: Session '$session' is not running" >&2
        exit 1
    fi

    local cname
    cname=$(container_name "$session")

    echo "==> Sending follow-up to session: $session"
    echo "    Task: $question"
    echo ""

    # Send command to tmux session inside container
    docker exec "$cname" tmux send-keys -t main "opencode --print \"$question\"" Enter

    echo "==> Follow-up sent. Use 'librarian logs --session $session --follow' to watch output."
}

cmd_status() {
    local session=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session) session="$2"; shift 2 ;;
            *) echo "Unknown option: $1" >&2; exit 1 ;;
        esac
    done

    if [[ -z "$session" ]]; then
        echo "ERROR: --session is required" >&2
        exit 1
    fi

    local cname
    cname=$(container_name "$session")

    if ! container_exists "$session"; then
        echo "not_found"
        exit 0
    fi

    if container_running "$session"; then
        # Check if tmux session is active with a running command
        local pane_cmd
        pane_cmd=$(docker exec "$cname" tmux display-message -t main -p '#{pane_current_command}' 2>/dev/null || echo "unknown")

        if [[ "$pane_cmd" == "opencode" ]]; then
            echo "running"
        else
            echo "idle"
        fi
    else
        echo "exited"
    fi
}

cmd_logs() {
    local session="" tail_lines="" follow=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session) session="$2"; shift 2 ;;
            --tail) tail_lines="$2"; shift 2 ;;
            --follow|-f) follow=true; shift ;;
            *) echo "Unknown option: $1" >&2; exit 1 ;;
        esac
    done

    if [[ -z "$session" ]]; then
        echo "ERROR: --session is required" >&2
        exit 1
    fi

    local cname
    cname=$(container_name "$session")

    if ! container_exists "$session"; then
        echo "ERROR: Session '$session' not found" >&2
        exit 1
    fi

    if [[ "$follow" == true ]]; then
        # Stream logs from container
        docker logs -f "$cname" 2>&1
    elif [[ -n "$tail_lines" ]]; then
        docker logs --tail "$tail_lines" "$cname" 2>&1
    else
        # Capture tmux pane output
        if container_running "$session"; then
            docker exec "$cname" tmux capture-pane -t main -p -S -500
        else
            docker logs "$cname" 2>&1
        fi
    fi
}

cmd_list() {
    echo "SESSION_ID        REPO                                          STATUS    CREATED"
    echo "-------------------------------------------------------------------------------"

    docker ps -a --filter "name=${CONTAINER_PREFIX}" --format '{{.Names}}\t{{.Status}}\t{{.CreatedAt}}' | \
    while IFS=$'\t' read -r name status created; do
        session_id="${name#$CONTAINER_PREFIX}"

        # Get repo from container env
        repo=$(docker inspect "$name" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | \
               grep "^LIBRARIAN_REPO=" | cut -d= -f2- | head -1)
        repo="${repo:-unknown}"

        # Truncate repo URL
        if [[ ${#repo} -gt 45 ]]; then
            repo="${repo:0:42}..."
        fi

        # Parse status
        if echo "$status" | grep -q "^Up"; then
            status_short="running"
        else
            status_short="exited"
        fi

        printf "%-17s %-45s %-9s %s\n" "$session_id" "$repo" "$status_short" "$created"
    done
}

cmd_kill() {
    local session="" all=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session) session="$2"; shift 2 ;;
            --all) all=true; shift ;;
            *) echo "Unknown option: $1" >&2; exit 1 ;;
        esac
    done

    if [[ "$all" == true ]]; then
        echo "==> Killing all librarian sandboxes..."
        docker ps -a --filter "name=${CONTAINER_PREFIX}" --format '{{.Names}}' | \
        while read -r name; do
            echo "    Removing: $name"
            docker rm -f "$name" > /dev/null 2>&1 || true
        done
        echo "==> Done."
        exit 0
    fi

    if [[ -z "$session" ]]; then
        echo "ERROR: --session or --all is required" >&2
        exit 1
    fi

    local cname
    cname=$(container_name "$session")

    if ! container_exists "$session"; then
        echo "ERROR: Session '$session' not found" >&2
        exit 1
    fi

    echo "==> Killing sandbox: $session"
    docker rm -f "$cname" > /dev/null
    echo "==> Sandbox destroyed."
}

cmd_help() {
    cat <<EOF
Librarian - Sandboxed Coding Environments

Usage: librarian <command> [options]

Commands:
  spawn     Create a new sandbox with a git repo and task
  ask       Send a follow-up question/task to an existing sandbox
  status    Check sandbox state (running, idle, exited, not_found)
  logs      View OpenCode output from a sandbox
  list      List all active sandboxes
  kill      Destroy a sandbox

Examples:
  librarian spawn --repo https://github.com/user/repo --task "Add tests"
  librarian ask --session abc123 "Now fix the failing tests"
  librarian logs --session abc123 --follow
  librarian kill --session abc123

Environment Variables:
  ANTHROPIC_API_KEY   API key for Claude models (required for OpenCode)
  OPENAI_API_KEY      API key for OpenAI models (optional)
  GITHUB_TOKEN        GitHub token for private repos and pushing (optional)
  LIBRARIAN_IMAGE     Custom sandbox image (default: clawdbot-librarian:local)
EOF
}

# === MAIN ===

case "${1:-help}" in
    spawn) shift; cmd_spawn "$@" ;;
    ask) shift; cmd_ask "$@" ;;
    status) shift; cmd_status "$@" ;;
    logs) shift; cmd_logs "$@" ;;
    list) shift; cmd_list "$@" ;;
    kill) shift; cmd_kill "$@" ;;
    help|--help|-h) cmd_help ;;
    *) echo "Unknown command: $1" >&2; cmd_help; exit 1 ;;
esac
