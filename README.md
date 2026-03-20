# UniversalBooks — AI Sales Outbound Agent

A multi-agent voice AI system for making outbound sales calls to tutors, teachers, and coaching centers. Built with LiveKit Agents SDK.

## Architecture

**20 specialized agents across 6 layers** — each agent has ONE focused job with automatic handoffs:

| Layer | Agents |
|-------|--------|
| First Contact | GreeterAgent → IdentityConfirmerAgent → GatekeeperAgent → HoldWaiterAgent |
| Pitch & Discovery | IntroAgent → NeedsAssessorAgent → ExamPitcherAgent → ClosingPitcherAgent |
| Objection Handling | OwnMaterialAgent, PriceHandlerAgent, NotInterestedAgent, ThinkAboutItAgent |
| Action & Fulfillment | MaterialSenderAgent, EmailCollectorAgent, BusySchedulerAgent, TeamConnectAgent |
| Closing | GracefulCloserAgent, HostileExitAgent |
| Edge Cases | WrongNumberAgent, ReEngagerAgent |

**Tech Stack:** Claude Haiku via AWS Bedrock (LLM) · Sarvam Saaras v3 (STT) · Sarvam Bulbul v3 (TTS) · LiveKit SIP · FastAPI · N8N webhooks

---

## Quick Start

### 1. Install

**Ubuntu / EC2:**
```bash
git clone https://github.com/mohitaksh/UniversalBooksDemo.git
cd UniversalBooksDemo
chmod +x install_ubuntu.sh
./install_ubuntu.sh
```

**Windows:**
```cmd
git clone https://github.com/mohitaksh/UniversalBooksDemo.git
cd UniversalBooksDemo
install_windows.bat
```

### 2. Configure

Edit `.env.local` with your API keys (created from `.env.example` during install):
```
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
SIP_OUTBOUND_TRUNK_ID
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
SARVAM_API_KEY
N8N_WHATSAPP_WEBHOOK_URL (+ SMS, CALLBACK, EMAIL)
```

### 3. Run (Ubuntu — using `screen`)

Open 3 screen sessions:

```bash
# Terminal 1: FastAPI server
screen -S server
./start_server.sh
# Ctrl+A then D to detach

# Terminal 2: Agent worker
screen -S agent
./start_agent.sh
# Ctrl+A then D to detach

# Terminal 3: ngrok tunnel
screen -S ngrok
./start_ngrok.sh
# Ctrl+A then D to detach
```

Reattach: `screen -r server` / `screen -r agent` / `screen -r ngrok`

### 3. Run (Windows)

Open 3 terminals:

```cmd
REM Terminal 1: FastAPI server
venv\Scripts\activate
uvicorn server:app --reload --port 8000

REM Terminal 2: Agent worker
venv\Scripts\activate
python main_agent.py dev

REM Terminal 3: ngrok
ngrok http 8000
```

---

## Triggering a Call (via N8N or cURL)

```bash
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+919999999999",
    "name": "Kavita",
    "call_type": "name"
  }'
```

- `call_type: "name"` — direct teacher/tutor (e.g., "क्या आप Kavita जी बोल रहे हैं?")
- `call_type: "institution"` — coaching center (e.g., "क्या आप Tiwari Tutorials से बोल रहे हैं?")

---

## Project Structure

```
├── main_agent.py          # 20 agent classes + entrypoint
├── prompts.py             # All agent prompts (Devanagari Hinglish)
├── server.py              # FastAPI server for triggering calls
├── models.py              # CostTracker and pricing models
├── logger.py              # 6-logger setup (full, brief, token, cost, LLM, transcript)
├── cumulative_logger.py   # Aggregates costs across all calls
├── requirements.txt       # Python dependencies
├── .env.example           # Template for API keys
├── .env.local             # Your actual API keys (git-ignored)
├── install_ubuntu.sh      # Ubuntu/EC2 install script
├── install_windows.bat    # Windows install script
├── start_server.sh        # Start FastAPI server
├── start_agent.sh         # Start agent worker
├── start_ngrok.sh         # Start ngrok tunnel
└── logs/                  # Call logs (git-ignored)
```

---

## Logs

Each call generates a folder in `logs/` with:
- `call_<id>.log` — full verbose log
- `call_<id>_brief.log` — key events only
- `call_<id>_tokens.log` — token usage per LLM turn
- `call_<id>_costs.log` — final cost report
- `call_<id>_llm_transcript.log` — raw LLM context dumps
- `call_<id>_transcript.txt` — human-readable conversation transcript
- `costs.json` — machine-readable cost data

Run `python cumulative_logger.py` alongside the agent to aggregate costs across all calls into `logs/summary.json`.
