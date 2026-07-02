import sqlite3
import os
import datetime
from typing import List

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class ConceptDriftEngine:
    """Calculates memory decay (drift) and degrades mastery state if revision is ignored."""
    
    @staticmethod
    def get_threshold(state_level: int) -> int:
        if state_level <= 3: return 3
        if state_level <= 5: return 7
        if state_level <= 7: return 14
        return 30
        
    @staticmethod
    def apply_drift_if_needed() -> None:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE user_profile ADD COLUMN last_drift_run TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        cursor.execute("SELECT last_drift_run FROM user_profile WHERE id = 1")
        row = cursor.fetchone()
        now = datetime.datetime.now()
        should_run = True
        
        if row and row[0]:
            try:
                last_run = datetime.datetime.fromisoformat(row[0])
                if (now - last_run).total_seconds() < 86400:
                    should_run = False
            except:
                pass
                
        if should_run:
            ConceptDriftEngine.apply_drift()
            cursor.execute("UPDATE user_profile SET last_drift_run = ? WHERE id = 1", (now.isoformat(),))
            conn.commit()
        conn.close()

    @staticmethod
    def apply_drift() -> List[str]:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.datetime.now()
        degraded_concepts = []
        
        cursor.execute("SELECT concept_id, state_level, last_revised FROM mastery_states WHERE state_level > 1")
        rows = cursor.fetchall()
        
        for row in rows:
            concept_id, state_level, last_revised_str = row
            if not last_revised_str:
                continue
                
            last_revised = datetime.datetime.fromisoformat(last_revised_str)
            days_since = (now - last_revised).days
            
            threshold = ConceptDriftEngine.get_threshold(state_level)
            should_degrade = days_since >= threshold
                
            if should_degrade:
                new_state = max(1, state_level - 1)
                cursor.execute(
                    "UPDATE mastery_states SET state_level = ? WHERE concept_id = ?",
                    (new_state, concept_id)
                )
                degraded_concepts.append(concept_id)
                
        conn.commit()
        conn.close()
        return degraded_concepts

if __name__ == "__main__":
    drifted = ConceptDriftEngine.apply_drift()
    print(f"Applied Concept Drift. Concepts degraded: {drifted}")
