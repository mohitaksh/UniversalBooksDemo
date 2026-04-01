import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

load_dotenv(dotenv_path=".env.local")

# Prefer PostgreSQL/MySQL DB URL if provided, fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///logs.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CallRecord(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, unique=True, index=True)
    caller_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    call_type = Column(String, nullable=True)
    agent_name = Column(String, nullable=True)
    
    # Costs & Metrics
    duration_seconds = Column(Float, default=0.0)
    tts_cost_inr = Column(Float, default=0.0)
    stt_cost_inr = Column(Float, default=0.0)
    llm_cost_inr = Column(Float, default=0.0)
    total_cost_inr = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    transcripts = relationship("TranscriptLine", back_populates="call_record", cascade="all, delete-orphan")

class TranscriptLine(Base):
    __tablename__ = "transcripts"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, ForeignKey("calls.call_id"))
    role = Column(String) # 'User' or 'Agent'
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    call_record = relationship("CallRecord", back_populates="transcripts")

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
