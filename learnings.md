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
    speaker="shubh",
)
```

### ❌ Do NOT use
- `speech_sample_rate=8000` — not needed, let Sarvam handle it.
- `api_key=` param — reads from env automatically via `SARVAM_API_KEY`.

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

## 5. Function Tools — Groq Schema Compatibility

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
async def transfer_to_intro(self, context: RunCtx) -> Agent:
    """Transfer to introduction."""
    return await self._transfer_to("intro", context)
```

Or use `session.update_agent()` for programmatic (non-LLM) transfers:
```python
self.session.update_agent(self.session.userdata.personas["identity_confirmer"])
```

### ❌ Do NOT use
- Returning `(agent, message)` tuples — that's a different SDK version pattern.
- Lazy imports inside function_tool — pre-instantiate all agents in entrypoint.

---

## 7. Entrypoint Pattern

### ✅ Correct
```python
async def entrypoint(ctx: JobContext):
    meta = json.loads(ctx.job.metadata or "{}")  # NOT ctx.room.metadata
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    # ... setup ...
    await session.start(room=ctx.room, agent=entry_agent)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

### ❌ Do NOT use
- `ctx.room.metadata` — metadata comes from `ctx.job.metadata` (dispatch metadata).
- `rtc_session` decorator — doesn't exist in v1.4.5.
- `agent_name="UniversalBooksAgent"` in WorkerOptions — only if LiveKit Cloud dispatch is configured for that name. Default empty string works with auto-dispatch.
- `room_io.RoomOptions` — not needed.

---

## 8. Environment Variables

```env
LIVEKIT_URL=wss://...livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
SIP_OUTBOUND_TRUNK_ID=...
GROQ_API_KEY=...
SARVAM_API_KEY=...
```

- **Must load `.env.local`** at the top of every entry file: `load_dotenv(dotenv_path=".env.local")`
- Agent workers read `LIVEKIT_URL` etc. automatically, but only if dotenv is loaded first.

---

## 9. LLM Choice

- **Working demo used:** `aws.LLM(model="global.anthropic.claude-sonnet-4-6", region="ap-south-1")`
- **Groq works but:** has strict JSON schema validation for tools. Every tool needs ≥1 parameter.
- **If Groq errors on tool schemas**, the LLM will retry infinitely and the agent goes silent.

---

## 10. Pre-instantiate All Agents

The working code creates ALL agents in `entrypoint()` and stores them in a `personas` dict:

```python
agents = {
    "greeter": GreeterAgent(...),
    "identity_confirmer": IdentityConfirmerAgent(...),
    # ... all agents pre-created ...
}
userdata.personas = agents
```

Handoffs then reference `userdata.personas["agent_name"]` — no lazy imports, no class instantiation inside function_tools.

---

*Last updated: 2026-04-02*
