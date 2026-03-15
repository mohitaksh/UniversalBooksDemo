import json
import logging
import os
from typing import Tuple
from models import CostTracker

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_loggers(call_id: str) -> Tuple[
    logging.Logger,
    logging.Logger,
    logging.Logger,
    logging.Logger,
    logging.Logger, # LLM Transcript log
    logging.Logger, # Human-readable Transcript log
]:
    """Returns (full_log, brief_log, token_log, cost_log, llm_log, transcript_log)."""

    def make_logger(name: str, filename: str, console: bool = False) -> logging.Logger:
        logger = logging.getLogger(f"{call_id}_{name}")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # prevent duplicate handlers on reload

        fmt = logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S")
        
        target_dir = os.path.join(LOG_DIR, call_id)
        os.makedirs(target_dir, exist_ok=True)

        fh = logging.FileHandler(os.path.join(target_dir, filename), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        if console:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(fmt)
            logger.addHandler(ch)

        return logger

    full_log  = make_logger("full",   f"call_{call_id}.log",        console=True)
    brief_log = make_logger("brief",  f"call_{call_id}_brief.log")
    token_log = make_logger("tokens", f"call_{call_id}_tokens.log")
    cost_log  = make_logger("costs",  f"call_{call_id}_costs.log")
    llm_log   = make_logger("llm",    f"call_{call_id}_llm_transcript.log")
    
    # Custom format for transcript: just message
    transcript_log = logging.getLogger(f"{call_id}_transcript")
    transcript_log.setLevel(logging.INFO)
    transcript_log.handlers = []
    target_dir = os.path.join(LOG_DIR, call_id)
    tfh = logging.FileHandler(os.path.join(target_dir, f"call_{call_id}_transcript.txt"), encoding="utf-8")
    tfh.setFormatter(logging.Formatter("%(message)s"))
    transcript_log.addHandler(tfh)

    return full_log, brief_log, token_log, cost_log, llm_log, transcript_log

def write_cost_report(tracker: CostTracker, full_log: logging.Logger, cost_log: logging.Logger, brief_log: logging.Logger) -> None:
    """Formats and writes the final cost report to cost + full logs."""
    c = tracker.calculate_costs()

    report = f"""
╔══════════════════════════════════════════════════════╗
║                CALL COST REPORT                      ║
║  Call ID : {tracker.call_id:<42}║
╠══════════════════════════════════════════════════════╣
║  DURATION                                            ║
║    Total time    : {c['duration_seconds']:>7.1f} seconds                 ║
║    Total time    : {c['duration_minutes']:>7.2f} minutes                 ║
╠══════════════════════════════════════════════════════╣
║  TTS — Bulbul v3 (₹30 per 10,000 chars)             ║
║    Characters    : {c['tts_chars']:>10,}                   ║
║    Active time   : {c['tts_seconds']:>7.1f} seconds                 ║
║    Cost          : ₹{c['tts_cost_inr']:>9.4f}                   ║
╠══════════════════════════════════════════════════════╣
║  STT — Saaras v3 (₹0.50 per minute)                 ║
║    Active time   : {c['stt_seconds']:>7.1f} seconds                 ║
║    Cost          : ₹{c['stt_cost_inr']:>9.4f}                   ║
╠══════════════════════════════════════════════════════╣
║  LLM — Groq API (Approx)                             ║
║    API calls         : {c['llm_calls']:>7}                   ║
║    Input tokens      : {c['llm_input_tokens']:>7,}  cumulative        ║
║    Output tokens     : {c['llm_output_tokens']:>7,}                   ║
║    Cost              : ₹{c['llm_cost_inr']:>6.4f}  (billed)       ║
╠══════════════════════════════════════════════════════╣
║  TOTAL                                               ║
║    Total cost    : ₹{c['total_cost_inr']:>9.4f}                   ║
║    Per minute    : ₹{c['cost_per_min_inr']:>9.4f}                   ║
╚══════════════════════════════════════════════════════╝"""

    cost_log.info(report)
    full_log.info(report)

    brief_log.info("\n── FUNCTION CALL TIMELINE ──")
    for fc in tracker.function_calls:
        brief_log.info(f"  {fc['time']} | {fc['function']} | {fc['args']}")
    brief_log.info(
        f"CALL_END | cost=₹{c['total_cost_inr']:.4f} | "
        f"duration={c['duration_seconds']:.1f}s"
    )

    # Write machine-readable costs.json for the cumulative aggregator
    log_dir = os.path.join("logs", tracker.call_id)
    json_path = os.path.join(log_dir, "costs.json")
    payload = {"call_id": tracker.call_id, **c}
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        full_log.error(f"Failed to write costs.json: {e}")
