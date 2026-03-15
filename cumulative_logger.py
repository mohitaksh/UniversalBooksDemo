"""
cumulative_logger.py
────────────────────
Scans all logs/*/costs.json files every 5 minutes and writes:
  logs/summary.json  → Aggregated totals across all calls
  logs/summary.txt   → Human-readable summary report

Run alongside your agent:
    python cumulative_logger.py
"""

import json
import os
import time
from datetime import datetime
from glob import glob

LOGS_DIR = "logs"
SUMMARY_JSON = os.path.join(LOGS_DIR, "summary.json")
SUMMARY_TXT  = os.path.join(LOGS_DIR, "summary.txt")
INTERVAL_SEC = 300  # 5 minutes


def aggregate_all_calls() -> dict:
    """Scan every logs/<call_id>/costs.json and sum up everything."""
    pattern = os.path.join(LOGS_DIR, "*", "costs.json")
    files = sorted(glob(pattern))

    total_calls        = 0
    total_minutes      = 0.0
    total_tts_chars    = 0
    total_tts_secs     = 0.0
    total_stt_secs     = 0.0
    total_llm_in       = 0
    total_llm_out      = 0
    total_llm_calls    = 0
    total_tts_cost     = 0.0
    total_stt_cost     = 0.0
    total_llm_cost     = 0.0
    total_cost         = 0.0

    call_records = []

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                c = json.load(f)
        except Exception:
            continue  # skip corrupted files

        total_calls        += 1
        total_minutes      += c.get("duration_minutes", 0)
        total_tts_chars    += c.get("tts_chars", 0)
        total_tts_secs     += c.get("tts_seconds", 0)
        total_stt_secs     += c.get("stt_seconds", 0)
        total_llm_in       += c.get("llm_input_tokens", 0)
        total_llm_out      += c.get("llm_output_tokens", 0)
        total_llm_calls    += c.get("llm_calls", 0)
        total_tts_cost     += c.get("tts_cost_inr", 0)
        total_stt_cost     += c.get("stt_cost_inr", 0)
        total_llm_cost     += c.get("llm_cost_inr", 0)
        total_cost         += c.get("total_cost_inr", 0)

        call_records.append({
            "call_id":   c.get("call_id", os.path.basename(os.path.dirname(fpath))),
            "minutes":   c.get("duration_minutes", 0),
            "cost_inr":  c.get("total_cost_inr", 0),
            "rs_per_min": c.get("cost_per_min_inr", 0),
        })

    telephony_cost = total_minutes * 0.45
    avg_cost_per_min = (total_cost / total_minutes) if total_minutes > 0 else 0.0

    return {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_calls":       total_calls,
        "total_minutes":     round(total_minutes, 2),
        "total_tts_chars":   total_tts_chars,
        "total_tts_seconds": round(total_tts_secs, 1),
        "total_stt_seconds": round(total_stt_secs, 1),
        "total_llm_calls":   total_llm_calls,
        "total_llm_input_tokens":  total_llm_in,
        "total_llm_output_tokens": total_llm_out,
        "cost_breakdown_inr": {
            "tts":       round(total_tts_cost, 4),
            "stt":       round(total_stt_cost, 4),
            "llm":       round(total_llm_cost, 4),
            "telephony": round(telephony_cost, 4),
            "total":     round(total_cost, 4),
        },
        "avg_cost_per_min_inr": round(avg_cost_per_min, 4),
        "calls": call_records,
    }


def write_summary(data: dict) -> None:
    # JSON
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Human-readable TXT
    cb = data["cost_breakdown_inr"]
    report = f"""
╔══════════════════════════════════════════════════════╗
║           CUMULATIVE COST SUMMARY REPORT             ║
║  Generated : {data['generated_at']:<38}║
╠══════════════════════════════════════════════════════╣
║  CALLS                                               ║
║    Total calls     : {data['total_calls']:>6}                      ║
║    Total minutes   : {data['total_minutes']:>9.2f}                   ║
╠══════════════════════════════════════════════════════╣
║  USAGE                                               ║
║    TTS Characters  : {data['total_tts_chars']:>10,}                  ║
║    TTS Seconds     : {data['total_tts_seconds']:>9.1f}                   ║
║    STT Seconds     : {data['total_stt_seconds']:>9.1f}                   ║
║    LLM Calls       : {data['total_llm_calls']:>6}                      ║
║    LLM Input Tok   : {data['total_llm_input_tokens']:>10,}                  ║
║    LLM Output Tok  : {data['total_llm_output_tokens']:>10,}                  ║
╠══════════════════════════════════════════════════════╣
║  COST BREAKDOWN (INR)                                ║
║    TTS (Bulbul)    : ₹{cb['tts']:>9.4f}                   ║
║    STT (Saaras)    : ₹{cb['stt']:>9.4f}                   ║
║    LLM (Groq)      : ₹{cb['llm']:>9.4f}                   ║
║    Telephony       : ₹{cb['telephony']:>9.4f}                   ║
╠══════════════════════════════════════════════════════╣
║  TOTAL                                               ║
║    Total cost      : ₹{cb['total']:>9.4f}                   ║
║    Avg ₹ / minute  : ₹{data['avg_cost_per_min_inr']:>9.4f}                   ║
╚══════════════════════════════════════════════════════╝

Per-call breakdown:
"""
    for rec in data["calls"]:
        report += (
            f"  {rec['call_id']:<25} | "
            f"{rec['minutes']:.2f} min | "
            f"₹{rec['cost_inr']:.4f} | "
            f"₹{rec['rs_per_min']:.4f}/min\n"
        )

    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Summary updated → {data['total_calls']} calls | "
          f"₹{cb['total']:.4f} total | ₹{data['avg_cost_per_min_inr']:.4f}/min avg")


def main():
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"Cumulative logger started. Updating summary every {INTERVAL_SEC // 60} minutes.")
    print(f"Output: {SUMMARY_JSON} and {SUMMARY_TXT}\n")

    while True:
        data = aggregate_all_calls()
        if data["total_calls"] > 0:
            write_summary(data)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No completed calls found yet.")

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
