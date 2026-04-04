import os
import re

for idx in range(1, 5):
    filepath = f"agents/new_teacher_script_{idx}/agent.py"
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Create the ListenClasses code
    listen_classes_code = """
class Step2_ListenClasses(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                 "You are waiting for the teacher to answer what classes they teach.\\n"
                 "ROUTING RULES (follow strictly):\\n"
                 "1. If they mention SPECIFIC classes/exams (e.g. 'NEET', '9th to 12th', 'JEE'), call classes_shared.\\n"
                 "2. If their answer is VAGUE or UNCLEAR, call unclear_response.\\n"
                 "3. If they say they are busy, call person_busy.\\n"
                 "4. If they say they are NOT interested (nahi chahiye, interest nahi, no), call not_interested.\\n"
                 "5. If they ask 'where did you get my number', call handle_objection.\\n"
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        pass  # NO SPEECH

    @function_tool
    async def classes_shared(self, context: RunCtx, classes_and_exams: str) -> "Step3_ShareSample":
        ud = context.userdata
        if classes_and_exams.strip().lower() in {"ji", "jee", "haan", "ha", "ok", "theek hai"} or len(classes_and_exams.strip()) <= 3:
            await self.say_script("जी सर, मतलब आपके यहाँ कौन सी classes चलती हैं?")
            return Step2_ListenClasses()
        ud.exam_type = classes_and_exams
        if ud.tracker: ud.tracker.log_function("set_exam_type", {"exam": classes_and_exams})
        return Step3_ShareSample()

    @function_tool
    async def unclear_response(self, context: RunCtx, what_they_said: str = "unclear") -> "Step2_ListenClasses":
        await self.say_script("जी सर, मतलब specifically कौन सी classes चलती हैं आपके यहाँ?")
        return Step2_ListenClasses()

    @function_tool
    async def person_busy(self, context: RunCtx, response: str = "busy") -> BaseUBAgent:
        await self.say_script(S_BUSY)
        return SchedulerAgent()

    @function_tool
    async def not_interested(self, context: RunCtx, response: str = "no") -> BaseUBAgent:
        await self.say_script(S_NOT_INTERESTED)
        return CloserAgent(tag="Not Interested")

    @function_tool
    async def handle_objection(self, context: RunCtx, objection: str = "unknown") -> BaseUBAgent:
        await self.say_script(S_NUMBER_SOURCE if "number" in objection.lower() or "kahan" in objection.lower() else S_AI_RESPONSE)
        return ObjectionAgent(return_agent=Step2_ListenClasses())
"""

    if "Step2_ListenClasses" not in content:
        # Change `return Step2_Intro()` inside `Step2_Intro.unclear_response`, `classes_shared` fallback, etc
        # Actually just find and replace in Step2_Intro
        content = re.sub(
            r'return Step2_Intro\(\)', 
            r'return Step2_ListenClasses()', 
            content
        )
        content = re.sub(
            r'return_agent=Step2_Intro\(\)', 
            r'return_agent=Step2_ListenClasses()', 
            content
        )
        # Inject the new class right before Step3_ShareSample
        content = content.replace("class Step3_ShareSample", listen_classes_code + "\nclass Step3_ShareSample")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")

print("Done")
