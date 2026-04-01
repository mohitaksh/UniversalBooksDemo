import os
import json
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from livekit.api import LiveKitAPI, CreateSIPParticipantRequest
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

load_dotenv(dotenv_path=".env.local")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CallRequest(BaseModel):
    phone_number: str
    name: str = "Client"
    call_type: str = "NEW_TEACHER" 
    # Valid types expected by N8N: 
    # NEW_TEACHER
    # DIGITAL_SAMPLE_FOLLOW_UP_1
    # DIGITAL_SAMPLE_FOLLOW_UP_2
    # PHYSICAL_SAMPLE_FOLLOW_UP_1
    # PHYSICAL_SAMPLE_FOLLOW_UP_2
    # VISITED_FOLLOW_UP
    # CONTACTED_BEFORE_PHYSICALLY
    # CONTACTED_BEFORE_CALL
    # REFERRED

@app.post("/call")
async def make_outbound_call(req: CallRequest):
    """
    Endpoint to trigger an outbound SIP call via LiveKit via N8N Webhook.
    """
    sip_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    if not sip_trunk_id:
        raise HTTPException(status_code=500, detail="SIP_OUTBOUND_TRUNK_ID not configured")

    timestamp = int(time.time())
    room_name = f"call_{req.phone_number.strip('+')}_{timestamp}"
    
    lk_url = os.getenv("LIVEKIT_URL")
    lk_api_key = os.getenv("LIVEKIT_API_KEY")
    lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not all([lk_url, lk_api_key, lk_api_secret]):
        raise HTTPException(status_code=500, detail="LiveKit credentials missing")
    
    api = LiveKitAPI(url=lk_url, api_key=lk_api_key, api_secret=lk_api_secret)
    
    try:
        request = CreateSIPParticipantRequest(
            sip_trunk_id=sip_trunk_id,
            sip_call_to=req.phone_number,
            room_name=room_name,
            participant_identity=f"sip_{req.phone_number}",
            participant_name=req.name
        )
        
        logger.info(f"Initiating SIP call for {req.phone_number} to room {room_name}")
        res = await api.sip.create_sip_participant(request)
        logger.info(f"SIP Participant created: {res.participant_identity}")
        
        dispatch_req = CreateAgentDispatchRequest(
            agent_name="UniversalBooksAgent", # The name doesn't really matter if we have 1 Worker accepting all
            room=room_name,
            metadata=json.dumps({
                "name": req.name,
                "phone": req.phone_number,
                "call_type": req.call_type
            })
        )
        try:
            logger.info(f"Dispatching Agent to room {room_name} with type {req.call_type}")
            dispatch_res = await api.agent_dispatch.create_dispatch(dispatch_req)
        except Exception as dispatch_err:
            logger.error(f"Agent Dispatch Failed! Error: {dispatch_err}")
        
        return {
            "status": "success", 
            "message": "Outbound call initiated",
            "room_name": room_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")
    finally:
        await api.aclose()
