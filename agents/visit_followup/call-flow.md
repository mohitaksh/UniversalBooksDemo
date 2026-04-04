# 🤝 Visit Follow-Up Flow

**Persona**: UniversalBooks Agent  
**Context**: Following up with a teacher who was recently visited in-person by a UniversalBooks team member to take feedback.

| Step | Interaction | Logic & Transitions |
|---|---|---|
| **Step 1a (Greet)** | Says **"Hello?"** silently waits | `caller_picked_up` -> Step 1b |
| **Step 1b (Confirm)** | "Hello kya meri baat Name sir se ho rahi hai?" | Confirm -> Step 2<br>`wrong_person` -> Close |
| **Step 2 (Recall & Ask)** | "Recently member ne visit kiya tha... content kaisa laga?" | `feedback_positive` -> Step 4<br>`hesitant` -> Save & Close<br>`not_interested` -> Close |
| **Step 4 (Share USP AI)** | *Generates 2-3 USPs from KB*, then asks if they want senior call | `interested` -> SchedulerAgent<br>`hesitant` -> CloserAgent<br>`not_interested` -> CloserAgent |

### 🛑 Global Objections
- **Busy**: Scheduler
- **Not Interested**: Close
- **Source/Bot**: Re-listen
