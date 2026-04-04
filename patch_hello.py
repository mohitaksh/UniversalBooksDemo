import os
import re

for idx in range(1, 5):
    filepath = f"agents/new_teacher_script_{idx}/agent.py"
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # We want to replace Step1_Greet with a version that says "Hello?"
    
    new_step1_greet = """class Step1_Greet(BaseUBAgent):
    def __init__(self, **kwargs):
        super().__init__(
            instructions=(
                "You just said 'Hello?'. Listen carefully for the person to speak.\\n"
                "When the person replies (hello, haan, ji, boliye, ha, etc.), "
                "call `caller_picked_up` IMMEDIATELY.\\n"
                "Do NOT generate any speech. ONLY call the tool."
            ),
            **kwargs,
        )

    async def on_enter(self) -> None:
        await self.say_script("Hello?")

    @function_tool
    async def caller_picked_up(self, context: RunCtx, response: str = "hello") -> "Step1b_ConfirmIdentity":
        return Step1b_ConfirmIdentity()"""

    # We'll use regex to replace the entire Step1_Greet class definition.
    # It starts at `class Step1_Greet(BaseUBAgent):` and ends before `class Step1b_ConfirmIdentity` or `# ══`
    
    pattern = re.compile(r'class Step1_Greet\(BaseUBAgent\):.*?@function_tool\s+async def caller_picked_up.*?return Step1b_ConfirmIdentity\(\)', re.DOTALL)
    
    content = pattern.sub(new_step1_greet, content)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {filepath}")

print("Done")
