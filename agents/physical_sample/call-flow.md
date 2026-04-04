# 📦 Physical Sample Flow

**Persona**: UniversalBooks Agent  
**Context**: Following up with a teacher who we previously mailed a physical box of sample books to.

| Step | Interaction | Logic & Transitions |
|---|---|---|
| **Step 1a (Greet)** | Says **"Hello?"** silently waits | `caller_picked_up` -> Step 1b |
| **Step 1b (Confirm)** | "Hello kya meri baat Name sir se ho rahi hai?" | Confirm -> Step 2<br>`wrong_person` -> Close |
| **Step 2 (Recall/Ask)** | "Aapko physical book sample mile honge... kya aapne content check kiya?" | `parcel_not_received` -> Webhook digital resend -> Close<br>`parcel_received` -> Step 4 |
| **Step 4 (Feedback)** | "Aapko content or paper quality kaise laga?" | `details_positive` -> S5 Positive -> SchedulerAgent<br>`details_hesitant` -> S5 Hesitant -> CloserAgent |

### 🛑 Global Objections
- **Busy**: Scheduler
- **Not Interested**: Close
- **Source/Bot**: Re-listen
