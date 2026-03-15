import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from livekit.api import LiveKitAPI, CreateSIPParticipantRequest
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

load_dotenv(dotenv_path=".env.local")

app = FastAPI()

class CallRequest(BaseModel):
    phone_number: str
    name: str = "Client"
    call_type: str = "name"  # "name" (direct person) or "institution" (coaching center)

@app.post("/call")
async def make_outbound_call(req: CallRequest):
    """
    Endpoint for N8N or other clients to trigger an outbound SIP call via LiveKit.
    
    call_type: "name" for direct teacher/tutor calls, "institution" for coaching centers.
    """
    sip_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    if not sip_trunk_id:
        raise HTTPException(status_code=500, detail="SIP_OUTBOUND_TRUNK_ID not configured in .env.local")
        
    room_name = f"call_{req.phone_number.strip('+')}"
    
    # LiveKit credentials
    lk_url = os.getenv("LIVEKIT_URL")
    lk_api_key = os.getenv("LIVEKIT_API_KEY")
    lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not all([lk_url, lk_api_key, lk_api_secret]):
        raise HTTPException(status_code=500, detail="LiveKit credentials missing in .env.local")
    
    api = LiveKitAPI(
        url=lk_url,
        api_key=lk_api_key,
        api_secret=lk_api_secret
    )
    
    try:
        # Create SIP Participant request
        request = CreateSIPParticipantRequest(
            sip_trunk_id=sip_trunk_id,
            sip_call_to=req.phone_number,
            room_name=room_name,
            participant_identity=f"sip_{req.phone_number}",
            participant_name=req.name
        )
        
        # Initiate the SIP call
        logger.info(f"Initiating SIP call for {req.phone_number} to room {room_name}")
        res = await api.sip.create_sip_participant(request)
        logger.info(f"SIP Participant created: {res.participant_identity}")
        
        # Dispatch the agent to the room explicitly
        dispatch_req = CreateAgentDispatchRequest(
            agent_name="UniversalBooksAgent",
            room=room_name,
            metadata=json.dumps({
                "name": req.name,
                "phone": req.phone_number,
                "call_type": req.call_type
            })
        )
        try:
            logger.info(f"Explicitly dispatching UniversalBooksAgent to room {room_name}")
            dispatch_res = await api.agent_dispatch.create_dispatch(dispatch_req)
            logger.info(f"Agent Dispatch Response: {dispatch_res}")
        except Exception as dispatch_err:
            logger.error(f"Agent Dispatch Failed! Is 'UniversalBooksAgent' registered? Error: {dispatch_err}")
            # We don't fail the whole request since the SIP connection already started, but we note it.
        
        return {
            "status": "success", 
            "message": "Outbound call initiated and agent dispatched",
            "room_name": room_name,
            "participant_id": res.participant_identity
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")
    finally:
        await api.aclose()
        
@app.get("/health")
def health_check():
    return {"status": "ok"}
