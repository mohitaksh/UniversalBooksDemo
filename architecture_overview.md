# UniversalBooks Voice AI: Ultra-Detailed Architecture & Code Flow

This document is a comprehensive, deep-dive technical reference into the UniversalBooks multi-agent Voice AI outbound calling system. It breaks down the exact architectural design pattern, the sequence of execution across files down to the millisecond, and code-level specifics.

---

## Part 1: High-Level Architecture Strategy

We employ a **Multi-Agent State Machine (Swarm)** pattern using LiveKit Agents v1.4.5. 

### Why Multi-Agent?
Instead of passing a massive, 2000-token multi-step instruction prompt to a single LLM (which incurs high latency, high tracking errors, and hallucination), the system breaks every discrete conversational turn into its own isolated `Agent` class.
*   **Precision**: By confining instructions to: *"You just asked about their classes. Wait for a response, then categorize it."* the LLM executes perfectly.
*   **Deterministic Scripting**: The LLMs *do not* generate speech at the start of turns. The system uses hard-coded text (`say_script`) synthesized via TTS to ensure brand safety, accurate pricing dictation, and zero latency. The LLM is strictly used as an **intent router** and **RAG-based explainer** in specific middle steps.
*   **Context Truncation**: As the agent traverses steps, we forcefully truncate the context window (retaining only the last ~6 messages) to prevent API payload bloat, ensuring ultra-fast Groq API inference.

### Core Stack Providers
1.  **Telephony Broker**: LiveKit Cloud / SIP Trunking.
2.  **App Server**: FastAPI (`server.py`).
3.  **LLM Inference**: Groq (`llama-3.3-70b-versatile`) — Chosen for sub-second tool-calling.
4.  **Speech-to-Text (STT)**: Sarvam AI (`saaras:v3`) — Chosen because of native Hinglish support and built-in edge VAD (Voice Activity Detection), allowing us to discard local VAD models (like Silero) entirely.
5.  **Text-to-Speech (TTS)**: Sarvam AI (`bulbul:v3`) — Chosen for natural Indian accents.
6.  **Automation/Webhooks**: n8n local instance for post-call logging.

---

## Part 2: File-by-File Deep Dive

### 1. `server.py` — The Dispatch Server
This FastApi server runs perpetually on port 8080.
*   **Role**: It is the bridge between the internal application and LiveKit's SIP infrastructure.
*   **Flow**:
    1. An HTTP POST request arrives at `/call` with payload `{"name": "...", "phone_number": "...", "call_type": "new_teacher..."}`.
    2. It authenticates with LiveKit using `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`.
    3. It provisions a unique LiveKit Room: `call_<phone>_<timestamp>`.
    4. It initiates an outbound SIP dial via `CreateSipParticipantRequest`.
    5. **Crucial Metatdata**: It serializes the user data into a JSON string and attaches it to the `.attributes` of the SIP participant. This allows the backend worker to know *who* it is calling.

### 2. `main_agent.py` — The Master Supervisor
This script (`python main_agent.py dev`) operates as a LiveKit Worker. It listens passively to LiveKit Cloud. When `server.py` connects a SIP participant to a room, LiveKit wakes up this worker and triggers `entrypoint()`.

*   **Job Bootstrapping**:
    *   Reads `ctx.job.metadata` to extract `caller_name`, `phone_number`, and `call_type`.
    *   Creates a `CostTracker` assigned to a unique `call_id`.
    *   Initializes `setup_loggers()` (from `logger.py`) building the 6-file metric traces in the `logs/` directory.
    *   Creates a global `CallUserData` object. This relies on Dependency Injection — it is passed to the `AgentSession` so that *every* isolated sub-agent can read and mutate global state (like exam type, or lead tags).
*   **Plugin Setup**:
    *   Initializes `sarvam.STT` and `sarvam.TTS`. Note: we specifically omit `speech_sample_rate` and local VAD, deferring all audio processing intelligence to Sarvam.
*   **Session Management**:
    *   Initializes `AgentSession`. We use `user_away_timeout=10` to trigger a re-engagement hook if the user goes absolutely silent for 10 seconds.
    *   Hooks into `@session.on("metrics_collected")` to intercept every granular token count, TTS character count, and audio byte streamed, flushing it immediately to `CostTracker`.
*   **Background Audio**:
    *   Instantiates `BackgroundAudioPlayer` feeding continuous `OFFICE_AMBIENCE` and `KEYBOARD_TYPING` mixed audio into the SIP stream, simulating an active telecaller environment.
*   **Room Teardown**:
    *   Watches for `ctx.room.on("participant_disconnected")`. Once triggered, stops logs, cancels background async tasks, and dumps the beautiful formatting of `write_cost_report()`.

### 3. `models.py` & `logger.py` — State & Telemetry
*   **`CallUserData`**: A Python dataclass that holds the `call_type`, the active `CostTracker`, the assigned `VoiceProfile` (so TTS speakers remain consistent across different agents), and tracks states like `exam_type` and `callback_time`.
*   **`CostTracker`**: Has real-time pricing constants. Every time Groq returns an API call, `log_llm()` fires, multiplying tokens by hardware costs. It aggregates `stt_active_seconds` and `tts_chars_total`.
*   **`setup_loggers`**: Orchestrates 6 Python standard loggers:
    1.  `call_XXX.log`: The unified chronological debug trace.
    2.  `...brief.log`: A clean view of function calls and major events.
    3.  `...tokens.log`: Line-by-line incrementing of tokens.
    4.  `...costs.log`/`costs.json`: Final monetary aggregations.
    5.  `...llm_transcript.log`: A raw dump of the JSON boundaries passing back and forth to Groq API.
    6.  `...transcript.txt`: The human-readable string conversation between "Agent" and "User".

### 4. `agents/base_agent.py` — The Universal Primitive
Every agent in the swarm inherits `BaseUBAgent`.
*   **`self.say_script()`**: Instead of asking the LLM to generate text, the system uses `{caller_name}` dynamic variable injection via `self.fmt()` and pushes hardcoded strings directly to `self.session.say()`.
*   **`self.ud`**: A rapid property exposing `self.session.userdata`.
*   **`_transfer_to()` API**: In a swarm, to jump to a new agent, LiveKit traditionally requires manual context splicing. The `_transfer_to` method handles Deep-Copying the existing `chat_ctx`, forcefully truncating it to the last 6 messages (`_truncate_chat_ctx`), appending the history to the *new* agent, and returning it.
*   **SIP Audio Delay**: Overridden `on_enter()` functions often include `await asyncio.sleep(5.0)`. SIP trunks take around 3-5 seconds to negotiate packet audio. Without this sleep, the agent begins speaking into the void before the user's telecom provider has unmuted the receiver.

---

## Part 3: Real-Time Execution Path (Action-by-Action Matrix)

Let's trace a call assigned `call_type = "new_teacher_coaching"` (using files in `agents/new_teacher/`).

### Step 1: The Operator Engages (`Step1_Greet`)
*   **T=0.0s**: `main_agent.py` calls `await session.start(agent=Step1_Greet())`.
*   **T=0.1s**: `Step1_Greet.on_enter()` is triggered.
*   **T=0.1s - 5.1s**: The system executes `asyncio.sleep(5.0)` allowing SIP audio routing to bridge successfully.
*   **T=5.1s**: `await self.say_script("Hello, kya meri baat {caller_name} se ho rahi hai?")` evaluates.
*   **T=5.5s**: TTS streams audio into the LiveKit room. The user hears it. The agent falls silent.
*   **T=7.0s**: User says "Haan boliye".
*   **T=7.2s**: Sarvam STT emits `UserTranscribedEvent`. The Groq API analyzes the transcript against `Step1_Greet`'s system prompt (*"If they confirm, call identity_confirmed"*).
*   **T=8.0s**: Groq responds with JSON calling the tool `identity_confirmed`.
*   **T=8.1s**: The python tool executes, logging the event, and executing `return Step2_Intro()`.
*   **T=8.2s**: LiveKit intercepts the return, pauses `Step1`, swaps the prompt, and mounts `Step2_Intro()`.

### Step 2 & 3: Information Retrieval
*   `Step2_Intro.on_enter()` fires, saying the company pitch, then returning `Step3_AskClasses()`.
*   `Step3_AskClasses.on_enter()` fires, asking what classes they teach.
*   User replies: "I teach 11th and 12th CBSE."
*   Groq API triggers `@function_tool async def classes_shared(self, ctx, classes_and_exams="11th and 12th CBSE")`.
*   **The KB Mapping**: Inside the tool, python invokes `resolve_kb_modules("11th and 12th")`. The logic cross-references the dictionary and returns `["class_11", "class_12"]`.

### Step 4: RAG & Dynamic Generative Pitch (`Step4_ShareProduct`)
*   `Step3` invokes `return Step4_ShareProduct(kb_modules=["class_11", "class_12"])`.
*   When `Step4` instantiates, its `__init__` constructor executes `kb_to_prompt()` to read the raw text from `knowledge/class_11.txt` and `knowledge/class_12.txt`.
*   It injects these paragraphs directly into the `instructions` variable (the overarching LLM prompt) alongside the rule: *"Generate 3 sentences using this product data natively in Hinglish."*
*   `on_enter()` triggers `self.session.generate_reply()`.
*   Unlike Steps 1-3, **this is pure LLM generation**. The LLM reads the KB and formulates an on-the-fly vocal response pitching the exact books available for Class 11 and 12.
*   The LLM finishes by monitoring user sentiment. If they are interested, it calls `offer_sample`.

### Step N: The Terminus Wrappers (`SchedulerAgent` & `CloserAgent`)
All paths in every isolated `.py` flow (whether New Teacher, Referral, Follow-Up) ultimately collapse into shared terminal nodes located in `agents/shared/`.

*   **Routing to Close**: If user says "Not interested", Groq triggers the LLM tool `not_interested` which executes `return CloserAgent(tag="Not Interested")`.
*   **`CloserAgent.on_enter()`**:
    *   Executes `self.say_script(CLOSING_GOOD_WISHES)`.
    *   Simultaneously queries `httpx.AsyncClient().post(...)` to fire the webhook over to the N8N instance, delivering a JSON payload containing the user's phone, exact callback time, specific exam types detected, and lead designation (e.g. "Not Interested").
    *   Issues `await asyncio.sleep(5.0)`. This guarantees that the final vowels of the TTS `CLOSING_GOOD_WISHES` finish emitting out of the SIP socket.
    *   Issues `ud.ctx.room.disconnect()`.
*   **Finalization**: `room.disconnect()` signals LiveKit Cloud to drop the SIP Trunk terminating the GSM phone call. It ripples back down to `main_agent.py`, firing `@ctx.room.on("disconnected")`, which computes the final cost aggregation, dumps `costs.json`, and elegantly exits the python process, freeing up the port assignment.

---

## 5. Critical Code Mandates

When extending this architecture, the following syntax mandates are strictly enforced:

### The Groq JSON Strictness
Groq's OpenAI-compatible router has rigorous JSON schema validators.
*   A tool requires at least ONE argument. A tool like `def hang_up(self, ctx: RunCtx):` will crash the application because Groq demands a non-empty `properties` dictionary. It must be written as `def hang_up(self, ctx: RunCtx, response: str = "ok"):`.
*   For this reason, we stripped LiveKit's default `EndCallTool()` from the project.

### Tool Decorator Syntax
*   `@function_tool()` -> **FAILS**.
*   `@function_tool` -> **WORKS**.

### Swarm Context Returns
*   To transfer agents, Python must return an *instance*: `return NextStepAgent()`.
*   Do *not* use explicit transfers inside tools (`self._transfer_to(agent)`). While available natively, simply yielding the class object guarantees LiveKit SDK safely drains the TTS queue before ripping the context away.

### Asynchronous Concurrency
*   Do not `time.sleep()`. Always `await asyncio.sleep()`.
*   Ensure HTTP webhooks to N8N are wrapped in `try/except` with a tight timeout (`httpx.AsyncClient(timeout=5)`) so webhook server failures do not arbitrarily prolong the hanging of a live phone call.
