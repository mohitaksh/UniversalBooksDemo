"""
config.py
─────────
Centralized configuration — all env vars and defaults in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

# ─── LiveKit ────────────────────────────────────────────────
LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
SIP_OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID", "")

# ─── LLM ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─── Sarvam ─────────────────────────────────────────────────
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# ─── N8N Webhooks ───────────────────────────────────────────
N8N_CALLBACK_WEBHOOK_URL = os.getenv("N8N_CALLBACK_WEBHOOK_URL", "")
N8N_TAG_LEAD_WEBHOOK_URL = os.getenv("N8N_TAG_LEAD_WEBHOOK_URL", "")
N8N_LOG_WEBHOOK_URL      = os.getenv("N8N_LOG_WEBHOOK_URL", "")

# ─── Recording ──────────────────────────────────────────────
ENABLE_RECORDING = os.getenv("ENABLE_RECORDING", "false").lower() == "true"
