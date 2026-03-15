#!/bin/bash
# ═══════════════════════════════════════════════════════
# UniversalBooks — Start LiveKit Agent Worker
# ═══════════════════════════════════════════════════════
# Usage:  ./start_agent.sh
# Starts the 20-agent multi-agent system in dev mode.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "🤖 Starting UniversalBooks Agent Worker (20-agent system)..."
echo "   Agent name: UniversalBooksAgent"
echo "   LLM: Claude Haiku | STT: Sarvam Saaras v3 | TTS: Sarvam Bulbul v3"
echo ""

python main_agent.py dev
