import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

# Official GATE DA Syllabus subset mapped with exact Concept IDs, dependencies, and importance
GATE_DA_SYLLABUS = [
    # Probability and Statistics
    {
        "concept_id": "PROB_001", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Axioms of Probability",
        "prerequisites": [], "difficulty": 4, "importance_weight": 0.5, "est_learning_time_mins": 60, "est_revision_time_mins": 15
    },
    {
        "concept_id": "PROB_002", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Conditional Probability",
        "prerequisites": ["PROB_001"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20
    },
    {
        "concept_id": "PROB_003", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Bayes Theorem",
        "prerequisites": ["PROB_002"], "difficulty": 8, "importance_weight": 1.0, "est_learning_time_mins": 120, "est_revision_time_mins": 30
    },
    # Linear Algebra
    {
        "concept_id": "LA_001", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Vector Space & Subspace",
        "prerequisites": [], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 90, "est_revision_time_mins": 20
    },
    {
        "concept_id": "LA_002", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Eigenvalues & Eigenvectors",
        "prerequisites": ["LA_001"], "difficulty": 7, "importance_weight": 0.9, "est_learning_time_mins": 120, "est_revision_time_mins": 25
    },
    # Machine Learning
    {
        "concept_id": "ML_001", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Linear Regression",
        "prerequisites": ["LA_001"], "difficulty": 5, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20
    },
    {
        "concept_id": "ML_002", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Naive Bayes Classifier",
        "prerequisites": ["PROB_003"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20
    }
]

def seed_syllabus():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # First, let's make sure the table has all the columns from our new specification.
    # The previous setup might only have (concept_id, subject, topic, prerequisites, est_learning_time_mins, est_revision_time_mins, importance_weight).
    # We will safely alter table if needed, or just insert based on the existing schema.
    # We should re-initialize the table to be safe for Phase 4.
    cursor.execute("DROP TABLE IF EXISTS concepts")
    cursor.execute("""
        CREATE TABLE concepts (
            concept_id TEXT PRIMARY KEY,
            subject TEXT,
            topic TEXT,
            subtopic TEXT,
            prerequisites TEXT,
            difficulty INTEGER,
            importance_weight REAL,
            est_learning_time_mins INTEGER,
            est_revision_time_mins INTEGER
        )
    """)
    
    for c in GATE_DA_SYLLABUS:
        cursor.execute("""
            INSERT INTO concepts 
            (concept_id, subject, topic, subtopic, prerequisites, difficulty, importance_weight, est_learning_time_mins, est_revision_time_mins)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c["concept_id"], c["subject"], c["topic"], c["subtopic"],
            json.dumps(c["prerequisites"]), c["difficulty"], c["importance_weight"], 
            c["est_learning_time_mins"], c["est_revision_time_mins"]
        ))
        
    conn.commit()
    print("Official GATE DA Syllabus successfully seeded into the Global Concept Registry.")
    
    # Also initialize mastery_states for testing so we don't break earlier modules
    cursor.execute("DROP TABLE IF EXISTS mastery_states")
    cursor.execute("""
        CREATE TABLE mastery_states (
            concept_id TEXT PRIMARY KEY,
            state_level INTEGER DEFAULT 1,
            accuracy REAL DEFAULT 0.0,
            last_revised TEXT,
            FOREIGN KEY(concept_id) REFERENCES concepts(concept_id)
        )
    """)
    for c in GATE_DA_SYLLABUS:
        cursor.execute("INSERT INTO mastery_states (concept_id, state_level, accuracy) VALUES (?, 1, 0.0)", (c["concept_id"],))
    conn.commit()
    print("Mastery states initialized for all new concepts.")
    
    conn.close()

if __name__ == "__main__":
    seed_syllabus()
