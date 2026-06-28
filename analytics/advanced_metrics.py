import sqlite3
import os
from typing import Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class AdvancedMetrics:
    """Computes high-level learning indicators like Confidence Calibration."""
    
    @staticmethod
    def calculate_confidence_calibration() -> Dict[str, Any]:
        """
        Analyzes quiz logs to see if the user is overconfident or underconfident.
        Confidence is 1-5. If high confidence (4-5) but incorrect frequently -> Overconfident.
        If low confidence (1-2) but correct frequently -> Underconfident.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Analyze historical quiz attempts
        cursor.execute("SELECT is_correct, confidence FROM quiz_attempts")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {"status": "Needs Data", "overconfident_rate": 0, "underconfident_rate": 0}
            
        overconfident_count = 0
        underconfident_count = 0
        
        for is_correct, confidence in rows:
            if not is_correct and confidence >= 4:
                overconfident_count += 1
            elif is_correct and confidence <= 2:
                underconfident_count += 1
                
        total = len(rows)
        over_rate = round(overconfident_count / total * 100, 2)
        under_rate = round(underconfident_count / total * 100, 2)
        
        status = "Calibrated"
        if over_rate > 20:
            status = "Highly Overconfident (Risk of Negative Marks)"
        elif under_rate > 20:
            status = "Underconfident (Hesitant on Exams)"
            
        return {
            "status": status,
            "overconfident_rate": over_rate,
            "underconfident_rate": under_rate,
            "total_questions_analyzed": total
        }

if __name__ == "__main__":
    print(AdvancedMetrics.calculate_confidence_calibration())
