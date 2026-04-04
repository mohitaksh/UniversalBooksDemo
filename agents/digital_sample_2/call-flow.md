# 📞 Digital Sample 2 (Follow-up 1) Flow

**Persona**: UniversalBooks Agent  
**Context**: Following up with a teacher who previously received the digital sample but we are now asking if they want a physical copy.

| Step | Interaction | Logic & Transitions |
|---|---|---|
| **Step 1a (Greet)** | Says **"Hello?"** silently waits | `caller_picked_up` -> Step 1b |
| **Step 1b (Confirm)** | "Hello kya meri baat Name sir se ho rahi hai?" | Confirm -> Step 2<br>`wrong_person` -> Close |
| **Step 2 (Recall/Ask)** | "Aapne time diya tha... kaisa laga content?" | `files_not_seen` -> Webhook resend, Free test papers -> Close<br>`files_seen` -> Step 4 |
| **Step 4 (Feedback & Ask Physical)** | "Kya aap physical book sample bhi chahte hai?" | `wants_physical_sample` -> Step 5<br>`declines_physical_sample` -> Close |
| **Step 5 (Dictation)** | "Sure sir, address dictate karde..." | `finish_address_dictation` -> Saves to tracker -> SchedulerAgent (Senior calls in 1 hr) |

### 🛑 Global Objections
- **Busy**: Scheduler
- **Not Interested**: Close
- **Source/Bot**: Re-listen
