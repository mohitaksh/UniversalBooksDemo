# UniversalBooks — AI Voice Calling System
**Development Progress Report** — April 2026

---

## What Has Been Built

### Infrastructure & Core Engine
A production-grade outbound calling system live on LiveKit Cloud with Indian regional servers, integrated with a SIP telephony trunk for PSTN calls across India. A REST API accepts a single trigger (`name`, `phone`, `call_type`) and autonomously places the call, converses, and closes — with zero human involvement.

- Sarvam AI **Speech-to-Text** (`Saaras v3`) — native Hindi/Hinglish transcription
- Sarvam AI **Text-to-Speech** (`Bulbul v3`) — natural Hindi female voice with correct gender verb conjugations
- Groq **LLaMA 3.3 70B** — ultra-low latency decision engine
- Ambient office background sounds during thinking pauses — makes calls feel more human
- Silence detection with automatic re-engagement if the prospect goes quiet
- Per-call cost tracking in INR (STT, TTS, LLM, telephony)

### Multi-Agent Swarm — 10 Complete Call Flows

Rather than one large AI with a single massive prompt, the system runs **10+ specialized micro-agents per call**, each with a focused role. Context transfers seamlessly between them.

| Call Type | Purpose |
|-----------|---------|
| New Teacher (Coaching / Tuition) | Cold call — brand new prospect |
| Digital Sample Follow-up × 2 | After WhatsApp sample shared |
| Physical Sample Follow-up × 2 | After book dispatch / delivery |
| Post-Visit Follow-up | After in-person sales visit |
| Contacted by Call / Physically | Re-engagement follow-ups |
| Referral | Referred prospect calling |

**Every flow handles:** right person / wrong number / busy → permission → product pitch → sample → callback scheduling → goodbye.

### Knowledge Base — 23 Product Modules

Dynamic KB loaded **only when needed**. When a teacher says *"I teach Class 9 and 10"*, the system pulls **only** those modules (`class_9`, `class_10`, `cbse_10_pyq`, `worksheets`) — not all 23. The AI then generates a natural, accurate product pitch from that data.

Modules cover: Class 6–12, NEET, JEE, JEE Advanced, CBSE PYQs, Worksheets, KCET, MHT-CET, EAPCET, CUET, DPPs, Crash Course, Formula Handbook, Company Overview.

### Objection Handling — Fires from Any Step

Mid-conversation objections resolved without breaking the flow. After resolution, the call **returns to exactly where it was.**

| Objection | Handled |
|-----------|---------|
| "Aapko mera number kahan se mila?" | ✅ |
| "Kya aap AI/robot ho?" | ✅ |
| "Main abhi class mein hun" | ✅ → Reschedule |
| "Dobara mat karna" | ✅ → DNC webhook |

### N8N Webhook Integrations

Five automation triggers wired and live:
- **Lead tagging** — every call outcome logged
- **Callback scheduling** — task created in backend
- **WhatsApp sample dispatch** — fires only on confirmed "yes"
- **Delivery check** — when physical book not received
- **Do Not Call** — prospect removed from list

---

## What's Next

| Item | Status |
|------|--------|
| Prompt tuning for natural Devanagari pronunciation | Upcoming |
| Voice pacing & speech rhythm optimization | Upcoming |
| N8N workflow build-out (CRM tagging, WA dispatch, tasks) | In progress |
| WhatsApp follow-up agent (post-call nurturing) | Upcoming |
| Call recordings archive + QA review dashboard | Upcoming |

---

*UniversalBooks Voice AI — April 2026*