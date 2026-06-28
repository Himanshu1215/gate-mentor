import sqlite3
import os
import datetime
from typing import List

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class ConceptDriftEngine:
    """Calculates memory decay (drift) and degrades mastery state if revision is ignored."""
    
    @staticmethod
    def apply_drift() -> List[str]:
        """
        Scans all concepts. If a concept hasn't been revised in X days (based on its mastery level),
        it degrades the mastery level and logs it as drifted.
        Returns a list of concept_ids that degraded.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Drift rules:
        # Level 2-3: degrade after 3 days
        # Level 4-5: degrade after 7 days
        # Level 6-7: degrade after 14 days
        # Level 8: degrades after 30 days
        
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
            
            should_degrade = False
            if state_level <= 3 and days_since >= 3:
                should_degrade = True
            elif state_level <= 5 and days_since >= 7:
                should_degrade = True
            elif state_level <= 7 and days_since >= 14:
                should_degrade = True
            elif state_level == 8 and days_since >= 30:
                should_degrade = True
                
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
