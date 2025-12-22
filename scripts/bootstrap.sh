#!/bin/bash
set -euo pipefail

# ansiblonomicon bootstrap script
# Run this on a fresh macOS or Arch Linux system to set everything up

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> ansiblonomicon bootstrap"
echo "    Repo: $REPO_DIR"

# Detect platform
if [[ "$(uname)" == "Darwin" ]]; then
    PLATFORM="darwin"
elif [[ -f /etc/arch-release ]]; then
    PLATFORM="archlinux"
else
    echo "ERROR: Unsupported platform: $(uname)"
    exit 1
fi
echo "    Platform: $PLATFORM"

# macOS: Install Xcode CLI tools (non-interactive)
if [[ "$PLATFORM" == "darwin" ]]; then
    if ! xcode-select -p &>/dev/null; then
        echo "==> Installing Xcode Command Line Tools..."
        # Create the placeholder file that triggers the install
        touch /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress
        # Find and install the latest CLI tools package
        PROD=$(softwareupdate -l 2>/dev/null | grep -B 1 "Command Line Tools" | grep -o "Command Line Tools.*" | head -1)
        if [[ -n "$PROD" ]]; then
            echo "    Found: $PROD"
            softwareupdate -i "$PROD" --verbose
        else
            echo "    ERROR: Could not find Command Line Tools in software updates"
            echo "    Falling back to interactive install..."
            xcode-select --install
            echo "    Press any key after installation completes..."
            read -n 1
        fi
        rm -f /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress
    else
        echo "==> Xcode CLI tools already installed"
    fi
fi

# macOS: Install Homebrew
if [[ "$PLATFORM" == "darwin" ]]; then
    if ! command -v brew &>/dev/null; then
        echo "==> Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add to PATH for this session
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        echo "==> Homebrew already installed"
    fi
fi

# Install Ansible
if ! command -v ansible-playbook &>/dev/null; then
    echo "==> Installing Ansible..."
    if [[ "$PLATFORM" == "darwin" ]]; then
        brew install ansible
    elif [[ "$PLATFORM" == "archlinux" ]]; then
        sudo pacman -S --noconfirm ansible
    fi
else
    echo "==> Ansible already installed"
fi

# Install chezmoi
if ! command -v chezmoi &>/dev/null; then
    echo "==> Installing chezmoi..."
    if [[ "$PLATFORM" == "darwin" ]]; then
        brew install chezmoi
    elif [[ "$PLATFORM" == "archlinux" ]]; then
        sudo pacman -S --noconfirm chezmoi
    fi
else
    echo "==> chezmoi already installed"
fi

# Install Ansible Galaxy requirements (if requirements.yml exists)
if [[ -f "$REPO_DIR/ansible/requirements.yml" ]]; then
    echo "==> Installing Ansible Galaxy requirements..."
    ansible-galaxy install -r "$REPO_DIR/ansible/requirements.yml"
fi

# Run the playbook
echo "==> Running Ansible playbook..."
cd "$REPO_DIR/ansible"
ansible-playbook main.yml -K

echo "==> Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Set up 1Password CLI: op signin"
echo "  2. Ensure 'Apple Macbook Login' item exists in Private vault"
echo "  3. Future runs: just run 'anup' (no password prompt needed)"
