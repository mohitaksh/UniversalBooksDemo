# Learnings regarding Outbound Script Agents

This document highlights the design patterns used to convert simple English scripts into robust LiveKit Agents.

## 1. Wait For Pickup (Silent Start)
A recurring issue with outbound dialers is wasting TTS (and LLM) costs on ringing phones. 

**Solution:** `Step1a_SilentWait`
```python
class Step1_Greet(BaseUBAgent):
    # ...
    instructions="Wait silently for the caller to pick up and speak first. Do not speak. When they say anything (hello, hanji), call `caller_picked_up`."
```
By explicitly telling the LLM to **wait and NOT speak**, the agent will quietly listen to the audio stream. Once the STT detects an utterance passing the `VAD`, the LLM triggers the `caller_picked_up` tool, allowing us to synchronously jump to Step 1b and fire the initial script.

## 2. STT Short-Circuit Guards
Often, the STT (Saaras:v3) converts common Hindi affirmative fillers into domain-specific entities. For example, "जी" (Ji) transcribed as "JEE" (Joint Entrance Examination).

**Solution:** 
```python
@function_tool
async def classes_shared(self, context: RunCtx, classes_and_exams: str) -> "Step3_ShareSample":
    # ── STT Guard: filter false positives ──
    cleaned = classes_and_exams.strip().lower()
    false_positives = {"ji", "jee", "haan", "ha", "ok", "theek hai"}
    if cleaned in false_positives or len(cleaned) <= 3:
        await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं?")
        return Step2_Intro()
```
By interecepting the tool execution and manually testing the parameter length/value, we can force a polite repeat without relying on the LLM to understand the nuance.

## 3. Strict Intents
Open domain questions (e.g., "What classes do you teach?") will often yield vague human responses "bahut padhai hoti hai" or "coaching chalti hai".

If the LLM has only `success` or `busy` tools available, it will wrongly select the closest semantic fit, failing catastrophically (e.g. routing a vague answer to scheduling a callback).
**Solution:** `unclear_response` Tool
Provide an explicit "catch-all" tool for when the criteria isn't met, accompanied with direct routing rules:

```markdown
ROUTING RULES (follow strictly):
1. If specific classes -> classes_shared
2. If vague (bahut, sab hota hai) -> unclear_response
3. If busy -> person_busy
```

## 4. Devanagari Translation
Translate scripts using phonetic/Hindi script (Devanagari) where native, but keep technical/industry terms in English letters (e.g. `books publish`, `CBSE`). This achieves the best enunciation from `saaras codemix / bulbul v3`.
```python
S2_INTRO = "मै Universal Books से बात कर रही हूँ, हम Errorless Self Scorer जैसी books publish करते हैं जो CBSE, JEE और NEET exams के लिए design की गयी हैं।"
```
