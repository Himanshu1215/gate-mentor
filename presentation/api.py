from typing import List, Optional, Dict, Any
import logging
import os
import tempfile
import shutil

try:
    from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    logging.warning("FastAPI not installed. Run: pip install -r requirements.txt")

from learning.ai_reasoner import AIReasoningEngine

app = FastAPI(title="GATE DA Mentor API", version="1.0.0")

# Add CORS Middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

reasoner = AIReasoningEngine()

class ChatRequest(BaseModel):
    session_id: str
    query: str

class ChatResponse(BaseModel):
    reply: str
    citations: List[str]

class QuizSubmitRequest(BaseModel):
    session_id: str
    concept_id: str
    is_correct: bool
    confidence: int

class QuizSubmitResponse(BaseModel):
    success: bool
    new_mastery_level: int

class SessionStartRequest(BaseModel):
    goals: str

class SessionStartResponse(BaseModel):
    session_id: str

class CurriculumNextResponse(BaseModel):
    concept_id: str
    topic: str
    action: str

class MockGenerateResponse(BaseModel):
    exam_id: str
    duration_mins: int
    total_marks: float
    questions: List[Dict[str, Any]]

class CoachAlertResponse(BaseModel):
    alerts: List[Dict[str, str]]

class DashboardStatsResponse(BaseModel):
    mastered_concepts: int
    total_concepts: int
    readiness_percentage: float
    total_quizzes: int
    active_days_last_week: int
    projected_air: int
    risk_level: str

class UploadResponse(BaseModel):
    success: bool
    message: str
    chunks_ingested: int

@app.post("/api/session/start", response_model=SessionStartResponse)
async def session_start_endpoint(request: SessionStartRequest, authorization: Optional[str] = Header(None)):
    """Starts a new learning session."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    from learning.session_manager import SessionManager
    from core.event_bus import bus, Events
    import asyncio
    
    session_id = SessionManager.start_session(request.goals)
    asyncio.create_task(bus.publish(Events.SESSION_STARTED, {"session_id": session_id}))
    
    return SessionStartResponse(session_id=session_id)

@app.get("/api/curriculum/next", response_model=CurriculumNextResponse)
async def curriculum_next_endpoint(authorization: Optional[str] = Header(None)):
    """Gets the next optimal concept from the Curriculum Engine."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    from curriculum.dependency_graph import CurriculumEngine
    next_concept_id = CurriculumEngine.get_next_optimal_concept()
    
    if not next_concept_id:
        return CurriculumNextResponse(concept_id="ALL_DONE", topic="Syllabus Complete", action="REVIEW")
        
    # Get topic name safely (mocking fetch for brevity in response)
    return CurriculumNextResponse(concept_id=next_concept_id, topic="Next Topic via DAG", action="TEACH")

@app.get("/api/mocks/generate", response_model=MockGenerateResponse)
async def mock_generate_endpoint(authorization: Optional[str] = Header(None)):
    """Generates a full mock exam with GATE schema."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    from assessment.simulation_engine import SimulationEngine
    exam = SimulationEngine.generate_mock_exam(65)
    return MockGenerateResponse(**exam)

@app.get("/api/coach/alerts", response_model=CoachAlertResponse)
async def coach_alerts_endpoint(authorization: Optional[str] = Header(None)):
    """Runs background daemon checks and returns proactive alerts."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    from core.autonomous_coach import AutonomousCoach
    alerts = AutonomousCoach.run_health_check()
    return CoachAlertResponse(alerts=alerts)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """
    Main endpoint for interacting with the AI Teacher.
    In Milestone 1, this uses mock retrieval chunks.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # In a full implementation, the Retrieval Agent would fetch chunks here
    mock_chunks = [{"content": "Naive Bayes assumes all features are conditionally independent.", "metadata": {"source": "ISLR Ch 4"}}]
    
    reply = reasoner.generate_explanation(request.query, mock_chunks)
    
    return ChatResponse(
        reply=reply,
        citations=["ISLR Ch 4"]
    )

@app.post("/api/quiz/submit", response_model=QuizSubmitResponse)
async def quiz_submit_endpoint(request: QuizSubmitRequest, authorization: Optional[str] = Header(None)):
    """
    Endpoint for submitting quiz answers. Invokes the deterministic decision engine.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    from learning.decision_engine import MasteryCalculator
    new_level = MasteryCalculator.update_mastery(request.concept_id, request.is_correct, request.confidence)
    
    # Fire event via the Event Bus asynchronously in background
    from core.event_bus import bus, Events
    import asyncio
    asyncio.create_task(bus.publish(Events.QUIZ_COMPLETED, request.dict()))
    
    return QuizSubmitResponse(success=True, new_mastery_level=new_level)

@app.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
async def dashboard_stats_endpoint(authorization: Optional[str] = Header(None)):
    """Returns real-time dashboard analytics and goal projections."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from analytics.dashboard_metrics import DashboardAnalytics
    from planner.goal_engine import GoalEngine

    stats = DashboardAnalytics.get_dashboard_stats()
    projection = GoalEngine.get_current_projection()

    return DashboardStatsResponse(
        mastered_concepts=stats["mastered_concepts"],
        total_concepts=stats["total_concepts"],
        readiness_percentage=stats["readiness_percentage"],
        total_quizzes=stats["total_quizzes"],
        active_days_last_week=stats["active_days_last_week"],
        projected_air=projection["projected_air"],
        risk_level=projection["risk_level"]
    )

@app.post("/api/upload", response_model=UploadResponse)
async def upload_file_endpoint(
    file: UploadFile = File(...),
    concept_id: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    """
    Upload a document (PDF, Markdown, or Text) to be ingested into the knowledge base.
    The file is chunked, embedded, and stored in ChromaDB for RAG retrieval.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not concept_id:
        raise HTTPException(status_code=400, detail="concept_id is required")

    # Determine file type
    filename = file.filename or "unknown"
    is_pdf = filename.lower().endswith(".pdf")

    # Save uploaded file to a temporary location
    knowledge_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge", "personal", "notes")
    os.makedirs(knowledge_dir, exist_ok=True)
    dest_path = os.path.join(knowledge_dir, filename)

    try:
        with open(dest_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    chunks_count = 0
    try:
        if is_pdf:
            from knowledge.ingestion import KnowledgeIngestor as PDFIngestor
            ingestor = PDFIngestor()
            ingestor.ingest_document(dest_path, concept_id, filename)
            # Estimate chunks (exact count logged but not easily returned)
            chunks_count = -1  # Will be logged
        else:
            from knowledge.ingestor import KnowledgeIngestor
            ingestor = KnowledgeIngestor()
            ingestor.ingest_file(dest_path, concept_id)
            chunks_count = -1  # Will be logged

        return UploadResponse(
            success=True,
            message=f"Successfully ingested '{filename}' into the knowledge base for concept '{concept_id}'.",
            chunks_ingested=chunks_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
