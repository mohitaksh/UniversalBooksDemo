#!/bin/bash
# ═══════════════════════════════════════════════════════
# UniversalBooks — Start FastAPI Server
# ═══════════════════════════════════════════════════════
# Usage:  ./start_server.sh
# Runs uvicorn on port 8000, accessible from all interfaces.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "🚀 Starting FastAPI server on port 8000..."
echo "   Health check: http://localhost:8000/health"
echo "   Call endpoint: POST http://localhost:8000/call"
echo ""

uvicorn server:app --host 0.0.0.0 --port 8000 --reload
