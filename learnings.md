# UniversalBooks Voice AI — Technical Learnings

> Hard-won lessons from debugging. **Read this before changing any agent/session code.**

---

## 1. LiveKit Agent Session Setup (v1.4.5)

### ✅ Correct Pattern
```python
session = AgentSession[CallUserData](
    llm=llm_plugin,
    stt=stt_plugin,
    tts=tts_plugin,
    userdata=userdata,
    user_away_timeout=10,
)
await session.start(room=ctx.room, agent=entry_agent)
```

### ❌ Do NOT use
- `silero.VAD.load()` — Sarvam STT (Saaras:v3) has **built-in voice activity detection**. Adding silero VAD causes double-detection and messes up turn handling.
- `turn_detection` / `MultilingualModel()` — not available in v1.4.5, and unnecessary with Sarvam.

### ✅ BackgroundAudioPlayer DOES work
```python
from livekit.agents import BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip

background_audio = BackgroundAudioPlayer(
    ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=3.0),
    thinking_sound=[
        AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
        AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=0.7),
    ],
)
userdata.background_audio = background_audio  # CRITICAL: prevent garbage collection!
await background_audio.start(room=ctx.room, agent_session=session)
```
- **Import from `livekit.agents`** — NOT from `livekit.agents.voice` (that path doesn't export it).
- Use `BuiltinAudioClip` enum values — NOT custom file paths.
- Call AFTER `session.start()`.
- **Volume is a GAIN MULTIPLIER, not 0-1.** Use `3.0` for ambient to be audible over SIP compression. Values ≤1.0 are inaudible over phone lines. Confirmed working at 3.0 in commit `746a063`.
- **Store ref on `userdata`** to prevent Python garbage collection from killing the background tasks.
- **Call `await background_audio.aclose()`** in shutdown to prevent Windows Proactor `WinError 10054` crashes.


---

## 2. Sarvam TTS Config

### ✅ Correct
```python
tts_plugin = sarvam.TTS(
    target_language_code="hi-IN",
    model="bulbul:v3",
    speaker="shreya",
    pace=1.65,               # 1.0 = default, 1.65 = natural fast pace
    enable_preprocessing=False,  # bulbul:v3 ignores this anyway
)
```

### ❌ Do NOT use
- `speech_sample_rate=8000` — not needed, let Sarvam handle it.
- `api_key=` param — reads from env automatically via `SARVAM_API_KEY`.

### TTS Speed (pace parameter)
- `pace` valid range: `0.5` to `2.0` (float)
- `1.0` = default speed (too slow for natural phone sales)
- `1.65` = recommended for natural-sounding sales call pacing
- Higher values make the agent sound rushed; lower values sound robotic

---

## 3. Sarvam STT Config

### ✅ Correct
```python
stt_plugin = sarvam.STT(
    language="hi-IN",
    model="saaras:v3",
    mode="codemix",
)
```

> **Note:** Saaras:v3 starts streaming audio chunks immediately after session.start(), even before the SIP participant connects. This is normal — it's listening to room audio from the start.

---

## 4. SIP Call Audio Establishment

### ✅ Correct — use `asyncio.sleep(5.0)`
```python
async def on_enter(self) -> None:
    await asyncio.sleep(5.0)  # SIP audio establishment delay
    await self.session.say(opener)
```

### ❌ Do NOT use
- `ctx.wait_for_participant()` — unreliable, sometimes the participant is already connected.
- `asyncio.sleep(2.0)` — too short for SIP, audio won't be ready.

---

## 5. Function Tools — Schema Compatibility

### ✅ Correct — `@function_tool` WITHOUT parentheses, every tool must have ≥1 parameter
```python
@function_tool
async def tag_lead(self, context: RunCtx, tag: str, notes: str = "") -> str:
    """Tag the lead outcome."""
    return f"Lead tagged as {tag}."
```

### ❌ Do NOT use
- `@function_tool()` with parentheses — different behavior in v1.4.5.
- **Zero-parameter tools** — Groq rejects JSON schemas where `required` is present but `properties` is missing. Always add at least one parameter (even `reason: str = "done"`).
- `EndCallTool()` from `livekit.agents.beta` — its schema is incompatible with Groq. Use a custom `tag_lead` + goodbye pattern instead.

---

## 6. Agent Handoffs

### ✅ Correct — return the Agent instance from a function_tool
```python
@function_tool
async def transfer_to_intro(self, context: RunCtx, response: str = "ok") -> "Step2_Intro":
    """Transfer to introduction."""
    return Step2_Intro()
```

### ❌ Do NOT use
- Returning `(agent, message)` tuples — that's a different SDK version pattern.
- Passing `chat_ctx=self.chat_ctx` manually — v1.4.5 handles context transfer automatically.

---

## 7. Entrypoint Pattern

### ✅ Correct
```python
async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    # Try job metadata first, fallback to room metadata
    raw = ctx.job.metadata or ""
    meta = json.loads(raw) if raw.strip() else {}
    if not meta:
        raw = ctx.room.metadata or ""
        meta = json.loads(raw) if raw.strip() else {}

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

### ❌ Do NOT use
- `ctx.room.metadata` alone — metadata may come from either `ctx.job.metadata` or `ctx.room.metadata` depending on dispatch mode.
- `rtc_session` decorator — doesn't exist in v1.4.5.

---

## 8. Environment Variables

```env
LIVEKIT_URL=wss://...livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
SIP_OUTBOUND_TRUNK_ID=...
OPENAI_API_KEY=...
SARVAM_API_KEY=...
```

- **Must load `.env.local`** at the top of every entry file: `load_dotenv(dotenv_path=".env.local")`
- Agent workers read `LIVEKIT_URL` etc. automatically, but only if dotenv is loaded first.

---

## 9. LLM Choice

- **Current production:** `openai.LLM(model="gpt-4.1-mini")` — fast, cheap, follows instructions well.
- **Previous:** Groq `llama-3.3-70b-versatile` — has strict JSON schema validation for tools.
- **If LLM errors on tool schemas**, the LLM will retry infinitely and the agent goes silent.

---

## 10. Call Termination (SIP Disconnect)

### ✅ Correct — use `session.shutdown()` in CloserAgent
```python
# In CloserAgent.on_enter():
await self.say_script(CLOSING_GOOD_WISHES)
await asyncio.sleep(2.0)  # Let TTS drain
self.session.shutdown()    # Gracefully ends session → triggers cleanup
```

### ❌ Do NOT use
- `ctx.room.disconnect()` — this is an async method, calling it synchronously or from wrong context fails silently.
- Manual `room.disconnect()` without `session.shutdown()` — leaves the session running, cost tracker keeps logging.

### Session close event
```python
@session.on("close")
def on_session_close():
    # Write final cost report + transcript here
    write_cost_report(...)
```

---

## 11. Agent Profile in Prompts (Gender/Name)

### ✅ Always inject agent identity into system instructions
All agents that generate free text must know:
- Agent name (श्रेया)
- Agent gender (female)
- Correct Hindi verb forms (बोल रही, ले सकती, चाहती, etc.)

This prevents the LLM from defaulting to masculine forms (बोल रहा, ले सकता).

### Pattern
```python
AGENT_PROFILE = """
YOUR IDENTITY:
- Your name is {agent_name}. You are a FEMALE sales representative.
- Always use FEMALE Hindi verb forms: बोल रही (not रहा), ले सकती (not सकता), चाहती (not चाहता)
- When the script uses {bol_raha}, {le_sakta}, {chahta} etc, those are already gender-correct. USE THEM.
"""
```

---

## 12. Script-Following vs AI Generation

### When to hardcode scripts (say_script):
- Greetings, introductions, product pitches with specific wording
- Pricing mentions, legal disclaimers
- Goodbye messages
- Any line where exact wording matters

### When to let AI generate:
- Responding to unexpected questions
- Step4_ShareProduct (product pitch from KB data)
- Handling objections naturally
- Summarizing feedback

### ✅ For scripted agents, use "SILENT listener" pattern:
```python
instructions = (
    "You just said a greeting. LISTEN for the response. "
    "Do NOT speak — only call the appropriate tool."
)
```
The LLM only decides WHICH tool to call, never generates speech.

### ⚠️ For AI-generating agents, use LANGUAGE_RULES + AGENT_PROFILE:
```python
instructions = f"{LANGUAGE_RULES}\n{AGENT_PROFILE}\n\nYour task: ..."
```
This ensures gender-correct, paced, natural Hinglish.

---

## 13. STT Misinterpretation ("Ji" → "JEE")

### Known issue
Sarvam Saaras:v3 in `codemix` mode can misinterpret Hindi filler words as English acronyms:
- "जी" (ji = yes/respectful) → "JEE" (exam name)
- "हाँ" (haan = yes) → "HAN" or similar

### Mitigation
- In `classes_shared` tool and KB routing, add guards against common false positives
- Don't route on single short words — require minimum context
- Add "ji" to tool descriptions as an affirmative, NOT as JEE

---

*Last updated: 2026-04-03*
