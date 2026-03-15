#!/bin/bash
# ═══════════════════════════════════════════════════════
# UniversalBooks — Ubuntu / Debian Install Script
# ═══════════════════════════════════════════════════════
# Usage:
#   chmod +x install_ubuntu.sh
#   ./install_ubuntu.sh
#
# Run this ONCE after cloning the repo on a fresh EC2 instance.
# It installs system deps, creates a venv, installs Python packages,
# copies .env.example → .env.local (if missing), and installs ngrok.
# ═══════════════════════════════════════════════════════

set -e  # Exit on any error

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   UniversalBooks — Ubuntu Install                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. System packages ───────────────────────────────────
echo "▶ [1/6] Installing system dependencies..."
sudo apt update -y
sudo apt install -y python3 python3-venv python3-pip python3-dev \
    build-essential curl wget screen

# ── 2. Python venv ───────────────────────────────────────
echo "▶ [2/6] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ venv created"
else
    echo "  ✓ venv already exists, skipping"
fi

source venv/bin/activate

# ── 3. Python dependencies ───────────────────────────────
echo "▶ [3/6] Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# ── 4. Environment file ─────────────────────────────────
echo "▶ [4/6] Setting up environment file..."
if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    echo "  ✓ Created .env.local from .env.example"
    echo "  ⚠ IMPORTANT: Edit .env.local and fill in your API keys!"
else
    echo "  ✓ .env.local already exists, skipping"
fi

# ── 5. Create logs directory ─────────────────────────────
echo "▶ [5/6] Creating logs directory..."
mkdir -p logs
echo "  ✓ logs/ directory ready"

# ── 6. Install ngrok ─────────────────────────────────────
echo "▶ [6/6] Installing ngrok..."
if ! command -v ngrok &> /dev/null; then
    curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
        | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
        | sudo tee /etc/apt/sources.list.d/ngrok.list
    sudo apt update -y && sudo apt install -y ngrok
    echo "  ✓ ngrok installed"
    echo "  ⚠ Run 'ngrok config add-authtoken YOUR_TOKEN' to authenticate"
else
    echo "  ✓ ngrok already installed"
fi

# ── 7. Make start scripts executable ─────────────────────
chmod +x start_server.sh start_agent.sh start_ngrok.sh 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ✅ Installation Complete!                          ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  Next steps:                                         ║"
echo "║  1. Edit .env.local with your API keys               ║"
echo "║  2. Start 3 screen sessions:                         ║"
echo "║                                                      ║"
echo "║     screen -S server  → ./start_server.sh            ║"
echo "║     screen -S agent   → ./start_agent.sh             ║"
echo "║     screen -S ngrok   → ./start_ngrok.sh             ║"
echo "║                                                      ║"
echo "║  Detach: Ctrl+A then D                               ║"
echo "║  Reattach: screen -r server                          ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
