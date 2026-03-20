import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

# Prices (adjust if needed, mimicking the Indian Rupee setup)
USD_TO_INR               = 92.0  # Approx
PRICE_TTS_PER_10K_CHARS  = 30.0  # INR
PRICE_STT_PER_MIN        = 0.50  # INR

# Claude Sonnet 4.5 via AWS Bedrock ($3.00 input, $15.00 output per 1M tokens)
PRICE_LLM_INPUT_PER_1M   = 3.00  # USD
PRICE_LLM_OUTPUT_PER_1M  = 15.00  # USD

# ─────────────────────────────────────────────────────────────────
# CALLER INFO
# ─────────────────────────────────────────────────────────────────

@dataclass
class PatientInfo:
    """Carries caller context across agent handoffs."""
    name:   Optional[str] = None
    phone:  Optional[str] = None
    reason: Optional[str] = None

    def is_complete(self) -> bool:
        return all([self.name, self.phone, self.reason])

    def __str__(self):
        return f"name='{self.name}' phone='{self.phone}' reason='{self.reason}'"


# ─────────────────────────────────────────────────────────────────
# COST TRACKER
# ─────────────────────────────────────────────────────────────────

@dataclass
class CostTracker:
    """
    Tracks all billable usage across the call.

    LLM BILLING NOTE:
    LLMs charge for the FULL context sent each turn
    (conversation history grows each turn — you pay for it every time).
    We track both:
      - llm_input_tokens_total : sum of full prompt_tokens (actual billing)
      - llm_input_tokens_delta : sum of new tokens only (informational)
    """

    call_id:    str   = ""
    call_start: float = field(default_factory=time.time)

    # TTS (Bulbul v3) — billed per character spoken
    tts_chars_total:    int   = 0
    tts_active_seconds: float = 0.0

    # STT (Saaras v3) — billed per minute of user speech
    stt_active_seconds: float = 0.0

    # LLM — billed per token
    llm_input_tokens_total:  int = 0   # cumulative (actual billing)
    llm_input_tokens_delta:  int = 0   # new tokens per turn (informational)
    llm_output_tokens_total: int = 0
    llm_calls:               int = 0
    _last_input_tokens:      int = 0   # used to compute delta

    # Function call timeline for brief log
    function_calls: list = field(default_factory=list)

    # ── LLM ────────────────────────────────────────────────────

    def log_llm(self, input_tokens: int, output_tokens: int):
        delta = (
            input_tokens - self._last_input_tokens
            if input_tokens > self._last_input_tokens
            else input_tokens
        )
        self.llm_input_tokens_total  += input_tokens
        self.llm_input_tokens_delta  += delta
        self.llm_output_tokens_total += output_tokens
        self.llm_calls               += 1
        self._last_input_tokens       = input_tokens

    # ── Function log ────────────────────────────────────────────

    def log_function(self, name: str, args: dict):
        self.function_calls.append({
            "time":     datetime.now().strftime("%H:%M:%S"),
            "function": name,
            "args":     args,
        })

    # ── Cost calculation ─────────────────────────────────────────

    def calculate_costs(self) -> dict:
        tts_cost = (self.tts_chars_total / 10_000) * PRICE_TTS_PER_10K_CHARS
        stt_cost = (self.stt_active_seconds / 60)  * PRICE_STT_PER_MIN
        llm_cost = (
            (self.llm_input_tokens_total  / 1_000_000) * PRICE_LLM_INPUT_PER_1M +
            (self.llm_output_tokens_total / 1_000_000) * PRICE_LLM_OUTPUT_PER_1M
        ) * USD_TO_INR
        
        # Telephony assumed roughly 0.45 per minute based on previous edits
        duration = time.time() - self.call_start
        telephony_cost = (duration / 60) * 0.45 
        
        total    = tts_cost + stt_cost + llm_cost + telephony_cost

        return {
            "duration_seconds":       round(duration, 1),
            "duration_minutes":       round(duration / 60, 2),
            "tts_chars":              self.tts_chars_total,
            "tts_seconds":            round(self.tts_active_seconds, 1),
            "tts_cost_inr":           round(tts_cost, 4),
            "stt_seconds":            round(self.stt_active_seconds, 1),
            "stt_cost_inr":           round(stt_cost, 4),
            "llm_calls":              self.llm_calls,
            "llm_input_tokens":       self.llm_input_tokens_total,
            "llm_input_tokens_delta": self.llm_input_tokens_delta,
            "llm_output_tokens":      self.llm_output_tokens_total,
            "llm_cost_inr":           round(llm_cost, 4),
            "total_cost_inr":         round(total, 4),
            "cost_per_min_inr":       round(total / max(duration / 60, 0.1), 4),
        }
