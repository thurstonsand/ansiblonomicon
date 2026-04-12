#!/bin/bash
set -euo pipefail

# ansiblonomicon bootstrap script
# Run this on a fresh macOS or Arch Linux system to set everything up

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GALAXY_IGNORE_CERTS=""
for arg in "$@"; do
    case "$arg" in
        --ignore-certs) GALAXY_IGNORE_CERTS="--ignore-certs" ;;
    esac
done

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

# Install 1Password CLI (required for secrets in Ansible and Chezmoi)
if ! command -v op &>/dev/null; then
    echo "==> Installing 1Password CLI..."
    if [[ "$PLATFORM" == "darwin" ]]; then
        brew install --cask 1password-cli
    elif [[ "$PLATFORM" == "archlinux" ]]; then
        # AUR package: 1password-cli
        echo "    Install 1password-cli from AUR manually"
    fi
else
    echo "==> 1Password CLI already installed"
fi

# Verify 1Password is signed in (required for secrets)
# op account list returns 0 even when not signed in, so we test an actual read
if ! op account get &>/dev/null; then
    echo ""
    echo "ERROR: 1Password CLI is not signed in."
    echo ""
    echo "To sign in, run:"
    echo "    op signin"
    echo ""
    echo "Then re-run this script."
    exit 1
fi
echo "==> 1Password CLI signed in"

# Install Ansible Galaxy requirements (if requirements.yml exists)
if [[ -f "$REPO_DIR/ansible/requirements.yml" ]]; then
    echo "==> Installing Ansible Galaxy requirements..."
    if ! ansible-galaxy install -r "$REPO_DIR/ansible/requirements.yml" $GALAXY_IGNORE_CERTS; then
        echo ""
        echo "ERROR: Failed to install Ansible Galaxy requirements."
        echo ""
        echo "If this is an SSL/certificate error (e.g. corporate proxy or Zscaler),"
        echo "re-run with:"
        echo "    ./scripts/bootstrap.sh --ignore-certs"
        exit 1
    fi
fi

echo "==> Bootstrap complete!"
echo ""
echo "Next step: run the appropriate playbook, e.g.:"
echo "    uv run poe macos"
echo "    uv run poe truenas"
echo "    uv run poe openclaw"
echo "    uv run poe work"
