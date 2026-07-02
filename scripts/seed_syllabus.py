import sqlite3
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.syllabus_data import GATE_DA_SYLLABUS

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")


def seed_syllabus():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Rebuild the concepts registry cleanly (guarantees the exact column set),
    # but PRESERVE mastery_states so re-running never wipes a learner's progress.
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

    # mastery_states: create if missing, add a level-1 row for any NEW concept,
    # leave existing progress untouched (INSERT OR IGNORE).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mastery_states (
            concept_id TEXT PRIMARY KEY,
            state_level INTEGER DEFAULT 1,
            accuracy REAL DEFAULT 0.0,
            last_revised TEXT,
            FOREIGN KEY(concept_id) REFERENCES concepts(concept_id)
        )
    """)
    for c in GATE_DA_SYLLABUS:
        cursor.execute(
            "INSERT OR IGNORE INTO mastery_states (concept_id, state_level, accuracy) VALUES (?, 1, 0.0)",
            (c["concept_id"],)
        )

    conn.commit()
    conn.close()
    n_subjects = len({c["subject"] for c in GATE_DA_SYLLABUS})
    print(f"Seeded {len(GATE_DA_SYLLABUS)} concepts across {n_subjects} GATE DA subjects "
          "(mastery progress preserved).")


if __name__ == "__main__":
    seed_syllabus()
