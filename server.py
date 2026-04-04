"""
server.py — FastAPI server that triggers outbound SIP calls.
═════════════════════════════════════════════════════════════

Receives: POST /call { name, phone_number, call_type }
Creates a LiveKit room with metadata, dispatches the agent,
and initiates a SIP outbound call.

The call_type determines which agent flow runs (10 types supported).
"""

import time
import logging
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from livekit.api import LiveKitAPI, CreateRoomRequest, SIPParticipantInfo
from livekit.api.sip_service import CreateSIPParticipantRequest

from config import LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, SIP_OUTBOUND_TRUNK_ID
from models import CallType

logger = logging.getLogger("server")

app = FastAPI(title="UniversalBooks Voice AI Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Model ──────────────────────────────────────────

class CallRequest(BaseModel):
    """
    Request body for /call endpoint.

    call_type accepts any of:
      new_teacher_coaching, new_teacher_tuition,
      followup_digital_sample_1, followup_digital_sample_2,
      followup_physical_sample_1, followup_physical_sample_2,
      followup_visit, contacted_physically, contacted_call, referral

    call_client_type: "teacher" or "institution"
      - teacher: individual tuition teacher (greeting uses their name)
      - institution: coaching center / school (greeting uses institution name)

    Legacy values also accepted: "name" → new_teacher_tuition, "institution" → new_teacher_coaching
    """
    name: str
    phone_number: str


# ─── Health Check ────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "UniversalBooks Voice AI"}


# ─── Place Call ──────────────────────────────────────────────

@app.post("/call")
async def make_outbound_call(req: CallRequest):
    """
    Create a room, dispatch the agent, and initiate a SIP outbound call.
    The agent reads call_type from room metadata and picks the right flow.
    """
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, SIP_OUTBOUND_TRUNK_ID]):
        raise HTTPException(status_code=500, detail="LiveKit not configured")

    phone = req.phone_number.strip()
    if not phone.startswith("+"):
        phone = f"+91{phone}"  # Default to India

    ts = int(time.time())
    room_name = f"call_{phone.replace('+', '')}_{ts}"

        # Room metadata — the agent reads this to pick the right flow
    import json
    metadata = json.dumps({
        "name": req.name,
        "phone_number": phone,
    })

    logger.info(f"CALL REQUEST | {req.name} | {phone}")

    try:
        api = LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )

        # Create room with metadata
        await api.room.create_room(CreateRoomRequest(
            name=room_name,
            empty_timeout=60,
            metadata=metadata,
        ))

        # Create SIP participant (the outbound call)
        await api.sip.create_sip_participant(CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,
            sip_call_to=phone,
            participant_identity=f"sip_{phone}",
            participant_name=req.name,
        ))

        await api.aclose()

        return {
            "status": "ok",
            "room_name": room_name,
            "phone": phone,
        }

    except Exception as e:
        logger.error(f"Call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
