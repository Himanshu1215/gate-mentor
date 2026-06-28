import sqlite3
import os
import datetime
from typing import Dict, Any

from core.event_bus import bus, Events

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class MasteryCalculator:
    """Deterministic decision engine for updating mastery states."""
    
    @staticmethod
    def update_mastery(concept_id: str, is_correct: bool, confidence: int):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Fetch current state
        cursor.execute("SELECT state_level, accuracy FROM mastery_states WHERE concept_id = ?", (concept_id,))
        row = cursor.fetchone()
        
        if not row:
            # Concept not found, initialize it
            state_level = 1
            accuracy = 0.0
        else:
            state_level, accuracy = row
            
        # Deterministic State Transition Logic
        if is_correct:
            if confidence >= 4 and state_level < 8:
                state_level += 1  # Move up a mastery level
            # simple running average for accuracy
            accuracy = (accuracy + 1.0) / 2.0
        else:
            if state_level > 1:
                state_level -= 1  # Demote mastery level
            accuracy = accuracy / 2.0
            
        now = datetime.datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO mastery_states (concept_id, state_level, accuracy, last_revised)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(concept_id) DO UPDATE SET
                state_level=excluded.state_level,
                accuracy=excluded.accuracy,
                last_revised=excluded.last_revised
        """, (concept_id, state_level, accuracy, now))
        
        conn.commit()
        conn.close()
        return state_level

class DecisionEngine:
    def __init__(self):
        bus.subscribe(Events.QUIZ_COMPLETED, self.handle_quiz_completed)
        
    async def handle_quiz_completed(self, data: Dict[str, Any]):
        concept_id = data.get("concept_id")
        is_correct = data.get("is_correct")
        confidence = data.get("confidence", 3)
        
        new_state = MasteryCalculator.update_mastery(concept_id, is_correct, confidence)
        print(f"[Decision Engine] Updated {concept_id} to Mastery Level {new_state}")
        
        # Publish downstream event
        await bus.publish(Events.CONCEPT_MASTERED, {"concept_id": concept_id, "new_level": new_state})

if __name__ == "__main__":
    # Simple test for deterministic logic
    print("Testing Mastery Update for ML_NB_001 (Correct, High Confidence)")
    new_lvl = MasteryCalculator.update_mastery("ML_NB_001", is_correct=True, confidence=5)
    print(f"New Level: {new_lvl}")
