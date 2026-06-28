import sqlite3
import os
from typing import Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class GoalEngine:
    """Tracks user goals (Target AIR) and computes dynamic projections."""
    
    @staticmethod
    def get_current_projection() -> Dict[str, Any]:
        """Calculates current projected AIR based on overall mastery state and accuracy."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get overall accuracy and mastery
        cursor.execute("SELECT AVG(state_level), AVG(accuracy) FROM mastery_states")
        row = cursor.fetchone()
        conn.close()
        
        avg_mastery = row[0] if row and row[0] is not None else 1.0
        avg_accuracy = row[1] if row and row[1] is not None else 0.0
        
        # Purely deterministic projection logic
        # Max mastery = 8.0, Max accuracy = 1.0
        # Simulated logic: if mastery is 8 and accuracy is 1.0, AIR is ~1.
        # If mastery is 1 and accuracy is 0, AIR is ~10000+.
        
        base_air = 10000
        mastery_factor = (avg_mastery - 1) / 7.0  # 0 to 1
        
        projected_score = (mastery_factor * 0.7 + avg_accuracy * 0.3) * 100
        
        # Simple exponential curve mapping score to rank
        if projected_score > 90:
            projected_air = max(1, int(100 - (projected_score - 90) * 10))
        elif projected_score > 70:
            projected_air = int(1000 - (projected_score - 70) * 45)
        else:
            projected_air = int(base_air - (projected_score * 100))
            
        projected_air = max(1, projected_air)
        
        return {
            "avg_mastery_level": round(avg_mastery, 2),
            "avg_accuracy": round(avg_accuracy, 2),
            "projected_score": round(projected_score, 1),
            "projected_air": projected_air,
            "risk_level": "High" if projected_air > 1000 else "Medium" if projected_air > 100 else "Low"
        }

if __name__ == "__main__":
    projection = GoalEngine.get_current_projection()
    print("Current Goal Projection:", projection)
