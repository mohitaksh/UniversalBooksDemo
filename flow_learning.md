# UniversalBooks Voice AI — Advanced Flow Architecture & Learnings

This document captures the rigorous, production-grade logic rules and architectural conventions developed during the `new_teacher` agent deployment. Every outbound AI workflow must abide by these rules to ensure high robustness, precise routing, maximum TTS enunciation, and strict cost optimization.

---

## 1. Silent Start & Initial Greeting (Cost Optimization)

### The Flaw
Older agents used `await asyncio.sleep(5.0)` to delay speaking while the SIP connected. If the agent immediately fired `S1_GREETING`, the audio would chop off during the VoIP bridging. If the human didn't pick up, the LLM and TTS would both still incur costs on voicemails/empty rooms.

### The Standard
- Every flow must begin with a dual-step greeting structure: `Step1_Greet` and `Step1b_ConfirmIdentity`.
- **`Step1_Greet`** acts as a lightweight proactive inviter. It natively says `"Hello?"` in its `on_enter()` function using `self.say_script("Hello?")`. 
- **Prompt Isolation:** The instruction prompt forbids any LLM hallucinated speech. It specifies: *"You just said 'Hello?'. Listen carefully for the person to speak. When the person replies, call `caller_picked_up` IMMEDIATELY. Do NOT generate any speech."*
- **Action:** Only once the human speaks triggers the actual script (`Step1b_ConfirmIdentity`), which carries the actual S1 string constraint (`S1_GREETING` containing the heavy TTS workload).

```python
# GOOD
class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions="You just said 'Hello?'. Wait for them to respond. Do NOT generate speech.",
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script("Hello?")
```

---

## 2. Granular Intent Routing & Listeners (The Loop Fix)

### The Flaw
Historically, agents combined the "Say Script" block and "Wait for User Input" block into the single `on_enter()` phase of a single agent class `Step2_Intro`.
If the user gave a vague response ("Sorry, kya bola?") and the agent triggered the `unclear_response` tool, it would return `Step2_Intro()`. Returning the *same* agent class caused `on_enter()` to execute again. The agent would awkwardly read out the entire 30-second intro from the top, causing an infinite loop.

### The Standard
- **Separation of Concerns:** Split the phase into `Step2_Talk` and `Step2_Listen`. 
- `Step2_Talk` delivers the long intro logic in `on_enter()` then natively transitions.
- Or, if keeping it in one agent (`Step2_Intro`), any tool that re-prompts the user (like `unclear_response` saying *"Sir matlab kya padhate ho?"*) must **return a dedicated listener class** (e.g. `Step2_ListenClasses`).
- **Listener Classes** have `pass` inside their `on_enter()`. They exist purely to house the transition tools (`classes_shared`, `unclear_response`, `not_interested`) without triggering a macro script rerun.

```python
# Listener Pattern
class Step2_ListenClasses(BaseUBAgent):
    async def on_enter(self) -> None:
        pass # Crucial: NO SPEECH HERE

    @function_tool
    async def unclear_response(self, context: RunCtx, what: str) -> "Step2_ListenClasses":
        await self.say_script("Can you specify?")
        return Step2_ListenClasses() # Safe loop
```

---

## 3. Global Objection Handlers in Every Listen Step

At absolutely *any* stage during a phone call, a human may interrupt and say:
1. "Mai busy hu."
2. "Mujhe call mat karo."
3. "Tumhara number kahan se mila?" / "Tum AI ho kya?"

### The Standard
Every single agent block that listens to the user must explicitly provide these three tools:
- **`not_interested`**: Calls `await self.say_script(S_NOT_INTERESTED)` and returns `CloserAgent(tag="Not Interested")`.
- **`person_busy`**: Calls `await self.say_script(S_BUSY)` and returns `SchedulerAgent()`.
- **`handle_objection`**: Dynamically answers the "where did you get my number / are you a bot" concern using the pre-seeded `S_NUMBER_SOURCE` / `S_AI_RESPONSE` texts. It then routes perfectly to an `ObjectionAgent` which silently shifts the LLM context back to the original listener.

---

## 4. Non-overlapping Webhooks & Redundancies

### The Flaw
The flow required offering a WhatsApp sample. `Step4` described the book and handed off to `Step6`. `Step6` said "Okay I shared it" and handed off to `SampleSenderAgent`. `SampleSenderAgent` said "Should I send the sample?" The user was subjected to 3 disjointed agent hops, breaking conversational cohesion and contradicting itself.

### The Standard
- Avoid using generic agents (like `SampleSenderAgent`) if the overarching script already incorporates sending samples into its core narrative.
- Instead, perform actionable operations (N8N webhook triggers for Whatsapp, CRM logging) **under the hood natively** inside the exact `@function_tool` transition loop, masking the technical complexity from the voice flow.

```python
# Silent Webhook Integration in Tool
@function_tool
async def send_whatsapp_sample(self, context: RunCtx, response: str) -> "BaseUBAgent":
    if N8N_WHATSAPP_SAMPLE_WEBHOOK_URL:
        asyncio.create_task(httpx.AsyncClient().post(URL, json={...}))
    
    await self.say_script("ठीक है सर, मै भिजवा देती हूँ।")
    return CloserAgent(tag="Sample Mailed")
```

---

## 5. Devnagari & English Phonetics (Sarvam / Bulbul v3 Native constraints)

Strict formatting dictates how string constants are passed into the `self.say_script()` TTS pipeline.

### The Standard
To maximize human-likeness and inflection:
1. **True Hindi words** must be in Devnagari (e.g., क्या, मै, हूँ). **Do not use latin script for Hindi** (e.g., "Kya mai hun" sounds robotic/English-shifted).
2. **Key Industry terms, numbers, and nouns** must remain pristine English (e.g., Universal Books, CBSE, NEET, JEE, WhatsApp, Class 10th).
3. **Punctuation matters**: Use double dots `..` to enforce a micro-pause. Use question marks `?` to force an upward inflection.

*Example string logic (Hybrid):*
```python
S1_GREETING = "Hello, क्या मेरी बात {caller_name} sir से हो रही है? Sir मेरा नाम {agent_name} है,"
```

---

## 6. Type-Hinting LLM Routing Triggers

When an LLM maps user intent to a tool, it uses parameter types to extract variables. 
Always include generic "fallback" defaults for parameters to force the LLM to easily trigger actions.

```python
# GOOD: The LLM doesn't have to struggle to figure out the parameter type to trigger this tool
@function_tool
async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
    ...
```

---
*Following these guidelines ensures every new generated campaign operates identically, preserving low bounds on API toxicity, loop traps, and stilted text generation.*
