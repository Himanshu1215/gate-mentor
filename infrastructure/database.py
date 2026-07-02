import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

def init_db():
    """Initializes the SQLite database exactly as defined in the TDS."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Concepts Table (Global Concept Registry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concepts (
        concept_id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        subtopic TEXT,
        prerequisites TEXT, -- Stored as JSON string
        importance_weight REAL DEFAULT 1.0,
        est_learning_time_mins INTEGER DEFAULT 30,
        est_revision_time_mins INTEGER DEFAULT 10,
        recommended_resources TEXT, -- JSON string
        linked_pyqs TEXT -- JSON string
    )
    """)
    
    # 2. Mastery States Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mastery_states (
        concept_id TEXT PRIMARY KEY,
        state_level INTEGER DEFAULT 1, -- 1: Unknown to 8: Mastered
        accuracy REAL DEFAULT 0.0,
        last_revised TIMESTAMP,
        FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
    )
    """)
    
    # 3. Learning Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learning_sessions (
        session_id TEXT PRIMARY KEY,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        goals TEXT,
        reflection TEXT
    )
    """)

    # 4. Quiz Attempts (Linked to Session & Concept)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        attempt_id TEXT PRIMARY KEY,
        session_id TEXT,
        concept_id TEXT,
        is_correct BOOLEAN,
        confidence INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES learning_sessions(session_id),
        FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
    )
    """)

    # 5. User Profile (single-row settings: target AIR, exam date, daily goal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        display_name TEXT,
        target_air INTEGER,
        exam_date TEXT,
        daily_goal INTEGER DEFAULT 10,
        mocks_completed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 6. User notes written directly against a syllabus concept.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concept_notes (
        concept_id TEXT PRIMARY KEY,
        content TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
    )
    """)

    # 7. Uploaded personal study material metadata. The actual files live on disk.
    cursor.execute("""
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

    # 8. Manual revision queue entries created from the syllabus detail page.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS manual_revision_items (
        concept_id TEXT PRIMARY KEY,
        due_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
    )
    """)

    # Phase 1: Attempt items
    cursor.execute("""
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempt_items_wrong ON attempt_items(is_correct, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempt_items_exam ON attempt_items(exam_id)")

    # Phase 1: Mock attempts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mock_attempts (
      exam_id     TEXT PRIMARY KEY,
      taken_at    TEXT DEFAULT (datetime('now')),
      score REAL, max_score REAL,
      correct INTEGER, incorrect INTEGER, unattempted INTEGER,
      subject_breakdown TEXT
    )
    """)

    # Phase 2: Revision queue items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revision_queue_items (
      question_id  TEXT PRIMARY KEY,
      concept_id   TEXT,
      interval_days INTEGER DEFAULT 1,
      due_at       TEXT NOT NULL,
      lapses       INTEGER DEFAULT 1,
      created_at   TEXT DEFAULT (datetime('now'))
    )
    """)

    # Phase 4: Chat messages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('user','assistant')),
      content TEXT NOT NULL,
      timestamp TEXT DEFAULT (datetime('now'))
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id)")

    conn.commit()
    conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory for dict-like row access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row  # access columns by name
    return conn

if __name__ == "__main__":
    init_db()
    print("TDS database schemas initialized successfully.")
