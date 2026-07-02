from typing import List, Optional, Dict, Any
import logging
import os
import tempfile
import shutil

try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from pydantic import BaseModel
except ImportError:
    logging.warning("FastAPI not installed. Run: pip install -r requirements.txt")

from learning.ai_reasoner import AIReasoningEngine

@asynccontextmanager
async def lifespan(app: FastAPI):
    from infrastructure.database import init_db
    init_db()
    _ensure_learning_tables()
    from learning.concept_drift import ConceptDriftEngine
    ConceptDriftEngine.apply_drift_if_needed()
    yield

app = FastAPI(title="GATE DA Mentor API", version="1.0.0", lifespan=lifespan)

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
    persona: Optional[str] = "Professor"

class ChatResponse(BaseModel):
    reply: str
    citations: List[str]

class QuizSubmitRequest(BaseModel):
    session_id: str
    concept_id: str
    is_correct: bool
    confidence: int
    question_id: Optional[str] = None
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    time_taken_sec: Optional[float] = None
    source: Optional[str] = "quiz"

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

class ConceptNoteRequest(BaseModel):
    content: str = ""

class RevisionScheduleRequest(BaseModel):
    concept_id: str
    due_in_days: int = 1
    question_id: Optional[str] = None

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
    from infrastructure.database import get_db_connection

    next_concept_id = CurriculumEngine.get_next_optimal_concept()

    if not next_concept_id:
        return CurriculumNextResponse(concept_id="ALL_DONE", topic="Syllabus Complete", action="REVIEW")

    # Fetch actual topic name from SQLite
    topic_name = next_concept_id  # fallback
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT topic FROM concepts WHERE concept_id = ?",
            (next_concept_id,)
        ).fetchone()
        conn.close()
        if row:
            topic_name = row["topic"]
    except Exception as e:
        logging.warning(f"Could not fetch topic name: {e}")

    return CurriculumNextResponse(concept_id=next_concept_id, topic=topic_name, action="TEACH")

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
    AI Tutor chat endpoint driven by the LangGraph agent.
    Routes queries through a structured state graph using local LLM, ChromaDB, and PYQ repository.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from learning.langgraph_agent import agent

    state_input = {
        "query": request.query,
        "session_id": request.session_id,
        "persona": request.persona or "Professor",
        "messages": [],
        "context": [],
        "reply": "",
        "citations": [],
        "next_node": ""
    }

    try:
        result = agent.invoke(state_input)
        reply = result.get("reply", "No response generated.")
        citations = result.get("citations", [])
    except Exception as e:
        logging.error(f"Error executing LangGraph agent: {e}")
        # Standard fallback logic in case of graph failure
        from knowledge.ingestor import KnowledgeIngestor
        retriever = KnowledgeIngestor()
        context_chunks = retriever.query(request.query, top_k=5)
        if not context_chunks:
            context_chunks = [{
                "content": "Knowledge base is empty. Please ingest GATE content first.",
                "metadata": {"source": "System"}
            }]
        reply = reasoner.generate_explanation(request.query, context_chunks, persona=request.persona or "Professor")
        citations = list({chunk["metadata"].get("source", "Unknown") for chunk in context_chunks})

    return ChatResponse(reply=reply, citations=citations)

@app.post("/api/quiz/submit", response_model=QuizSubmitResponse)
async def quiz_submit_endpoint(request: QuizSubmitRequest, authorization: Optional[str] = Header(None)):
    """
    Endpoint for submitting quiz answers. Invokes the deterministic decision engine.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Record the attempt so analytics / gamification / calibration have data.
    import uuid
    from infrastructure.database import get_db_connection
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO quiz_attempts (attempt_id, session_id, concept_id, is_correct, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, request.session_id, request.concept_id,
             1 if request.is_correct else 0, request.confidence),
        )
        if request.question_id:
            conn.execute("""
                INSERT INTO attempt_items
                (session_id, source, question_id, concept_id, user_answer, correct_answer, is_correct, confidence, time_taken_sec)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.session_id,
                request.source,
                request.question_id,
                request.concept_id,
                request.user_answer,
                request.correct_answer,
                1 if request.is_correct else 0,
                request.confidence,
                request.time_taken_sec
            ))
            if not request.is_correct:
                conn.execute("""
                    INSERT INTO revision_queue_items (question_id, concept_id, interval_days, due_at, lapses)
                    VALUES (?, ?, 1, datetime('now', '+1 day'), 1)
                    ON CONFLICT(question_id) DO UPDATE SET
                        interval_days = 1, due_at = datetime('now', '+1 day'), lapses = lapses + 1
                """, (request.question_id, request.concept_id))
            else:
                row = conn.execute("SELECT interval_days FROM revision_queue_items WHERE question_id = ?", (request.question_id,)).fetchone()
                if row:
                    curr_interval = row["interval_days"]
                    next_interval = {1: 3, 3: 7, 7: 14}.get(curr_interval, 14)
                    if curr_interval >= 14:
                        conn.execute("DELETE FROM revision_queue_items WHERE question_id = ?", (request.question_id,))
                    else:
                        conn.execute("UPDATE revision_queue_items SET interval_days = ?, due_at = datetime('now', '+' || ? || ' days') WHERE question_id = ?", (next_interval, next_interval, request.question_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"Could not record quiz attempt: {e}")

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
    import uuid
    from infrastructure.database import get_db_connection

    _ensure_learning_tables()
    conn = get_db_connection()
    concept_exists = conn.execute("SELECT 1 FROM concepts WHERE concept_id = ?", (concept_id,)).fetchone()
    conn.close()
    if not concept_exists:
        raise HTTPException(status_code=404, detail="Concept not found")

    filename = file.filename or "unknown"
    is_pdf = filename.lower().endswith(".pdf")
    file_type = os.path.splitext(filename)[1].lower().lstrip(".") or "file"

    MAX_FILE_SIZE = 10 * 1024 * 1024
    if hasattr(file, "size") and file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Payload Too Large")

    # Save uploaded file to a temporary location
    knowledge_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge", "personal", "notes")
    os.makedirs(knowledge_dir, exist_ok=True)
    safe_name = f"{concept_id}_{uuid.uuid4().hex}_{os.path.basename(filename)}"
    dest_path = os.path.join(knowledge_dir, safe_name)

    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Payload Too Large")
        with open(dest_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
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

        try:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO concept_files
                (file_id, concept_id, filename, stored_path, file_type)
                VALUES (?, ?, ?, ?, ?)
            """, (uuid.uuid4().hex, concept_id, filename, os.path.abspath(dest_path), file_type))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.warning(f"Could not record uploaded file metadata: {e}")

        return UploadResponse(
            success=True,
            message=f"Successfully ingested '{filename}' into the knowledge base for concept '{concept_id}'.",
            chunks_ingested=chunks_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

# ════════════════════════════════════════════════════════════════════════════
#  Real-data endpoints (concepts, PYQ bank, quiz bank, mocks, revision,
#  gamification, profile, analytics) — added for the gamified frontend rebuild.
# ════════════════════════════════════════════════════════════════════════════

def _auth(authorization):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _ensure_learning_tables():
    from infrastructure.database import get_db_connection
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_notes (
            concept_id TEXT PRIMARY KEY,
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_files (
            file_id TEXT PRIMARY KEY,
            concept_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            file_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS manual_revision_items (
            concept_id TEXT PRIMARY KEY,
            due_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS attempt_items (
      item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id   TEXT,
      source       TEXT NOT NULL CHECK(source IN ('quiz','mock','pyq')),
      exam_id      TEXT,
      question_id  TEXT NOT NULL,
      concept_id   TEXT,
      user_answer  TEXT,
      correct_answer TEXT,
      is_correct   INTEGER NOT NULL,
      confidence   INTEGER,
      time_taken_sec REAL,
      marks_awarded REAL,
      timestamp    TEXT DEFAULT (datetime('now'))
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attempt_items_wrong ON attempt_items(is_correct, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attempt_items_exam ON attempt_items(exam_id)")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mock_attempts (
      exam_id     TEXT PRIMARY KEY,
      taken_at    TEXT DEFAULT (datetime('now')),
      score REAL, max_score REAL,
      correct INTEGER, incorrect INTEGER, unattempted INTEGER,
      subject_breakdown TEXT
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS revision_queue_items (
      question_id  TEXT PRIMARY KEY,
      concept_id   TEXT,
      interval_days INTEGER DEFAULT 1,
      due_at       TEXT NOT NULL,
      lapses       INTEGER DEFAULT 1,
      created_at   TEXT DEFAULT (datetime('now'))
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('user','assistant')),
      content TEXT NOT NULL,
      timestamp TEXT DEFAULT (datetime('now'))
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id)")
    conn.commit()
    conn.close()


def _parse_prereqs(value):
    import json as _json
    try:
        return _json.loads(value) if value else []
    except Exception:
        return []


def _progress_for_level(level):
    return round(max(0, min(8, level or 1)) / 8 * 100, 1)


def _status_for_level(level):
    if level >= 8:
        return "Mastered"
    if level >= 5:
        return "Strong"
    if level >= 2:
        return "Learning"
    return "Not started"


def _concepts_payload():
    from infrastructure.database import get_db_connection

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT c.concept_id, c.subject, c.topic, c.subtopic, c.prerequisites,
               c.difficulty, c.importance_weight, c.est_learning_time_mins,
               c.est_revision_time_mins,
               COALESCE(m.state_level, 1) AS state_level,
               COALESCE(m.accuracy, 0.0) AS accuracy
        FROM concepts c
        LEFT JOIN mastery_states m ON c.concept_id = m.concept_id
        ORDER BY c.subject, c.concept_id
    """).fetchall()
    conn.close()

    prereqs_by_id = {r["concept_id"]: _parse_prereqs(r["prerequisites"]) for r in rows}
    mastery = {r["concept_id"]: r["state_level"] for r in rows}
    dependents_by_id = {r["concept_id"]: [] for r in rows}
    for cid, prereqs in prereqs_by_id.items():
        for prereq in prereqs:
            if prereq in dependents_by_id:
                dependents_by_id[prereq].append(cid)

    subjects = {}
    concepts_by_id = {}
    for r in rows:
        cid = r["concept_id"]
        prereqs = prereqs_by_id[cid]
        blockers = [p for p in prereqs if mastery.get(p, 1) <= 2]
        level = r["state_level"] or 1
        item = {
            "concept_id": cid,
            "subject": r["subject"],
            "topic": r["topic"],
            "subtopic": r["subtopic"],
            "difficulty": r["difficulty"] or 5,
            "importance_weight": r["importance_weight"] or 1.0,
            "est_learning_time_mins": r["est_learning_time_mins"] or 30,
            "est_revision_time_mins": r["est_revision_time_mins"] or 10,
            "prerequisites": prereqs,
            "dependents": dependents_by_id.get(cid, []),
            "mastery_level": level,
            "accuracy": round(r["accuracy"] or 0.0, 2),
            "progress_percent": _progress_for_level(level),
            "status": _status_for_level(level),
            "locked": len(blockers) > 0,
            "blocked_by": blockers,
        }
        concepts_by_id[cid] = item
        subjects.setdefault(r["subject"], []).append(item)

    grouped = []
    all_concepts = []
    for subject, concepts in subjects.items():
        all_concepts.extend(concepts)
        mastered = sum(1 for c in concepts if c["mastery_level"] >= 8)
        avg = sum(c["mastery_level"] for c in concepts) / len(concepts) if concepts else 1
        grouped.append({
            "subject": subject,
            "concepts": concepts,
            "total": len(concepts),
            "mastered": mastered,
            "readiness": round(avg / 8 * 100, 1),
            "progress_percent": round(avg / 8 * 100, 1),
        })

    total = len(all_concepts)
    mastered = sum(1 for c in all_concepts if c["mastery_level"] >= 8)
    avg = sum(c["mastery_level"] for c in all_concepts) / total if total else 1
    return {
        "overall": {
            "total": total,
            "mastered": mastered,
            "average_mastery": round(avg, 2),
            "progress_percent": round(avg / 8 * 100, 1),
        },
        "subjects": grouped,
        "concepts_by_id": concepts_by_id,
    }


# prefix -> subject (mirrors knowledge/pyq_repository + seed_syllabus)
_PREFIX_SUBJECT = {
    "PROB": "Probability and Statistics", "LA": "Linear Algebra",
    "CALC": "Calculus and Optimization", "DSA": "Programming, DS & Algorithms",
    "DB": "Database Management and Warehousing", "ML": "Machine Learning",
    "AI": "Artificial Intelligence",
}


@app.get("/api/concepts")
async def list_concepts(authorization: Optional[str] = Header(None)):
    """All concepts grouped by subject, with mastery level + locked status."""
    _auth(authorization)
    _ensure_learning_tables()
    payload = _concepts_payload()
    return {"overall": payload["overall"], "subjects": payload["subjects"]}


@app.get("/api/concepts/{concept_id}")
async def get_concept_detail(concept_id: str, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    _ensure_learning_tables()
    from infrastructure.database import get_db_connection

    payload = _concepts_payload()
    concept = payload["concepts_by_id"].get(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    conn = get_db_connection()
    note = conn.execute(
        "SELECT content, updated_at FROM concept_notes WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    files = [dict(r) for r in conn.execute("""
        SELECT file_id, filename, file_type, uploaded_at
        FROM concept_files WHERE concept_id = ?
        ORDER BY uploaded_at DESC
    """, (concept_id,)).fetchall()]
    manual = conn.execute(
        "SELECT due_at FROM manual_revision_items WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    conn.close()

    return {
        "concept": concept,
        "prerequisites": [payload["concepts_by_id"][cid] for cid in concept["prerequisites"] if cid in payload["concepts_by_id"]],
        "dependents": [payload["concepts_by_id"][cid] for cid in concept["dependents"] if cid in payload["concepts_by_id"]],
        "subject_progress": next((s for s in payload["subjects"] if s["subject"] == concept["subject"]), None),
        "revision_status": {"manual_due_at": manual["due_at"] if manual else None},
        "notes": {
            "self_note": note["content"] if note else "",
            "updated_at": note["updated_at"] if note else None,
            "uploaded_files": files,
        },
    }


@app.get("/api/concepts/{concept_id}/notes")
async def get_concept_notes(concept_id: str, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    _ensure_learning_tables()
    from infrastructure.database import get_db_connection

    conn = get_db_connection()
    concept = conn.execute("SELECT 1 FROM concepts WHERE concept_id = ?", (concept_id,)).fetchone()
    if not concept:
        conn.close()
        raise HTTPException(status_code=404, detail="Concept not found")
    note = conn.execute(
        "SELECT content, updated_at FROM concept_notes WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    conn.close()
    return {
        "concept_id": concept_id,
        "content": note["content"] if note else "",
        "updated_at": note["updated_at"] if note else None,
    }


@app.put("/api/concepts/{concept_id}/notes")
async def put_concept_notes(concept_id: str, request: ConceptNoteRequest, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    _ensure_learning_tables()
    from infrastructure.database import get_db_connection

    conn = get_db_connection()
    concept = conn.execute("SELECT 1 FROM concepts WHERE concept_id = ?", (concept_id,)).fetchone()
    if not concept:
        conn.close()
        raise HTTPException(status_code=404, detail="Concept not found")
    conn.execute("""
        INSERT INTO concept_notes (concept_id, content, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(concept_id) DO UPDATE SET
            content=excluded.content,
            updated_at=CURRENT_TIMESTAMP
    """, (concept_id, request.content))
    conn.commit()
    note = conn.execute(
        "SELECT content, updated_at FROM concept_notes WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    conn.close()
    return {"concept_id": concept_id, "content": note["content"], "updated_at": note["updated_at"]}


@app.get("/api/concepts/{concept_id}/files")
async def get_concept_files(concept_id: str, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    _ensure_learning_tables()
    from infrastructure.database import get_db_connection

    conn = get_db_connection()
    concept = conn.execute("SELECT 1 FROM concepts WHERE concept_id = ?", (concept_id,)).fetchone()
    if not concept:
        conn.close()
        raise HTTPException(status_code=404, detail="Concept not found")
    files = [dict(r) for r in conn.execute("""
        SELECT file_id, filename, file_type, uploaded_at
        FROM concept_files WHERE concept_id = ?
        ORDER BY uploaded_at DESC
    """, (concept_id,)).fetchall()]
    conn.close()
    return {"files": files}


@app.get("/api/concepts/{concept_id}/files/{file_id}")
async def download_concept_file(concept_id: str, file_id: str, authorization: Optional[str] = Header(None)):
    _ensure_learning_tables()
    from infrastructure.database import get_db_connection

    conn = get_db_connection()
    row = conn.execute("""
        SELECT filename, stored_path FROM concept_files
        WHERE concept_id = ? AND file_id = ?
    """, (concept_id, file_id)).fetchone()
    conn.close()
    if not row or not os.path.exists(row["stored_path"]):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(row["stored_path"], filename=row["filename"])


@app.get("/api/pyqs")
async def list_pyqs(
    q: str = Query(""), year: Optional[int] = None, exam: Optional[str] = None,
    subject: Optional[str] = None, type: Optional[str] = None, marks: Optional[int] = None,
    concept_id: Optional[str] = None, has_solution: Optional[bool] = None,
    has_answer: Optional[bool] = None, quality: Optional[str] = "ok",
    limit: int = 20, offset: int = 0,
    authorization: Optional[str] = Header(None),
):
    """Filtered + paginated access to the parsed PYQ bank (754 questions).
    `quality` defaults to 'ok' (hides extraction-failure fragments); pass
    quality='' (or 'all') to include low-quality items."""
    _auth(authorization)
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    qual = None if quality in ("", "all", None) else quality
    items = repo.filter(q=q, year=year, exam=exam, subject=subject, qtype=type,
                        marks=marks, concept_id=concept_id,
                        has_solution=has_solution, has_answer=has_answer, quality=qual)
    return repo.paginate(items, limit=max(1, min(limit, 100)), offset=max(0, offset))


@app.get("/api/pyqs/filters")
async def pyq_filters(authorization: Optional[str] = Header(None)):
    """Available filter values for the PYQ explorer UI."""
    _auth(authorization)
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    return {"years": repo.years(), "exams": repo.exams(),
            "subjects": repo.subjects(), "stats": repo.stats()}


@app.get("/api/pyqs/{pyq_id}")
async def get_pyq(pyq_id: str, authorization: Optional[str] = Header(None)):
    """A single PYQ (incl. solution)."""
    _auth(authorization)
    from knowledge.pyq_repository import get_repository
    rec = get_repository().get(pyq_id)
    if not rec:
        raise HTTPException(status_code=404, detail="PYQ not found")
    return rec


@app.get("/api/quiz/next")
async def quiz_next(
    mode: str = Query("mixed"), concept_id: Optional[str] = None,
    exclude: str = Query(""), authorization: Optional[str] = Header(None),
):
    """
    Return one real, answerable question for the quiz flow.
    mode: topic (needs concept_id) | mixed | weak | revision.
    `track_concept_id` is what mastery should be recorded against.
    """
    _auth(authorization)
    from knowledge.pyq_repository import get_repository
    from infrastructure.database import get_db_connection
    repo = get_repository()
    exclude_ids = set(filter(None, exclude.split(",")))
    track = concept_id

    question = None
    if mode == "topic" and concept_id:
        question = repo.random_question(exclude_ids=exclude_ids, concept_id=concept_id)
        if not question:  # fall back to the concept's subject
            subj = _PREFIX_SUBJECT.get(concept_id.split("_")[0].upper())
            question = repo.random_question(exclude_ids=exclude_ids, subject=subj)
    elif mode in ("weak", "revision"):
        conn = get_db_connection()
        if mode == "revision":
            due_row = conn.execute("SELECT question_id, concept_id FROM revision_queue_items WHERE due_at <= datetime('now')").fetchone()
            if due_row:
                track = due_row["concept_id"]
                question = repo.get(due_row["question_id"])
                
        if not question:
            order = "state_level ASC" if mode == "weak" else "last_revised ASC"
            rows = conn.execute(
                f"SELECT concept_id FROM mastery_states WHERE state_level BETWEEN 2 AND 7 "
                f"ORDER BY {order} LIMIT 8"
            ).fetchall()
            for r in rows:
                cid = r["concept_id"]
                subj = _PREFIX_SUBJECT.get(cid.split("_")[0].upper())
                question = (repo.random_question(exclude_ids=exclude_ids, concept_id=cid)
                            or repo.random_question(exclude_ids=exclude_ids, subject=subj))
                if question:
                    track = cid
                    break
        conn.close()

    if not question:  # mixed / final fallback
        question = repo.random_question(exclude_ids=exclude_ids)

    if not question:
        raise HTTPException(status_code=404, detail="No answerable questions available")

    if not track:
        track = question.get("concept_id")
    return {
        "pyq_id": question["id"],
        "concept_id": question.get("concept_id"),
        "track_concept_id": track,
        "subject": question.get("subject"),
        "question_type": question.get("question_type"),
        "marks": question.get("marks"),
        "year": question.get("year"),
        "exam": question.get("exam"),
        "question_text": question.get("question_text"),
        "options": question.get("options") or {},
        "answer": question.get("answer"),
        "solution": question.get("solution"),
    }


@app.get("/api/revision/due")
async def revision_due(authorization: Optional[str] = Header(None)):
    """Concepts due for revision based on mastery level + time since last revised."""
    _auth(authorization)
    import datetime
    from infrastructure.database import get_db_connection
    from learning.concept_drift import ConceptDriftEngine

    _ensure_learning_tables()

    def threshold_for(level):
        return ConceptDriftEngine.get_threshold(level)

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT m.concept_id, m.state_level, m.last_revised,
               c.subject, c.topic, c.subtopic
        FROM mastery_states m JOIN concepts c ON m.concept_id = c.concept_id
        WHERE m.state_level > 1 AND m.last_revised IS NOT NULL
    """).fetchall()

    now = datetime.datetime.now()
    due, upcoming = [], []
    for r in rows:
        try:
            last = datetime.datetime.fromisoformat(r["last_revised"])
        except Exception:
            continue
        days_since = (now - last).days
        thresh = threshold_for(r["state_level"])
        entry = {
            "concept_id": r["concept_id"], "subject": r["subject"],
            "topic": r["topic"], "subtopic": r["subtopic"],
            "state_level": r["state_level"], "days_since": days_since,
            "due_in_days": max(0, thresh - days_since),
        }
        (due if days_since >= thresh else upcoming).append(entry)

    manual_rows = conn.execute("""
        SELECT r.concept_id, r.due_at,
               c.subject, c.topic, c.subtopic,
               COALESCE(m.state_level, 1) AS state_level
        FROM manual_revision_items r
        JOIN concepts c ON r.concept_id = c.concept_id
        LEFT JOIN mastery_states m ON r.concept_id = m.concept_id
    """).fetchall()
    conn.close()

    for r in manual_rows:
        try:
            due_at = datetime.datetime.fromisoformat(r["due_at"])
        except Exception:
            continue
        delta_days = (due_at.date() - now.date()).days
        entry = {
            "concept_id": r["concept_id"], "subject": r["subject"],
            "topic": r["topic"], "subtopic": r["subtopic"],
            "state_level": r["state_level"], "days_since": 0,
            "due_in_days": max(0, delta_days), "source": "manual",
        }
        target = due if due_at <= now else upcoming
        if not any(x["concept_id"] == entry["concept_id"] and x.get("source") == "manual" for x in target):
            target.append(entry)

    due.sort(key=lambda x: x["days_since"], reverse=True)
    upcoming.sort(key=lambda x: x["due_in_days"])
    
    due_items_count = conn.execute("SELECT COUNT(*) as c FROM revision_queue_items WHERE due_at <= datetime('now')").fetchone()["c"]
    
    return {"due": due, "upcoming": upcoming[:10], "due_count": len(due), "due_items_count": due_items_count}


@app.get("/api/schedule/today")
async def get_schedule_today(authorization: Optional[str] = Header(None)):
    """Generate adaptive daily schedule with revision and new concepts."""
    _auth(authorization)
    from infrastructure.database import get_db_connection
    from planner.adaptive_scheduler import AdaptiveScheduler
    
    conn = get_db_connection()
    user = conn.execute("SELECT daily_goal FROM user_profile WHERE id = 1").fetchone()
    conn.close()
    
    daily_goal = user["daily_goal"] if user and user["daily_goal"] else 10
    minutes = daily_goal * 3  # estimate 3 mins per question mapped to time
    
    plan = AdaptiveScheduler.generate_daily_schedule(minutes)
    return plan


@app.post("/api/revision/schedule")
async def revision_schedule(request: RevisionScheduleRequest, authorization: Optional[str] = Header(None)):
    """Manually add a concept to the revision queue."""
    _auth(authorization)
    _ensure_learning_tables()
    import datetime
    from infrastructure.database import get_db_connection

    due_in_days = max(0, min(365, request.due_in_days))
    due_at = (datetime.datetime.now() + datetime.timedelta(days=due_in_days)).replace(microsecond=0)

    conn = get_db_connection()
    if request.question_id:
        conn.execute("""
            INSERT INTO revision_queue_items (question_id, concept_id, interval_days, due_at, lapses)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(question_id) DO UPDATE SET due_at = excluded.due_at
        """, (request.question_id, request.concept_id, due_in_days, due_at.isoformat()))
    else:
        concept = conn.execute("SELECT subject, topic, subtopic FROM concepts WHERE concept_id = ?", (request.concept_id,)).fetchone()
        if not concept:
            conn.close()
            raise HTTPException(status_code=404, detail="Concept not found")
            
        conn.execute("""
            INSERT INTO manual_revision_items (concept_id, due_at) VALUES (?, ?)
            ON CONFLICT(concept_id) DO UPDATE SET due_at = ?
        """, (request.concept_id, due_at, due_at))
        
        conn.execute("""
            INSERT INTO revision_queue_items (item_type, item_id, due_at, repetition_number, easiness_factor, interval_days)
            VALUES ('concept', ?, ?, 0, 2.5, ?)
        """, (request.concept_id, due_at, due_in_days))
    
    conn.commit()
    conn.close()
    return {
        "success": True,
        "concept_id": request.concept_id,
        "due_at": due_at.isoformat(),
        "due_in_days": due_in_days,
        "subject": concept["subject"],
        "topic": concept["topic"],
        "subtopic": concept["subtopic"],
    }


@app.get("/api/mock/generate")
async def mock_generate(authorization: Optional[str] = Header(None)):
    """Generate a real GATE-pattern mock exam (answers withheld from client)."""
    _auth(authorization)
    from assessment.simulation_engine import SimulationEngine
    return SimulationEngine.generate_mock_exam(65)


class MockGradeRequest(BaseModel):
    exam_id: str
    answers: Dict[str, str]


@app.post("/api/mock/grade")
async def mock_grade(request: MockGradeRequest, authorization: Optional[str] = Header(None)):
    """Grade a previously generated mock and bump mocks_completed."""
    _auth(authorization)
    from assessment.simulation_engine import SimulationEngine, _MOCK_CACHE
    from infrastructure.database import get_db_connection
    import json
    try:
        result = SimulationEngine.grade_mock_exam(request.exam_id, request.answers)
    except KeyError:
        raise HTTPException(status_code=404, detail="Exam expired — generate a new mock.")

    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO user_profile (id, mocks_completed) VALUES (1, 1)
            ON CONFLICT(id) DO UPDATE SET mocks_completed = COALESCE(mocks_completed, 0) + 1
        """)
        
        conn.execute("""
            INSERT INTO mock_attempts (exam_id, score, max_score, correct, incorrect, unattempted, subject_breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.exam_id,
            result.get("total_score", 0),
            result.get("max_score", 100),
            result.get("correct_answers", 0),
            result.get("incorrect_answers", 0),
            result.get("unattempted", 0),
            json.dumps(result.get("per_subject", {}))
        ))
        
        cached = _MOCK_CACHE.get(request.exam_id)
        if cached:
            paper_questions = {q["q_id"]: q for q in cached["paper"]["questions"]}
            for rev in result.get("review", []):
                q = paper_questions.get(rev["q_id"])
                if not q: continue
                marks_awarded = 0.0
                is_correct = 0
                if rev["verdict"] == "correct":
                    marks_awarded = q.get("marks_if_correct", 1)
                    is_correct = 1
                elif rev["verdict"] == "incorrect":
                    marks_awarded = q.get("negative_marks", 0)
                
                conn.execute("""
                    INSERT INTO attempt_items (
                        session_id, source, exam_id, question_id, concept_id, user_answer, correct_answer, is_correct, marks_awarded
                    ) VALUES (?, 'mock', ?, ?, ?, ?, ?, ?, ?)
                """, (
                    None,
                    request.exam_id,
                    q["pyq_id"],
                    q.get("concept_id"),
                    rev.get("your_answer"),
                    rev.get("correct_answer"),
                    is_correct,
                    marks_awarded
                ))
                
                if not is_correct and rev.get("your_answer") is not None:
                    conn.execute("""
                        INSERT INTO revision_queue_items (question_id, concept_id, interval_days, due_at, lapses)
                        VALUES (?, ?, 1, datetime('now', '+1 day'), 1)
                        ON CONFLICT(question_id) DO UPDATE SET
                            interval_days = 1, due_at = datetime('now', '+1 day'), lapses = lapses + 1
                    """, (q["pyq_id"], q.get("concept_id")))

        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"Could not persist mock attempt: {e}")
    return result

@app.get("/api/mistakes")
async def get_mistakes(
    subject: str = Query(""), source: str = Query(""), since: str = Query(""),
    limit: int = 50, offset: int = 0, authorization: Optional[str] = Header(None)
):
    _auth(authorization)
    from infrastructure.database import get_db_connection
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    
    query = "SELECT * FROM attempt_items WHERE is_correct = 0 AND user_answer IS NOT NULL"
    params = []
    if source:
        query += " AND source = ?"
        params.append(source)
    if since:
        query += " AND timestamp >= ?"
        params.append(since)
    
    query += " ORDER BY timestamp DESC"
    
    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    mistakes = []
    for r in rows:
        q_detail = repo.get(r["question_id"])
        if not q_detail: continue
        if subject and q_detail.get("subject") != subject: continue
        
        mistakes.append({
            "attempt": dict(r),
            "question": q_detail
        })
    
    return mistakes[offset:offset+limit]

@app.get("/api/mock/attempts")
async def get_mock_attempts(authorization: Optional[str] = Header(None)):
    _auth(authorization)
    from infrastructure.database import get_db_connection
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM mock_attempts ORDER BY taken_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/mock/attempts/{exam_id}/review")
async def review_mock_attempt(exam_id: str, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    from infrastructure.database import get_db_connection
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM attempt_items WHERE exam_id = ? ORDER BY item_id ASC", (exam_id,)).fetchall()
    conn.close()
    
    review = []
    for r in rows:
        q_detail = repo.get(r["question_id"])
        if not q_detail: continue
        review.append({
            "attempt": dict(r),
            "question": q_detail
        })
    return review


class ProfileRequest(BaseModel):
    display_name: Optional[str] = None
    target_air: Optional[int] = None
    exam_date: Optional[str] = None
    daily_goal: Optional[int] = None


@app.get("/api/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    _auth(authorization)
    from infrastructure.database import get_db_connection
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"onboarded": False, "display_name": None, "target_air": None,
                "exam_date": None, "daily_goal": 10, "mocks_completed": 0}
    d = dict(row)
    d["onboarded"] = bool(d.get("exam_date") or d.get("target_air"))
    return d


@app.put("/api/profile")
async def put_profile(request: ProfileRequest, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    from infrastructure.database import get_db_connection
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO user_profile (id, daily_goal) VALUES (1, 10)")
    conn.execute("""
        UPDATE user_profile SET
            display_name = COALESCE(?, display_name),
            target_air   = COALESCE(?, target_air),
            exam_date    = COALESCE(?, exam_date),
            daily_goal   = COALESCE(?, daily_goal)
        WHERE id = 1
    """, (request.display_name, request.target_air, request.exam_date, request.daily_goal))
    conn.commit()
    row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    conn.close()
    return dict(row)


@app.get("/api/gamification")
async def gamification(authorization: Optional[str] = Header(None)):
    _auth(authorization)
    from analytics.gamification import get_gamification
    return get_gamification()


@app.get("/api/analytics/overview")
async def analytics_overview(authorization: Optional[str] = Header(None)):
    """Series powering the Analytics charts."""
    _auth(authorization)
    from infrastructure.database import get_db_connection
    conn = get_db_connection()

    # 1. Accuracy trend by day
    trend = [dict(r) for r in conn.execute("""
        SELECT DATE(timestamp) AS day,
               COUNT(*) AS attempts,
               SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
        FROM quiz_attempts WHERE timestamp IS NOT NULL
        GROUP BY DATE(timestamp) ORDER BY day
    """).fetchall()]
    for t in trend:
        t["accuracy"] = round(t["correct"] / t["attempts"] * 100, 1) if t["attempts"] else 0

    # 2. Mastery distribution (levels 1..8)
    dist_rows = {r["state_level"]: r["c"] for r in conn.execute(
        "SELECT state_level, COUNT(*) AS c FROM mastery_states GROUP BY state_level").fetchall()}
    mastery_distribution = [{"level": lvl, "count": dist_rows.get(lvl, 0)} for lvl in range(1, 9)]

    # 3. Subject readiness (avg mastery / 8)
    subject_readiness = [{
        "subject": r["subject"],
        "readiness": round((r["avg_lvl"] or 1) / 8 * 100, 1),
        "concepts": r["c"],
    } for r in conn.execute("""
        SELECT c.subject, AVG(COALESCE(m.state_level, 1)) AS avg_lvl, COUNT(*) AS c
        FROM concepts c LEFT JOIN mastery_states m ON c.concept_id = m.concept_id
        GROUP BY c.subject ORDER BY c.subject
    """).fetchall()]

    # 4. Confidence calibration (accuracy per confidence 1..5)
    calib_rows = {r["confidence"]: r for r in conn.execute("""
        SELECT confidence, COUNT(*) AS attempts,
               SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
        FROM quiz_attempts GROUP BY confidence
    """).fetchall()}
    confidence_calibration = []
    for c in range(1, 6):
        row = calib_rows.get(c)
        attempts = row["attempts"] if row else 0
        correct = row["correct"] if row else 0
        confidence_calibration.append({
            "confidence": c, "attempts": attempts,
            "accuracy": round(correct / attempts * 100, 1) if attempts else 0,
        })

    conn.close()
    return {
        "accuracy_trend": trend,
        "mastery_distribution": mastery_distribution,
        "subject_readiness": subject_readiness,
        "confidence_calibration": confidence_calibration,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
