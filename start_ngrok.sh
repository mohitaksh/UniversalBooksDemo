#!/bin/bash
# ═══════════════════════════════════════════════════════
# UniversalBooks — Start ngrok Tunnel
# ═══════════════════════════════════════════════════════
# Usage:  ./start_ngrok.sh
# Tunnels port 8000 (FastAPI server) to a public URL.
# Copy the public URL and use it in your N8N webhook.

echo "🌐 Starting ngrok tunnel for port 8000..."
echo "   Copy the 'Forwarding' URL for N8N webhook."
echo ""

ngrok http 8000
