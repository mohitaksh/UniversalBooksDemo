# 📞 Digital Sample Follow-Up Flow

**Persona**: UniversalBooks Agent  
**Context**: Re-calling a teacher who has *already* received a digital sample on WhatsApp.

| Step | Interaction | Logic & Transitions |
|---|---|---|
| **Step 1a (Greet)** | Says **"Hello?"** silently waits | `caller_picked_up` -> Step 1b |
| **Step 1b (Confirm)** | "Hello kya meri baat Name se ho rahi hai?" | Confirm -> Step 2<br>`wrong_person` -> Close |
| **Step 2 (Recall/Ask)** | "Pichli baar whatsapp par share kiya tha... files dikhi?" | `files_not_seen` -> Webhook resend -> Close<br>`files_seen` -> Step 4 |
| **Step 4 (Feedback)** | "Aapka kya feedback hai content kaisa laga?" | `details_positive` -> S5 Positive -> SchedulerAgent<br>`details_hesitant` -> S5 Hesitant -> CloserAgent |

### 🛑 Global Objections
Available globally at any `Listen` step:
- **Busy**: "Koi baat nahi baad me karenge" -> Scheduler
- **Not Interested**: "No issues sir" -> Closer (Not Interested)
- **Source/Bot**: "Number database se liya / Mai AI assistant" -> Re-listen
