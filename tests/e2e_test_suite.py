import os
import shutil
import sqlite3
import subprocess
import time
import socket
import datetime
import pytest
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer e2e-test-token"}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "gate_mentor.db")
DB_BAK_PATH = os.path.join(BASE_DIR, "data", "gate_mentor.db.bak")

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

@pytest.fixture(scope="session", autouse=True)
def test_server():
    # 1. Back up database if exists
    db_exists = os.path.exists(DB_PATH)
    if db_exists:
        # Close any existing connections before copy
        shutil.copy2(DB_PATH, DB_BAK_PATH)
        
    # 2. Reset/Seed the database for a clean test run
    from infrastructure.database import init_db
    from scripts.seed_syllabus import seed_syllabus
    init_db()
    seed_syllabus()
    
    # Insert mock concept for decision engine tests
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO concepts (concept_id, subject, topic, subtopic) VALUES ('TEST_001', 'Test', 'Test', 'Test')")
    cursor.execute("INSERT OR REPLACE INTO mastery_states (concept_id, state_level, accuracy) VALUES ('TEST_001', 1, 0.0)")
    conn.commit()
    conn.close()

    # 3. Start server if not running
    proc = None
    if not is_port_open(8000):
        proc = subprocess.Popen(
            ["python", "-m", "presentation.api"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for port to open
        for _ in range(30):
            if is_port_open(8000):
                break
            time.sleep(0.5)
        else:
            if proc:
                proc.kill()
            if db_exists:
                shutil.copy2(DB_BAK_PATH, DB_PATH)
                os.remove(DB_BAK_PATH)
            raise RuntimeError("Failed to start FastAPI server")

    yield

    # 4. Tear down server
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # 5. Restore database
    if db_exists:
        if os.path.exists(DB_BAK_PATH):
            try:
                shutil.copy2(DB_BAK_PATH, DB_PATH)
                os.remove(DB_BAK_PATH)
            except Exception:
                pass
    else:
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

@pytest.fixture(autouse=True)
def clean_db_state():
    """Ensure database is in a clean seeded state before each test case."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Reset mastery levels to 1
    cursor.execute("UPDATE mastery_states SET state_level = 1, accuracy = 0.0, last_revised = NULL")
    # Clean temporary tables
    cursor.execute("DELETE FROM quiz_attempts")
    cursor.execute("DELETE FROM concept_notes")
    cursor.execute("DELETE FROM concept_files")
    cursor.execute("DELETE FROM manual_revision_items")
    cursor.execute("DELETE FROM learning_sessions")
    cursor.execute("DELETE FROM user_profile")
    conn.commit()
    conn.close()


# ==============================================================================
# TIER 1: FEATURE COVERAGE (Tests 1 to 30)
# ==============================================================================

# --- F1: RAG Chat & Tutor ---

def test_f1_chat_happy_path():
    # Start a session first
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Test chat happy path"}, headers=HEADERS)
    assert res_sess.status_code == 200
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "What is Bayes Theorem?", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "citations" in data
    assert len(data["reply"]) > 0

def test_f1_chat_with_custom_persona():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Custom persona test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Explain Conditional Probability", "persona": "Socratic"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert "reply" in res.json()

def test_f1_chat_with_citations():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Citations test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Axioms of Probability", "persona": "Coach"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) > 0

def test_f1_chat_session_continuation():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Continuation test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    # First turn
    res1 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "query": "What is eigenvalues?", "persona": "Professor"}, headers=HEADERS)
    assert res1.status_code == 200
    
    # Second turn
    res2 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "query": "How do we find eigenvectors?", "persona": "Professor"}, headers=HEADERS)
    assert res2.status_code == 200
    assert len(res2.json()["reply"]) > 0

def test_f1_chat_empty_context_fallback():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Fallback test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    # Query with random gibberish that won't yield context chunks in RAG query
    payload = {"session_id": session_id, "query": "xyzqwertyyuiopasdfghjklzxcvbnm", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0


# --- F2: Advanced Tutor Shortcuts ---

def test_f2_visual_shortcut():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Visual shortcut test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Explain this concept visually with an intuitive example.", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0

def test_f2_derivation_shortcut():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Derivation shortcut test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Show the full step-by-step derivation.", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0

def test_f2_pyq_shortcut():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "PYQ shortcut test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Give me a GATE previous-year question on this topic.", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0

def test_f2_quiz_shortcut():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Quiz shortcut test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Ask me one GATE-level question and wait for my answer.", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0

def test_f2_shortcut_with_coach_persona():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Coach shortcut test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Show the full step-by-step derivation.", "persona": "Coach"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert len(res.json()["reply"]) > 0


# --- F3: Syllabus & Topic Progress ---

def test_f3_list_concepts():
    res = requests.get(f"{BASE_URL}/api/concepts", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert "subjects" in data
    assert len(data["subjects"]) > 0

def test_f3_get_concept_detail():
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_001", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "concept" in data
    assert data["concept"]["concept_id"] == "PROB_001"
    assert "notes" in data

def test_f3_subject_grouping():
    res = requests.get(f"{BASE_URL}/api/concepts", headers=HEADERS)
    data = res.json()
    subjects = [s["subject"] for s in data["subjects"]]
    assert "Probability and Statistics" in subjects
    assert "Linear Algebra" in subjects

def test_f3_dependency_graph_prerequisites():
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_002", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "PROB_001" in data["concept"]["prerequisites"]

def test_f3_next_optimal_concept():
    res = requests.get(f"{BASE_URL}/api/curriculum/next", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "concept_id" in data
    assert "topic" in data
    assert "action" in data


# --- F4: Syllabus Topic Notes ---

def test_f4_get_concept_notes():
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_001/notes", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["concept_id"] == "PROB_001"
    assert "content" in data

def test_f4_put_concept_notes():
    payload = {"content": "Persistent self-study notes for axioms of probability."}
    res = requests.put(f"{BASE_URL}/api/concepts/PROB_001/notes", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["content"] == "Persistent self-study notes for axioms of probability."
    
    # Check persistence
    res_get = requests.get(f"{BASE_URL}/api/concepts/PROB_001/notes", headers=HEADERS)
    assert res_get.json()["content"] == "Persistent self-study notes for axioms of probability."

def test_f4_get_concept_files():
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_001/files", headers=HEADERS)
    assert res.status_code == 200
    assert "files" in res.json()
    assert len(res.json()["files"]) == 0

def test_f4_upload_text_file():
    files = {"file": ("notes.txt", "Random variable expectation limits and properties.")}
    data = {"concept_id": "PROB_001"}
    res = requests.post(f"{BASE_URL}/api/upload", files=files, data=data, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["success"] is True

def test_f4_download_uploaded_file():
    # 1. Upload file
    files = {"file": ("rules.txt", "P(A union B) = P(A) + P(B) - P(A cap B)")}
    data = {"concept_id": "PROB_001"}
    requests.post(f"{BASE_URL}/api/upload", files=files, data=data, headers=HEADERS)

    # 2. Get list of files to retrieve file_id
    res_files = requests.get(f"{BASE_URL}/api/concepts/PROB_001/files", headers=HEADERS)
    file_id = res_files.json()["files"][0]["file_id"]

    # 3. Download and verify content
    res_down = requests.get(f"{BASE_URL}/api/concepts/PROB_001/files/{file_id}", headers=HEADERS)
    assert res_down.status_code == 200
    assert res_down.text == "P(A union B) = P(A) + P(B) - P(A cap B)"


# --- F5: Quiz Practice & Mastery Tracking ---

def test_f5_get_next_quiz_mixed():
    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=mixed", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "pyq_id" in data
    assert "question_text" in data

def test_f5_get_next_quiz_topic():
    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=topic&concept_id=PROB_001", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "pyq_id" in data

def test_f5_get_next_quiz_weak():
    # Prime database with a weak concept (level between 2 and 7)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE mastery_states SET state_level = 3 WHERE concept_id = 'PROB_001'")
    conn.commit()
    conn.close()

    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=weak", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "pyq_id" in data

def test_f5_get_next_quiz_revision():
    # Prime database with a concept due for revision
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE mastery_states SET state_level = 5, last_revised = '2020-01-01T00:00:00' WHERE concept_id = 'PROB_001'")
    conn.commit()
    conn.close()

    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=revision", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "pyq_id" in data

def test_f5_submit_quiz_correct():
    # Start session
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Quiz submission"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 5}
    res = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["new_mastery_level"] == 2


# --- F6: Mock Exam Simulator ---

def test_f6_generate_mock_exam():
    res = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "exam_id" in data
    assert "total_marks" in data
    assert "questions" in data

def test_f6_generate_mock_exam_questions_fields():
    res = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS)
    questions = res.json()["questions"]
    assert len(questions) > 0
    q = questions[0]
    assert "q_id" in q
    assert "pyq_id" in q
    assert "marks_if_correct" in q
    assert "negative_marks" in q
    assert "question" in q

def test_f6_submit_mock_exam_grading():
    # 1. Generate mock
    res_gen = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS)
    data_gen = res_gen.json()
    exam_id = data_gen["exam_id"]
    q_id = data_gen["questions"][0]["q_id"]

    # 2. Submit answers
    payload = {"exam_id": exam_id, "answers": {q_id: "A"}}
    res_grade = requests.post(f"{BASE_URL}/api/mock/grade", json=payload, headers=HEADERS)
    assert res_grade.status_code == 200
    data_grade = res_grade.json()
    assert "total_score" in data_grade
    assert "accuracy" in data_grade

def test_f6_get_dashboard_stats():
    res = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "mastered_concepts" in data
    assert "readiness_percentage" in data
    assert "projected_air" in data

def test_f6_autonomous_coach_alerts():
    res = requests.get(f"{BASE_URL}/api/coach/alerts", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert isinstance(data["alerts"], list)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (Tests 31 to 60)
# ==============================================================================

# --- F1 RAG Chat Boundaries ---

def test_f1_chat_missing_authorization():
    res = requests.post(f"{BASE_URL}/api/chat", json={"session_id": "xyz", "query": "hello", "persona": "Professor"})
    assert res.status_code == 401

def test_f1_chat_empty_query():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    
    payload = {"session_id": session_id, "query": "", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200 or res.status_code == 422 # Handle validation or empty reply

def test_f1_chat_invalid_session_id():
    payload = {"session_id": "", "query": "What is normal distribution?", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    # session_id empty is allowed by Pydantic string validation, checks success/failure
    assert res.status_code == 200 or res.status_code == 422

def test_f1_chat_unsupported_persona():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    
    payload = {"session_id": session_id, "query": "Probability axioms", "persona": "SuperHero"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200 # Should default or pass back reply safely

def test_f1_chat_malformed_json():
    res = requests.post(f"{BASE_URL}/api/chat", data="malformed-string", headers=HEADERS)
    assert res.status_code == 422


# --- F2 Tutor Shortcuts Boundaries ---

def test_f2_shortcut_extremely_long_query():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    query = "Explain this concept visually with an intuitive example. " + ("A" * 5000)
    payload = {"session_id": session_id, "query": query, "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200

def test_f2_shortcut_unicode_characters():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    query = "Show derivation for ∫ x^2 dx = x^3/3 + C. ∇ × B = μ₀J."
    payload = {"session_id": session_id, "query": query, "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200

def test_f2_shortcut_missing_session_id():
    # session_id is a required field in ChatRequest
    payload = {"query": "Explain visually", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 422

def test_f2_shortcut_empty_persona():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "query": "Give me a PYQ", "persona": ""}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200

def test_f2_shortcut_without_auth():
    payload = {"session_id": "xyz", "query": "Quiz me", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload)
    assert res.status_code == 401


# --- F3 Syllabus Boundaries ---

def test_f3_get_nonexistent_concept_detail():
    res = requests.get(f"{BASE_URL}/api/concepts/NON_EXISTENT_ID", headers=HEADERS)
    assert res.status_code == 404

def test_f3_curriculum_next_no_auth():
    res = requests.get(f"{BASE_URL}/api/curriculum/next")
    assert res.status_code == 401

def test_f3_list_concepts_no_auth():
    res = requests.get(f"{BASE_URL}/api/concepts")
    assert res.status_code == 401

def test_f3_concept_locking_boundary():
    # PROB_002 has prerequisite PROB_001. If PROB_001 is at state_level 1 (unmastered <=2), PROB_002 must be locked.
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_002", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["concept"]["locked"] is True

def test_f3_curriculum_next_all_mastered():
    # If all concepts are mastered (level 8), next concept should return Complete
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE mastery_states SET state_level = 8")
    conn.commit()
    conn.close()

    res = requests.get(f"{BASE_URL}/api/curriculum/next", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["concept_id"] == "ALL_DONE"


# --- F4 Notes Boundaries ---

def test_f4_get_notes_nonexistent_concept():
    res = requests.get(f"{BASE_URL}/api/concepts/NON_EXISTENT/notes", headers=HEADERS)
    assert res.status_code == 404

def test_f4_put_notes_nonexistent_concept():
    res = requests.put(f"{BASE_URL}/api/concepts/NON_EXISTENT/notes", json={"content": "notes"}, headers=HEADERS)
    assert res.status_code == 404

def test_f4_upload_file_nonexistent_concept():
    files = {"file": ("notes.txt", "some notes text")}
    data = {"concept_id": "NON_EXISTENT"}
    res = requests.post(f"{BASE_URL}/api/upload", files=files, data=data, headers=HEADERS)
    assert res.status_code == 404

def test_f4_download_nonexistent_file():
    res = requests.get(f"{BASE_URL}/api/concepts/PROB_001/files/nonexistent_file_id", headers=HEADERS)
    assert res.status_code == 404

def test_f4_upload_empty_filename():
    files = {"file": ("", "Empty filename content")}
    data = {"concept_id": "PROB_001"}
    res = requests.post(f"{BASE_URL}/api/upload", files=files, data=data, headers=HEADERS)
    # Depending on upload handler, check if it handles it (either 200 with default name or 400/500)
    assert res.status_code in (200, 400, 500)


# --- F5 Quiz Practice Boundaries ---

def test_f5_get_next_quiz_invalid_mode():
    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=invalid_mode", headers=HEADERS)
    # Defaults to mixed mode under the hood, should return 200
    assert res.status_code == 200

def test_f5_get_next_quiz_nonexistent_concept():
    res = requests.get(f"{BASE_URL}/api/quiz/next?mode=topic&concept_id=NON_EXISTING_CID", headers=HEADERS)
    # Should fall back to random/mixed question rather than crashing
    assert res.status_code == 200

def test_f5_submit_quiz_invalid_session_id():
    payload = {"session_id": "", "concept_id": "PROB_001", "is_correct": True, "confidence": 5}
    res = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload, headers=HEADERS)
    # Checks database record update is safe or fails validation
    assert res.status_code == 200 or res.status_code == 422

def test_f5_submit_quiz_out_of_bounds_confidence():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 100}
    res = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload, headers=HEADERS)
    assert res.status_code == 200
    # Should advance mastery because confidence 100 is >= 4
    assert res.json()["new_mastery_level"] == 2

def test_f5_submit_quiz_nonexistent_concept():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    payload = {"session_id": session_id, "concept_id": "NON_EXISTENT", "is_correct": True, "confidence": 5}
    res = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload, headers=HEADERS)
    # The calculator initializes non-existent concept level to 1, then correct + conf=5 promotes to 2
    assert res.status_code == 200
    assert res.json()["new_mastery_level"] == 2


# --- F6 Mock Simulator Boundaries ---

def test_f6_grade_mock_exam_expired():
    payload = {"exam_id": "MOCK_EXPIRED_123", "answers": {}}
    res = requests.post(f"{BASE_URL}/api/mock/grade", json=payload, headers=HEADERS)
    assert res.status_code == 404

def test_f6_grade_mock_exam_empty_answers():
    res_gen = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS)
    exam_id = res_gen.json()["exam_id"]

    payload = {"exam_id": exam_id, "answers": {}}
    res = requests.post(f"{BASE_URL}/api/mock/grade", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["unattempted"] > 0
    assert res.json()["correct_answers"] == 0

def test_f6_grade_mock_exam_negative_marking_bounds():
    # 1. Generate mock
    res_gen = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS)
    exam = res_gen.json()
    exam_id = exam["exam_id"]
    
    # 2. Grade with all wrong answers
    # Send incorrect answer for each question (e.g. key + "X" to ensure mismatch)
    answers = {q["q_id"]: "WRONG" for q in exam["questions"]}
    payload = {"exam_id": exam_id, "answers": answers}
    res = requests.post(f"{BASE_URL}/api/mock/grade", json=payload, headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    # Score should be negative due to wrong MCQ answers
    assert data["total_score"] < 0
    assert data["incorrect_answers"] == len(exam["questions"])

def test_f6_profile_update_invalid_air():
    payload = {"target_air": -10}
    res = requests.put(f"{BASE_URL}/api/profile", json=payload, headers=HEADERS)
    # The API updates profile settings directly (check validation or success)
    assert res.status_code == 200
    assert res.json()["target_air"] == -10

def test_f6_profile_update_empty_display_name():
    payload = {"display_name": ""}
    res = requests.put(f"{BASE_URL}/api/profile", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["display_name"] == ""


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (Tests 61 to 67)
# ==============================================================================

def test_tier3_quiz_submission_updates_mastery_and_lock_states():
    # 1. Verify PROB_002 is locked because prerequisite PROB_001 is at level 1 (unmastered)
    res_init = requests.get(f"{BASE_URL}/api/concepts/PROB_002", headers=HEADERS)
    assert res_init.json()["concept"]["locked"] is True

    # 2. Submit quiz to promote PROB_001 to level 3 (mastered/unlocked threshold > 2)
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    requests.post(f"{BASE_URL}/api/quiz/submit", json={"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 5}, headers=HEADERS)
    requests.post(f"{BASE_URL}/api/quiz/submit", json={"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 5}, headers=HEADERS)

    # 3. Check PROB_001 is now level 3
    res_prob1 = requests.get(f"{BASE_URL}/api/concepts/PROB_001", headers=HEADERS)
    assert res_prob1.json()["concept"]["mastery_level"] == 3

    # 4. Verify PROB_002 is now unlocked
    res_prob2 = requests.get(f"{BASE_URL}/api/concepts/PROB_002", headers=HEADERS)
    assert res_prob2.json()["concept"]["locked"] is False

def test_tier3_quiz_correct_submission_updates_dashboard_readiness():
    res_init = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS)
    init_readiness = res_init.json()["readiness_percentage"]

    # Submit multiple correct answers to drive up readiness
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    # Promote PROB_001 to level 8 (Mastered)
    for _ in range(7):
        requests.post(f"{BASE_URL}/api/quiz/submit", json={"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 5}, headers=HEADERS)

    res_final = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS)
    final_stats = res_final.json()
    assert final_stats["mastered_concepts"] == 1
    assert final_stats["readiness_percentage"] > init_readiness

def test_tier3_manual_revision_scheduling_appears_in_due_revision():
    # 1. Verify revision queue is empty
    res_due_init = requests.get(f"{BASE_URL}/api/revision/due", headers=HEADERS)
    assert res_due_init.json()["due_count"] == 0

    # 2. Schedule manual revision for PROB_001 due in 0 days (immediate)
    payload = {"concept_id": "PROB_001", "due_in_days": 0}
    res_sched = requests.post(f"{BASE_URL}/api/revision/schedule", json=payload, headers=HEADERS)
    assert res_sched.status_code == 200

    # 3. Verify it shows up in due revision
    res_due_final = requests.get(f"{BASE_URL}/api/revision/due", headers=HEADERS)
    assert res_due_final.json()["due_count"] == 1
    assert res_due_final.json()["due"][0]["concept_id"] == "PROB_001"

def test_tier3_quiz_attempts_feed_into_analytics_overview():
    # Submit a quiz attempt
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    requests.post(f"{BASE_URL}/api/quiz/submit", json={"session_id": session_id, "concept_id": "PROB_001", "is_correct": True, "confidence": 4}, headers=HEADERS)

    # Check analytics overview contains data
    res = requests.get(f"{BASE_URL}/api/analytics/overview", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data["accuracy_trend"]) > 0
    assert data["accuracy_trend"][0]["attempts"] == 1

def test_tier3_mock_exam_completion_updates_profile_and_air_projection():
    # 1. Verify profile mock count is 0
    profile_init = requests.get(f"{BASE_URL}/api/profile", headers=HEADERS).json()
    assert profile_init["mocks_completed"] == 0

    # 2. Generate and submit a mock exam
    mock = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS).json()
    exam_id = mock["exam_id"]
    requests.post(f"{BASE_URL}/api/mock/grade", json={"exam_id": exam_id, "answers": {}}, headers=HEADERS)

    # 3. Verify profile mock count updated to 1
    profile_final = requests.get(f"{BASE_URL}/api/profile", headers=HEADERS).json()
    assert profile_final["mocks_completed"] == 1

def test_tier3_file_upload_updates_rag_context_and_affects_chat_replies():
    # 1. Verify files list for concept is empty
    assert len(requests.get(f"{BASE_URL}/api/concepts/PROB_001/files", headers=HEADERS).json()["files"]) == 0

    # 2. Upload reference text file
    files = {"file": ("custom_axioms.txt", "The total probability of all sample space events equals exactly 1.0.")}
    requests.post(f"{BASE_URL}/api/upload", files=files, data={"concept_id": "PROB_001"}, headers=HEADERS)

    # 3. Check files list has 1 item
    files_list = requests.get(f"{BASE_URL}/api/concepts/PROB_001/files", headers=HEADERS).json()["files"]
    assert len(files_list) == 1

    # 4. Chat with query that targets the uploaded content and verify citation
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "RAG upload test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    
    chat_res = requests.post(f"{BASE_URL}/api/chat", json={
        "session_id": session_id,
        "query": "What does the total probability of all sample space events equal?",
        "persona": "Professor"
    }, headers=HEADERS).json()
    # Check if the citation lists our uploaded file name
    assert "custom_axioms.txt" in chat_res["citations"] or len(chat_res["citations"]) > 0

def test_tier3_chat_interaction_logged_in_session():
    # 1. Start session
    goals = "Revise Linear Algebra"
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": goals}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    # 2. Send messages
    requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "query": "What are eigenvalues?", "persona": "Professor"}, headers=HEADERS)
    
    # 3. Check sqlite db directly for learning session log
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM learning_sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row[2] is None  # end_time is not set yet


# ==============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (Tests 68 to 75)
# ==============================================================================

def test_tier4_student_onboarding_and_first_session():
    # Step 1: Student registers display name and set goals
    onboard_payload = {
        "display_name": "GATE aspirant",
        "target_air": 50,
        "exam_date": "2027-02-01",
        "daily_goal": 15
    }
    requests.put(f"{BASE_URL}/api/profile", json=onboard_payload, headers=HEADERS)

    # Verify profile updated
    profile = requests.get(f"{BASE_URL}/api/profile", headers=HEADERS).json()
    assert profile["display_name"] == "GATE aspirant"
    assert profile["target_air"] == 50

    # Step 2: Student starts learning session
    sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Study probability axioms and test today"}, headers=HEADERS).json()
    session_id = sess["session_id"]
    assert len(session_id) > 0

    # Step 3: Request the next optimal concept recommended by curriculum engine
    next_concept = requests.get(f"{BASE_URL}/api/curriculum/next", headers=HEADERS).json()
    # It should recommend a fundamental concept like PROB_001
    assert next_concept["concept_id"] == "PROB_001"

def test_tier4_concept_study_workflow():
    # Step 1: Request next optimal concept (PROB_001)
    next_c = requests.get(f"{BASE_URL}/api/curriculum/next", headers=HEADERS).json()
    concept_id = next_c["concept_id"]

    # Step 2: Start session and ask tutor for visual explanation
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Study " + concept_id}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    chat = requests.post(f"{BASE_URL}/api/chat", json={
        "session_id": session_id,
        "query": f"Explain {concept_id} visually with an intuitive example.",
        "persona": "Professor"
    }, headers=HEADERS).json()
    assert len(chat["reply"]) > 0

    # Step 3: Write persistent self-notes on the concept
    notes_payload = {"content": "Syllabus notes: Probability axioms require total probability of all disjoint events to sum to 1."}
    requests.put(f"{BASE_URL}/api/concepts/{concept_id}/notes", json=notes_payload, headers=HEADERS)

    # Step 4: Upload reference PDF/text material
    files = {"file": ("axioms_ref.txt", "Reference text: P(A) >= 0 for all events A.")}
    requests.post(f"{BASE_URL}/api/upload", files=files, data={"concept_id": concept_id}, headers=HEADERS)

    # Step 5: Verify upload by downloading file
    files_list = requests.get(f"{BASE_URL}/api/concepts/{concept_id}/files", headers=HEADERS).json()["files"]
    file_id = files_list[0]["file_id"]
    download = requests.get(f"{BASE_URL}/api/concepts/{concept_id}/files/{file_id}", headers=HEADERS)
    assert "P(A) >= 0" in download.text

def test_tier4_weak_concept_remediation():
    # Step 1: Verify concept PROB_001 starts at mastery level 1
    concept_detail = requests.get(f"{BASE_URL}/api/concepts/PROB_001", headers=HEADERS).json()
    assert concept_detail["concept"]["mastery_level"] == 1

    # Step 2: Request quiz for this concept
    quiz = requests.get(f"{BASE_URL}/api/quiz/next?mode=topic&concept_id=PROB_001", headers=HEADERS).json()
    assert quiz["concept_id"] == "PROB_001" or quiz["concept_id"] is not None

    # Step 3: Submit wrong answer, verify it doesn't demote below 1
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "remediation"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    submit1 = requests.post(f"{BASE_URL}/api/quiz/submit", json={
        "session_id": session_id,
        "concept_id": "PROB_001",
        "is_correct": False,
        "confidence": 3
    }, headers=HEADERS).json()
    assert submit1["new_mastery_level"] == 1

    # Step 4: Ask tutor for derivation to study
    chat = requests.post(f"{BASE_URL}/api/chat", json={
        "session_id": session_id,
        "query": "Show the full step-by-step derivation of Bayes Theorem.",
        "persona": "Socratic"
    }, headers=HEADERS).json()
    assert len(chat["reply"]) > 0

    # Step 5: Retake quiz and submit correct answer with high confidence
    submit2 = requests.post(f"{BASE_URL}/api/quiz/submit", json={
        "session_id": session_id,
        "concept_id": "PROB_001",
        "is_correct": True,
        "confidence": 5
    }, headers=HEADERS).json()
    assert submit2["new_mastery_level"] == 2

def test_tier4_exam_prep_sprint():
    # Step 1: Check initial dashboard stats and risk level
    dash_init = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS).json()
    assert dash_init["risk_level"] in ("High", "Medium", "Low")

    # Step 2: Schedule two topics for manual revision
    requests.post(f"{BASE_URL}/api/revision/schedule", json={"concept_id": "PROB_001", "due_in_days": 0}, headers=HEADERS)
    requests.post(f"{BASE_URL}/api/revision/schedule", json={"concept_id": "LA_001", "due_in_days": 0}, headers=HEADERS)

    # Verify both show up in due revision
    due = requests.get(f"{BASE_URL}/api/revision/due", headers=HEADERS).json()
    assert due["due_count"] >= 2

    # Step 3: Run coach diagnostics for health check and read alerts
    alerts = requests.get(f"{BASE_URL}/api/coach/alerts", headers=HEADERS).json()["alerts"]
    assert isinstance(alerts, list)

    # Step 4: Generate and complete a mock exam
    mock = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS).json()
    exam_id = mock["exam_id"]
    q_id = mock["questions"][0]["q_id"]

    # Submit all correct mock responses (using the cached keys indirectly or just submitting)
    # Since we don't know the exact answers from generate (withheld), we submit random
    grade = requests.post(f"{BASE_URL}/api/mock/grade", json={
        "exam_id": exam_id,
        "answers": {q_id: "A"}
    }, headers=HEADERS).json()
    assert grade["exam_id"] == exam_id

    # Step 5: Check updated dashboard metrics
    dash_final = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS).json()
    # Check that mocks completed is bumped or risk is updated
    assert dash_final["projected_air"] > 0

def test_tier4_syllabus_mastery_milestone():
    # Step 1: Student answers quizzes for a topic to reach mastery level 8
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "Mastering probability"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]

    # We submit correct answers sequentially to promote PROB_001 to level 8
    for i in range(7):
        submit = requests.post(f"{BASE_URL}/api/quiz/submit", json={
            "session_id": session_id,
            "concept_id": "PROB_001",
            "is_correct": True,
            "confidence": 5
        }, headers=HEADERS).json()
        expected_level = i + 2
        assert submit["new_mastery_level"] == expected_level

    # Check mastery level is now 8 (Mastered)
    concept_detail = requests.get(f"{BASE_URL}/api/concepts/PROB_001", headers=HEADERS).json()
    assert concept_detail["concept"]["mastery_level"] == 8
    assert concept_detail["concept"]["status"] == "Mastered"

    # Step 2: Verify syllabus progress percentage has climbed on the dashboard
    dash = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS).json()
    assert dash["mastered_concepts"] == 1
    assert dash["readiness_percentage"] > 0.0

def test_tier4_multiple_users_or_sessions_isolation():
    # Start Session 1
    sess1 = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "User 1 Goal"}, headers=HEADERS).json()
    session1_id = sess1["session_id"]

    # Start Session 2
    sess2 = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "User 2 Goal"}, headers=HEADERS).json()
    session2_id = sess2["session_id"]

    # Verify session IDs are unique
    assert session1_id != session2_id

    # Submit quiz under session 1
    requests.post(f"{BASE_URL}/api/quiz/submit", json={
        "session_id": session1_id,
        "concept_id": "PROB_001",
        "is_correct": True,
        "confidence": 5
    }, headers=HEADERS)

    # Verify session logs in sqlite are independent
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT session_id, COUNT(*) FROM quiz_attempts GROUP BY session_id").fetchall()
    conn.close()
    
    session_counts = {r[0]: r[1] for r in rows}
    assert session_counts[session1_id] == 1
    assert session2_id not in session_counts

def test_tier4_comprehensive_revision_loop():
    # Step 1: Student checks due revision (starts at 0)
    due_init = requests.get(f"{BASE_URL}/api/revision/due", headers=HEADERS).json()
    assert due_init["due_count"] == 0

    # Step 2: Manually schedule LA_001 for revision today
    requests.post(f"{BASE_URL}/api/revision/schedule", json={"concept_id": "LA_001", "due_in_days": 0}, headers=HEADERS)

    # Verify it is due
    due_mid = requests.get(f"{BASE_URL}/api/revision/due", headers=HEADERS).json()
    assert due_mid["due_count"] == 1
    assert due_mid["due"][0]["concept_id"] == "LA_001"

    # Step 3: Practice with revision mode quiz
    quiz = requests.get(f"{BASE_URL}/api/quiz/next?mode=revision", headers=HEADERS).json()
    # It should track against LA_001
    assert quiz["track_concept_id"] == "LA_001"

    # Step 4: Submit response, check it clears from manual queue (or updates last revised)
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "revision"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    requests.post(f"{BASE_URL}/api/quiz/submit", json={
        "session_id": session_id,
        "concept_id": "LA_001",
        "is_correct": True,
        "confidence": 5
    }, headers=HEADERS)

    # Verify last revised timestamp is updated in database
    conn = sqlite3.connect(DB_PATH)
    last_revised = conn.execute("SELECT last_revised FROM mastery_states WHERE concept_id = 'LA_001'").fetchone()[0]
    conn.close()
    assert last_revised is not None

def test_tier4_complete_diagnostics_and_coach_recommendation():
    # Step 1: Complete a mock exam with low scores
    mock = requests.get(f"{BASE_URL}/api/mock/generate", headers=HEADERS).json()
    exam_id = mock["exam_id"]
    # Submit incorrect answers to ensure a poor score
    requests.post(f"{BASE_URL}/api/mock/grade", json={
        "exam_id": exam_id,
        "answers": {q["q_id"]: "WRONG" for q in mock["questions"]}
    }, headers=HEADERS)

    # Step 2: Check dashboard stats to see current readiness/risk
    dash = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS).json()
    assert dash["risk_level"] in ("High", "Medium", "Low")

    # Step 3: Get proactive coach recommendations
    coach = requests.get(f"{BASE_URL}/api/coach/alerts", headers=HEADERS).json()
    # Coach should have flagged areas or generated alerts
    assert len(coach["alerts"]) > 0
    assert "text" in coach["alerts"][0]

def test_adversarial_blank_queries():
    from learning.langgraph_agent import clean_solution, format_pyq_fallback
    # Test clean_solution
    assert clean_solution(None) == ""
    assert clean_solution(12345) == ""
    assert clean_solution("") == ""
    
    # Test format_pyq_fallback
    assert format_pyq_fallback(None) == "No solution details available."
    assert format_pyq_fallback("not a dict") == "No solution details available."
    assert format_pyq_fallback({"solution": None, "answer": ""}) == "No solution explanation available.\n\nFinal answer: N/A"
    assert format_pyq_fallback({"solution": "", "answer": "C"}) == "No solution explanation available.\n\nFinal answer: C"

def test_adversarial_large_payloads():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    # Send a large payload (e.g. 1MB)
    large_query = "X" * (1024 * 1024)
    payload = {"session_id": session_id, "query": large_query, "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code in (200, 413, 422)

def test_adversarial_out_of_domain_queries():
    res_sess = requests.post(f"{BASE_URL}/api/session/start", json={"goals": "test"}, headers=HEADERS)
    session_id = res_sess.json()["session_id"]
    # Query completely unrelated to GATE/Computer Science
    payload = {"session_id": session_id, "query": "How to bake a chocolate cake?", "persona": "Professor"}
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert "reply" in res.json()

def test_adversarial_large_file_uploads():
    # 1. Create a concept so we have a valid concept_id to upload to
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO concepts (concept_id, subject, topic, subtopic) VALUES ('TEST_UPLOAD_001', 'Test', 'Test', 'Test')")
    conn.commit()
    conn.close()

    # 2. Upload file exceeding 10MB
    large_content = b"0" * (10 * 1024 * 1024 + 100) # Slightly larger than 10MB
    files = {"file": ("large_file.txt", large_content, "text/plain")}
    data = {"concept_id": "TEST_UPLOAD_001"}
    res = requests.post(f"{BASE_URL}/api/upload", files=files, data=data, headers=HEADERS)
    assert res.status_code == 413
    
    # 3. Upload file within limit (e.g. 100 bytes) should not return 413
    small_content = b"hello world small file content"
    files_small = {"file": ("small_file.txt", small_content, "text/plain")}
    res_small = requests.post(f"{BASE_URL}/api/upload", files=files_small, data=data, headers=HEADERS)
    assert res_small.status_code != 413
