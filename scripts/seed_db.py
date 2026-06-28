import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

def seed_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    concepts = [
        ("ML_RV_001", "Machine Learning", "Probability", "Random Variable", "[]", 1.2),
        ("ML_CP_001", "Machine Learning", "Probability", "Conditional Probability", '["ML_RV_001"]', 1.5),
        ("ML_BR_001", "Machine Learning", "Probability", "Bayes Rule", '["ML_CP_001"]', 2.0),
        ("ML_NB_001", "Machine Learning", "Algorithms", "Naive Bayes", '["ML_BR_001"]', 2.5),
        ("LA_EIG_001", "Linear Algebra", "Matrices", "Eigenvalues", "[]", 2.0)
    ]

    for c in concepts:
        cursor.execute("""
            INSERT OR IGNORE INTO concepts 
            (concept_id, subject, topic, subtopic, prerequisites, importance_weight) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, c)
        
        # Also initialize mastery state to Unknown (1)
        cursor.execute("""
            INSERT OR IGNORE INTO mastery_states (concept_id, state_level) 
            VALUES (?, 1)
        """, (c[0],))

    conn.commit()
    conn.close()
    print("Database seeded with 5 concepts.")

if __name__ == "__main__":
    seed_db()
