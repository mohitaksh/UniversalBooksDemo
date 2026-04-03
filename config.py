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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o")

# ─── Sarvam ─────────────────────────────────────────────────
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# ─── N8N Webhooks ───────────────────────────────────────────
N8N_CALLBACK_WEBHOOK_URL         = os.getenv("N8N_CALLBACK_WEBHOOK_URL", "")
N8N_TAG_LEAD_WEBHOOK_URL         = os.getenv("N8N_TAG_LEAD_WEBHOOK_URL", "")
N8N_LOG_WEBHOOK_URL              = os.getenv("N8N_LOG_WEBHOOK_URL", "")
N8N_WHATSAPP_SAMPLE_WEBHOOK_URL  = os.getenv("N8N_WHATSAPP_SAMPLE_WEBHOOK_URL", "")
N8N_DELIVERY_CHECK_WEBHOOK_URL   = os.getenv("N8N_DELIVERY_CHECK_WEBHOOK_URL", "")
N8N_DNC_WEBHOOK_URL              = os.getenv("N8N_DNC_WEBHOOK_URL", "")

# ─── Recording ──────────────────────────────────────────────
ENABLE_RECORDING = os.getenv("ENABLE_RECORDING", "false").lower() == "true"
