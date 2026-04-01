"""
agents package — Multi-agent swarm for UniversalBooks.

ARCHITECTURE:
- Each call flow = 1 folder (new_teacher, digital_sample, etc.)
- Each folder has an agent.py with all steps as separate Agent classes
- Steps hand off to each other via function_tool returns
- Shared agents (closer, scheduler) in agents/shared/
- Scripts are editable constants at the top of each agent.py

FLOW DISPATCH:
  server.py sends call_type → main_agent.py → picks the right flow entry agent
"""

from agents.base_agent import BaseUBAgent

__all__ = ["BaseUBAgent"]
