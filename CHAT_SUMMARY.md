# Multi-Agent Voice AI - Stabilization & Fixes Chat Summary
**Date:** April 4, 2026

## 1. Architectural Changes & Handoff Refactoring
*   **Handoff Pattern Update:** Standardized all peripheral agent flows (e.g., eight separate flow agents) to the `v1.4.5` handoff pattern. Instead of returning a tuple or manually passing `chat_ctx`, the agents now simply return an `Agent` instance from a `@function_tool` (e.g., `return Step2_Intro()`) and LiveKit handles the state transfer automatically.
*   **Shared Agent Swarm:**
    *   **ObjectionAgent:** Created a centralized handler in `agents/shared/objection_handler.py` for interruptions like "kahan se number mila?", "are you AI?", or "I am busy". It supports returning back to the *calling agent* natively when it finishes.
    *   **SampleSenderAgent:** Extracted WhatsApp sample logic into a dedicated agent (`agents/shared/sample_sender.py`) that handles asking for permission and firing the N8N webhook.

## 2. Audio & Pacing Fixes
*   **SIP Audio Delay (`main_agent.py` & Base Agent):** Added a mandatory `asyncio.sleep(5.0)` to all `Step1_Greet` agents to verify SIP audio is completely routed before the agent starts speaking. `wait_for_participant()` was found to be unreliable.
*   **TTS Pacing (`main_agent.py`):** Updated Sarvam TTS `pace` from the default `1.0` (too slow/robotic) to `1.65` for a much more natural, fast-paced sales execution.

## 3. Tool & LLM Integrations
*   **LLM Provider Swap:** Moved from Groq to OpenAI (`gpt-4.1-mini`). Groq had very strict JSON tool schema bounds, while OpenAI handles tool bounds much better natively. Updated `config.py` with `OPENAI_API_KEY` and updated the `livekit-plugins-openai` pip module.
*   **Prompt Language Rules & Profiles (`new_teacher/agent.py`):**
    *   **Devanagari Instructions:** Centralized strict instructions natively forcing the AI to generate responses in Devanagari Hinglish.
    *   **Gender Profiles (`AGENT_PROFILE`):** Added strict profile rules injecting the agent's name (Shreya) and explicitly enforcing female Hindi verbs (e.g., "बोल रही हूँ", "दे सकती", "समझ गयी"). Prevents masculine defaults.
*   **STT Misinterpretation Guards (`new_teacher/agent.py`):** Fixed an issue where the Sarvam codemix STT misinterpreted affirmative fillers like "ji" as the exam name "JEE" by adding a custom guard checking for strings ≤3 characters or matching known affirmations (ji, haan, ok) before passing to KB routing.

## 4. Disconnect Logic & Call State Management
*   **SIP Call Disconnection (`closer.py`):** Fixed the bug where the call wouldn't hang up after saying goodbye. Swapped out the failing asynchronous `ctx.room.disconnect()` calls directly for `self.session.shutdown()`, which correctly drains audio, ends the session, and triggers LiveKit cleanup bindings.
*   **Cleanup Binding (`main_agent.py`):** Bound end-of-call metric printing and cleanup routines explicitly to `@session.on("close")` instead of unreliable room participant disconnection bindings.

## 5. Webhook Configurations
*   **N8N Integration:** Linked up `N8N_WHATSAPP_SAMPLE_WEBHOOK_URL`, `N8N_DELIVERY_CHECK_WEBHOOK_URL`, `N8N_DNC_WEBHOOK_URL`, and `N8N_TAG_LEAD_WEBHOOK_URL` in `config.py`.
*   **Metrics Integration (`models.py`):** Updated `CostTracker` inputs with standard rates: USD $0.4 / 1M Input and $1.6 / 1M Output, matching the `gpt-4.1-mini` baseline.

## 6. Documentation
*   **Learnings (`learnings.md`):** Updated the global learnings list with the explicit API requirements across Session Loading, TTS metrics, Prompt engineering strategies (e.g., silent listener vs active generative models), and termination workflows.
*   **Progress Report (`CLIENT_PROGRESS_REPORT.md`):** Created a succinct 2-page progress report mapping completed features against remaining blockers (prompt optimization, pacing testing, and dashboard tracking).
