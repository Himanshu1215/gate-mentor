import sqlite3
import os
import datetime
from typing import Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class DashboardAnalytics:
    """Computes real-time analytics for the user frontend."""
    
    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Returns readiness, concepts mastered, and session statistics."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Total Concepts Mastered (Level 8)
        cursor.execute("SELECT COUNT(*) FROM mastery_states WHERE state_level = 8")
        mastered_count = cursor.fetchone()[0]
        
        # 2. Total Concepts in Syllabus
        cursor.execute("SELECT COUNT(*) FROM concepts")
        total_concepts = cursor.fetchone()[0] or 1  # Avoid div zero
        
        # 3. Overall Readiness %
        readiness = (mastered_count / total_concepts) * 100
        
        # 4. Total Quizzes Attempted
        cursor.execute("SELECT COUNT(*) FROM quiz_attempts")
        total_quizzes = cursor.fetchone()[0]
        
        # 5. Last 7 Days Activity (Streak approximation for Milestone 2)
        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        cursor.execute("SELECT COUNT(DISTINCT DATE(start_time)) FROM learning_sessions WHERE start_time >= ?", (week_ago,))
        active_days_last_week = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "mastered_concepts": mastered_count,
            "total_concepts": total_concepts,
            "readiness_percentage": round(readiness, 2),
            "total_quizzes": total_quizzes,
            "active_days_last_week": active_days_last_week
        }

if __name__ == "__main__":
    stats = DashboardAnalytics.get_dashboard_stats()
    print("Dashboard Analytics:", stats)
