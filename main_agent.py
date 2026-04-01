import logging
from livekit.agents import cli
from agents.dispatch import get_dispatcher_worker
import asyncio
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

logger = logging.getLogger("main_agent")

if __name__ == "__main__":
    cli.run_app(get_dispatcher_worker())
