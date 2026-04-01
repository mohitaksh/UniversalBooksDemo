import json
import logging
import asyncio
import time
import os
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli, llm, AutoSubscribe, JobRequest
from livekit.plugins import sarvam, groq, silero, openai
from db import SessionLocal, CallRecord, TranscriptLine
from models import CostTracker

try:
    from models import get_random_voice
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models import get_random_voice

logger = logging.getLogger("agents.dispatch")

def get_dispatcher_worker() -> WorkerOptions:
    
    async def preflight(req: JobRequest) -> None:
        await req.accept()

    async def entrypoint(ctx: JobContext):
        start_time = time.time()
        logger.info(f"Connecting to room {ctx.room.name}...")
        
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

        metadata = {}
        if ctx.job.metadata:
            try:
                metadata = json.loads(ctx.job.metadata)
            except Exception as e:
                logger.error(f"Failed to parse job metadata: {e}")
                
        call_type = metadata.get("call_type", "NEW_TEACHER")
        caller_name = metadata.get("name", "ji")
        phone = metadata.get("phone", "Unknown")
        call_id = f"{phone}_{int(start_time)}"

        logger.info(f"Inbound Job: call_type={call_type}, name={caller_name}, phone={phone}")

        # Voice Profile
        voice = get_random_voice()
        logger.info(f"🎤 SELECTED VOICE | {voice.name} ({voice.tts_speaker})")

        # Database Init
        db = SessionLocal()
        call_record = CallRecord(
            call_id=call_id,
            caller_name=caller_name,
            phone_number=phone,
            call_type=call_type,
            agent_name=voice.name
        )
        db.add(call_record)
        db.commit()

        # Tracker
        tracker = CostTracker(call_id=call_id)

        # Plugins
        llm_plugin = groq.LLM(
            api_key=os.getenv("GROQ_API_KEY"),
            model="llama-3.3-70b-versatile",
            temperature=0.3,
        )
        stt_plugin = openai.STT(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            model="whisper-large-v3",
        )
        tts_plugin = sarvam.TTS(
            target_language_code="hi-IN",
            model="bulbul:v3",
            speaker=voice.tts_speaker,
            speech_sample_rate=8000,
        )
        vad_plugin = silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.6,
        )

        # TTS Tracking Injection
        orig_tts_synthesize = tts_plugin.synthesize
        def tts_interceptor(text: str, **kwargs):
            tracker.add_tts_chars(len(text))
            return orig_tts_synthesize(text, **kwargs)
        tts_plugin.synthesize = tts_interceptor

        orig_tts_stream = tts_plugin.stream
        def tts_stream_interceptor(**kwargs):
            stream = orig_tts_stream(**kwargs)
            orig_push_text = stream.push_text
            def push_text_interceptor(text: str | None):
                if text: tracker.add_tts_chars(len(text))
                orig_push_text(text)
            stream.push_text = push_text_interceptor
            return stream
        tts_plugin.stream = tts_stream_interceptor

        # Route to the correct Initial Agent
        initial_agent = None
        if call_type in ["NEW_TEACHER", "NEW_TEACHER_COACHING", "NEW_TEACHER_SCHOOL"]:
            from agents.intake.new_teacher import NewTeacherAgent
            initial_agent = NewTeacherAgent(caller_name=caller_name, voice_profile=voice)
        else:
            from agents.intake.new_teacher import NewTeacherAgent
            initial_agent = NewTeacherAgent(caller_name=caller_name, voice_profile=voice)

        session = llm.AgentSession(
            agent=initial_agent,
            llm=llm_plugin,
            tts=tts_plugin,
            stt=stt_plugin,
            vad=vad_plugin,
            room=ctx.room,
        )

        # Transcripts to DB
        @session.on("chat_message")
        def on_chat_message(msg: llm.ChatMessage):
            if msg.role in ["user", "assistant"]:
                text = msg.text_content
                if text:
                    t_line = TranscriptLine(call_id=call_id, role=msg.role, text=text)
                    db.add(t_line)
                    db.commit()

        # Metrics Tracking
        @session.on("metrics_collected")
        def on_metrics(mtrcs: llm.LLMMetrics):
            tracker.add_llm_metrics(mtrcs.usage.input_tokens, mtrcs.usage.output_tokens)

        # Background Audio (Ambience + Typing)
        bg_audio = rtc.BackgroundAudioPlayer(
            room=ctx.room, clip=rtc.BuiltinAudioClip.OFFICE_AMBIENCE, loop=True
        )
        await bg_audio.play(gain=3.0)

        typing_audio = rtc.BackgroundAudioPlayer(
            room=ctx.room, clip=rtc.BuiltinAudioClip.KEYBOARD_TYPING, loop=True
        )
        
        @session.on("agent_started_thinking")
        def agent_started_thinking():
            asyncio.create_task(typing_audio.play(gain=0.8))

        @session.on("agent_stopped_thinking")
        def agent_stopped_thinking():
            asyncio.create_task(typing_audio.pause())

        # Shutdown + DB Save
        async def on_call_ended():
            tracker.end_call()
            c = tracker.calculate_costs()
            
            call_record.duration_seconds = c['duration_seconds']
            call_record.tts_cost_inr = c['tts_cost_inr']
            call_record.stt_cost_inr = c['stt_cost_inr']
            call_record.llm_cost_inr = c['llm_cost_inr']
            call_record.total_cost_inr = c['total_cost_inr']
            db.commit()
            db.close()
            
            await session.aclose()
            if ctx.room:
                await ctx.room.disconnect()
            
        ctx.room.on("disconnected", lambda reason: asyncio.create_task(on_call_ended()))
        ctx.room.on("participant_disconnected", lambda p: asyncio.create_task(on_call_ended()))

        session.start()

    return WorkerOptions(entrypoint_fnc=entrypoint, preflight_fnc=preflight)
