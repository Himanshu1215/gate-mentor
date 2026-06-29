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

    conn.commit()
    conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory for dict-like row access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name
    return conn

if __name__ == "__main__":
    init_db()
    print("TDS database schemas initialized successfully.")
