# UniversalBooks Outbound Agent: Code Flow & Architecture

This document breaks down exactly how an outbound call is triggered from N8N, how it reaches the user's phone, and how the Voice Agent responds.

---

## 1. Triggering the Call (N8N → FastAPI)

The flow begins when your N8N workflow wants to call a specific lead. N8N sends an HTTP `POST` request to your FastAPI server (`server.py`).

```python
# From server.py
@app.post("/call")
async def make_outbound_call(req: CallRequest):
    sip_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    room_name = f"call_{req.phone_number.strip('+')}"

    # 1. Create SIP Participant (initiates the phone call)
    request = CreateSIPParticipantRequest(
        sip_trunk_id=sip_trunk_id,
        sip_call_to=req.phone_number,
        room_name=room_name,
        participant_identity=f"sip_{req.phone_number}",
        participant_name=req.name
    )
    res = await api.sip.create_sip_participant(request)

    # 2. Explicitly dispatch the agent to the room
    dispatch_req = CreateAgentDispatchRequest(
        agent_name="UniversalBooksAgent",
        room=room_name,
        metadata=json.dumps({"name": req.name, "phone": req.phone_number})
    )
    dispatch_res = await api.agent_dispatch.create_dispatch(dispatch_req)
```

**What happens here?**
1. FastAPI receives `req.phone_number` and `req.name`.
2. It calls `CreateSIPParticipantRequest` — LiveKit Cloud tells the VOBIZ SIP trunk to dial the phone number and place the audio into a Room named `call_919999999999`.
3. It then explicitly dispatches the `UniversalBooksAgent` to that room, passing the caller's name and phone as metadata.

---

## 2. The Agent Connects (LiveKit Cloud → Python Worker)

In the background, your `main_agent.py` process is running as a LiveKit worker, registered as `UniversalBooksAgent`. When dispatched to a room, it accepts the job.

```python
# From main_agent.py
async def entrypoint(ctx: JobContext):
    call_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    loggers = setup_loggers(call_id)
    full_log, brief_log, token_log, cost_log, llm_log, transcript_log = loggers

    # Read caller name from dispatch metadata
    meta = json.loads(ctx.job.metadata or "{}")
    caller_name = meta.get("name", "ji") or "ji"

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    tracker = CostTracker(call_id=call_id)

    # Initialize AI plugins
    llm_plugin = groq.LLM(model="openai/gpt-oss-120b", api_key=os.getenv("GROQ_API_KEY"))
    stt_plugin = sarvam.STT(language="en-IN", model="saaras:v3")
    tts_plugin = sarvam.TTS(target_language_code="hi-IN", model="bulbul:v3", speaker="shubh")

    initial_agent = MainAgent(tracker=tracker, brief_log=brief_log, caller_name=caller_name)
    session = AgentSession(llm=llm_plugin, stt=stt_plugin, tts=tts_plugin)

    await session.start(room=ctx.room, agent=initial_agent)
```

**What happens here?**
1. The worker accepts the job, generates a unique call ID, and sets up 6 separate log files.
2. It reads the caller's name from the dispatch metadata JSON.
3. It initializes the three AI services: Groq LLM, Sarvam STT (Saaras v3), Sarvam TTS (Bulbul v3).
4. It creates the `MainAgent` with a cost tracker and starts the `AgentSession`.

---

## 3. The Conversation Starts (MainAgent.on_enter)

When the agent enters the session, the `on_enter` method fires.

```python
# From main_agent.py
class MainAgent(Agent):
    def __init__(self, tracker, brief_log, caller_name: str = "ji"):
        super().__init__(instructions=PRIYA_AGENT_PROMPT)
        self.tracker = tracker
        self.brief_log = brief_log
        self.caller_name = caller_name

    async def on_enter(self) -> None:
        self.brief_log.info(f"AGENT_ENTER | MainAgent (Priya) | caller={self.caller_name}")
        await asyncio.sleep(5.0)  # Wait for SIP audio to stabilize
        await self.session.say(
            f"Hello, {self.caller_name} ji? Main Priya bol rahi hoon, Universal Books se. "
            f"Kya aap thodi der baat kar sakte hain?"
        )
```

**What happens here?**
1. The agent waits 5 seconds for the SIP trunk audio to fully establish (otherwise the AI might talk over the ringtone).
2. The agent delivers a hardcoded Hinglish opener using `session.say()` — this bypasses the LLM for a consistent first line.
3. After the opener, the LLM takes over using the `PRIYA_AGENT_PROMPT` instructions.

---

## 4. Conversation Loop (STT → LLM → TTS)

Once the opener plays, the agent enters its main conversation loop:

1. **User speaks** → Sarvam STT (Saaras v3) transcribes audio to text
2. **Text goes to LLM** → Groq (gpt-oss-120b) processes it with the full chat context and `PRIYA_AGENT_PROMPT`
3. **LLM responds** → May include text responses and/or tool calls
4. **Text goes to TTS** → Sarvam TTS (Bulbul v3) synthesizes the Hinglish response to audio
5. **Audio plays** to the user's phone

The LLM has access to two function tools and uses them based on conversation context.

---

## 5. Tool Calling — WhatsApp PDF & Lead Tagging

### send_demo_pdf_whatsapp
When the user agrees to receive a sample/catalogue:

```python
@function_tool(description="Use this tool to send the demo PDF over WhatsApp...")
async def send_demo_pdf_whatsapp(self, context: llm.RunContext) -> str:
    webhook_url = os.getenv("N8N_WHATSAPP_WEBHOOK_URL", "")
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"action": "send_pdf"})
        return "WhatsApp message triggered successfully."
```

**What happens**: Python sends an HTTP POST to the N8N webhook URL, which triggers an N8N workflow that sends the PDF via WhatsApp.

### tag_lead
At the end of every call, the LLM tags the outcome:

```python
@function_tool(description="Call this tool at the very end to tag the lead outcome.")
async def tag_lead(self, context: llm.RunContext, tag: str, notes: str = "") -> str:
    self.tracker.log_function("tag_lead", {"tag": tag, "notes": notes})
    return f"Lead successfully tagged as {tag}."
```

**Allowed tags**: Interested, Send Sample, Call Back, Not Interested, Wrong Contact.

---

## 6. Real-Time Logging & Cost Tracking

While the conversation runs, the system tracks everything through **6 per-call loggers** and a **CostTracker**:

### Metrics Collection
```python
@session.on("metrics_collected")
def on_metrics(event):
    m = event.metrics
    # Tracks: LLM tokens (input/output), TTS chars, STT seconds
    # Also dumps full LLM context to llm_log each turn
```

### Transcript Logging
```python
@session.on("agent_speech_committed")
def on_agent_speech_committed(msg):
    transcript_log.info(f"Priya: {msg.content}")

@session.on("user_speech_committed")
def on_user_speech_committed(msg):
    transcript_log.info(f"User: {msg.content}")
```

### Periodic Cost Updates
Every 5 seconds, a background task logs running costs in INR to both the full log and token log.

### Log Files Per Call (`logs/<call_id>/`)
| File | Contents |
|------|----------|
| `call_<id>.log` | Everything (also printed to console) |
| `call_<id>_brief.log` | High-level events only |
| `call_<id>_tokens.log` | Token/char counts per turn |
| `call_<id>_costs.log` | Final cost report |
| `call_<id>_llm_transcript.log` | Full LLM context dump each turn |
| `call_<id>_transcript.txt` | Clean `Priya: ... / User: ...` dialogue |
| `costs.json` | Machine-readable costs for aggregator |

---

## 7. Call Cleanup (Disconnect)

When the user hangs up or the room disconnects:

```python
@ctx.room.on("disconnected")
def on_disconnected(*args):
    shutdown_call(reason="room disconnected")

def shutdown_call(reason="room disconnected"):
    cost_task.cancel()
    write_cost_report(tracker=tracker, full_log=full_log, cost_log=cost_log, brief_log=brief_log)
```

**What happens**:
1. The periodic cost logger is cancelled.
2. A formatted ASCII cost report is written to both cost_log and full_log.
3. `costs.json` is written for the cumulative aggregator.
4. The function call timeline is dumped to the brief log.

---

## 8. Cumulative Cost Aggregation

A separate standalone process (`cumulative_logger.py`) runs alongside the agent:

```bash
python cumulative_logger.py
```

Every 5 minutes it:
1. Scans all `logs/*/costs.json` files
2. Sums up totals across all calls (tokens, chars, seconds, costs)
3. Adds telephony cost estimate (₹0.45/min)
4. Writes `logs/summary.json` and `logs/summary.txt`

---

## Architecture Diagram

```
N8N Workflow
    │
    │ POST /call {phone_number, name}
    ▼
┌──────────────┐
│  server.py   │  FastAPI on port 8000
│  (FastAPI)   │
└──────┬───────┘
       │ 1. CreateSIPParticipant (Vobiz trunk)
       │ 2. CreateAgentDispatch (UniversalBooksAgent)
       ▼
┌──────────────┐        ┌──────────────┐
│  LiveKit     │───────▶│  Vobiz SIP   │──────▶ 📞 User's Phone
│  Cloud       │        │  Trunk       │
└──────┬───────┘        └──────────────┘
       │ Job dispatched
       ▼
┌──────────────────────────────────────────────┐
│  main_agent.py (Worker)                       │
│                                               │
│  MainAgent (Priya)                            │
│  ├── PRIYA_AGENT_PROMPT (Hinglish sales)      │
│  ├── send_demo_pdf_whatsapp → N8N webhook     │
│  └── tag_lead → logs outcome                  │
│                                               │
│  Plugins:                                     │
│  ├── Groq LLM (gpt-oss-120b)                 │
│  ├── Sarvam STT (Saaras v3)                  │
│  └── Sarvam TTS (Bulbul v3, speaker: shubh)  │
│                                               │
│  Logging: 6 per-call loggers + CostTracker    │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│  cumulative_logger.py    │
│  (standalone process)     │
│  → logs/summary.json     │
│  → logs/summary.txt      │
└──────────────────────────┘
```
