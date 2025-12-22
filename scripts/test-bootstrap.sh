#!/bin/bash
set -euo pipefail

# Test bootstrap script in a clean macOS VM using Tart
# Requires: tart, sshpass (brew install cirruslabs/cli/tart cirruslabs/cli/sshpass)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VM_NAME="bootstrap-test"
VM_IMAGE="ghcr.io/cirruslabs/macos-sequoia-vanilla:latest"
VM_USER="admin"
VM_PASS="admin"
BOOT_WAIT=60

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}==>${NC} $1"; }
error() { echo -e "${RED}==>${NC} $1"; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Test the bootstrap script in a clean macOS VM.

Options:
    --reuse             Reuse existing VM instead of creating fresh (default: fresh)
    --uninstall-xcode   Remove Xcode CLI tools before running bootstrap
    --full-brew-bundle  Use full Brewfile instead of minimal test bundle
    --keep-running      Don't stop the VM after test completes
    --interactive       Open VM GUI instead of headless mode
    -h, --help          Show this help message

Examples:
    $(basename "$0")                    # Fresh VM with minimal Brewfile
    $(basename "$0") --reuse            # Quick test with existing VM
    $(basename "$0") --full-brew-bundle # Test with full Brewfile (slow)
    $(basename "$0") --uninstall-xcode  # Test Xcode CLI tools installation
EOF
}

# Parse arguments
FRESH=true
UNINSTALL_XCODE=false
FULL_BREW_BUNDLE=false
KEEP_RUNNING=false
INTERACTIVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --reuse) FRESH=false; shift ;;
        --uninstall-xcode) UNINSTALL_XCODE=true; shift ;;
        --full-brew-bundle) FULL_BREW_BUNDLE=true; shift ;;
        --keep-running) KEEP_RUNNING=true; shift ;;
        --interactive) INTERACTIVE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Check dependencies
check_deps() {
    local missing=()
    command -v tart &>/dev/null || missing+=("tart (brew install cirruslabs/cli/tart)")
    command -v sshpass &>/dev/null || missing+=("sshpass (brew install cirruslabs/cli/sshpass)")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo "  - $dep"
        done
        exit 1
    fi
}

# SSH helper
vm_ssh() {
    sshpass -p "$VM_PASS" ssh -o "StrictHostKeyChecking=no" -o "ConnectTimeout=10" "$VM_USER@$VM_IP" "$@"
}

vm_ssh_sudo() {
    vm_ssh "echo '$VM_PASS' | sudo -S $*"
}

# Wait for VM to be SSH-accessible
wait_for_ssh() {
    log "Waiting for VM to become accessible..."
    local attempts=0
    local max_attempts=30
    
    while [[ $attempts -lt $max_attempts ]]; do
        VM_IP=$(tart ip "$VM_NAME" 2>/dev/null || true)
        if [[ -n "$VM_IP" ]]; then
            if sshpass -p "$VM_PASS" ssh -o "StrictHostKeyChecking=no" -o "ConnectTimeout=5" "$VM_USER@$VM_IP" "true" 2>/dev/null; then
                log "VM accessible at $VM_IP"
                return 0
            fi
        fi
        ((attempts++))
        sleep 2
    done
    
    error "VM did not become accessible after $((max_attempts * 2)) seconds"
    return 1
}

# Cleanup on exit
cleanup() {
    # Restore original Brewfile if we swapped it
    if [[ -f "$REPO_DIR/ansible/Brewfile.bak" ]]; then
        mv "$REPO_DIR/ansible/Brewfile.bak" "$REPO_DIR/ansible/Brewfile"
    fi
    
    if [[ "$KEEP_RUNNING" == "false" ]] && tart list 2>/dev/null | grep -q "$VM_NAME.*running"; then
        log "Stopping VM..."
        tart stop "$VM_NAME" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Main
main() {
    check_deps
    
    log "Testing bootstrap script"
    echo "    Repo: $REPO_DIR"
    echo "    VM: $VM_NAME"
    echo ""
    
    # Fresh VM if requested
    if [[ "$FRESH" == "true" ]]; then
        log "Creating fresh VM from $VM_IMAGE..."
        tart stop "$VM_NAME" 2>/dev/null || true
        tart delete "$VM_NAME" 2>/dev/null || true
        tart clone "$VM_IMAGE" "$VM_NAME"
    fi
    
    # Check VM exists
    if ! tart list 2>/dev/null | grep -q "$VM_NAME"; then
        log "VM not found, cloning from $VM_IMAGE..."
        tart clone "$VM_IMAGE" "$VM_NAME"
    fi
    
    # Stop if already running
    if tart list 2>/dev/null | grep -q "$VM_NAME.*running"; then
        warn "VM already running, stopping first..."
        tart stop "$VM_NAME"
        sleep 2
    fi
    
    # Start VM
    log "Starting VM..."
    if [[ "$INTERACTIVE" == "true" ]]; then
        tart run --dir=ansiblonomicon:"$REPO_DIR" "$VM_NAME" &
    else
        tart run --no-graphics --dir=ansiblonomicon:"$REPO_DIR" "$VM_NAME" &
    fi
    
    wait_for_ssh
    
    # Uninstall Xcode CLI tools if requested
    if [[ "$UNINSTALL_XCODE" == "true" ]]; then
        log "Removing Xcode CLI tools to test fresh installation..."
        vm_ssh_sudo "rm -rf /Library/Developer/CommandLineTools" || true
        vm_ssh_sudo "xcode-select --reset" 2>/dev/null || true
        
        if vm_ssh "xcode-select -p" 2>/dev/null; then
            error "Failed to remove Xcode CLI tools"
            exit 1
        fi
        log "Xcode CLI tools removed"
    fi
    
    # Swap to minimal Brewfile if not using full (do locally so trap can restore)
    if [[ "$FULL_BREW_BUNDLE" == "false" ]]; then
        log "Using minimal test Brewfile..."
        cp "$REPO_DIR/ansible/Brewfile" "$REPO_DIR/ansible/Brewfile.bak"
        cp "$REPO_DIR/ansible/Brewfile.test" "$REPO_DIR/ansible/Brewfile"
    fi
    
    # Run bootstrap
    log "Running bootstrap script..."
    echo ""
    
    if vm_ssh "cd '/Volumes/My Shared Files/ansiblonomicon' && ./scripts/bootstrap.sh"; then
        echo ""
        log "Bootstrap completed successfully!"
        
        # Verify key components
        log "Verifying installation..."
        echo -n "    Homebrew: "
        vm_ssh "command -v brew" && echo "OK" || echo "MISSING"
        echo -n "    Ansible: "
        vm_ssh "command -v ansible-playbook" && echo "OK" || echo "MISSING"
        echo -n "    Xcode CLI: "
        vm_ssh "xcode-select -p" 2>/dev/null && echo "OK" || echo "MISSING"
    else
        echo ""
        error "Bootstrap failed!"
        exit 1
    fi
    
    if [[ "$KEEP_RUNNING" == "true" ]]; then
        warn "VM left running at $VM_IP (user: $VM_USER, pass: $VM_PASS)"
        warn "Stop with: tart stop $VM_NAME"
    fi
}

main "$@"
