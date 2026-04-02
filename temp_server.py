"""
temp_server.py — Minimal test server on port 8081.
"""

import time
import json
import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from livekit.api import LiveKitAPI, CreateRoomRequest
from livekit.api.sip_service import CreateSIPParticipantRequest

load_dotenv(dotenv_path=".env.local")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
SIP_OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID", "")

app = FastAPI()


class CallReq(BaseModel):
    name: str = "ji"
    phone_number: str = ""


@app.post("/call")
async def call(req: CallReq):
    phone = req.phone_number.strip()
    if not phone.startswith("+"):
        phone = f"+91{phone}"

    room_name = f"test_{phone.replace('+', '')}_{int(time.time())}"
    metadata = json.dumps({"name": req.name, "phone": phone})

    api = LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    await api.room.create_room(CreateRoomRequest(
        name=room_name,
        empty_timeout=60,
        metadata=metadata,
    ))

    await api.sip.create_sip_participant(CreateSIPParticipantRequest(
        room_name=room_name,
        sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,
        sip_call_to=phone,
        participant_identity=f"sip_{phone}",
        participant_name=req.name,
    ))

    await api.aclose()
    return {"status": "ok", "room": room_name, "phone": phone}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
