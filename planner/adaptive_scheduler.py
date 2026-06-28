import sqlite3
import os
import datetime
from typing import List, Dict, Any
from curriculum.dependency_graph import CurriculumEngine

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class AdaptiveScheduler:
    """Generates a dynamic daily schedule combining new topics and spaced repetition revisions."""
    
    @staticmethod
    def generate_daily_schedule(available_minutes: int = 120) -> Dict[str, Any]:
        """
        Allocates available study time between:
        1. Revisions (Topics with low accuracy or due for review)
        2. New Learning (Next unlocked concept in the Curriculum DAG)
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        schedule = {
            "revision_tasks": [],
            "learning_tasks": [],
            "estimated_time_mins": 0
        }
        time_used = 0
        
        # 1. Fetch Revision Candidates (Mastery > 1 and < 8, accuracy < 0.7 or haven't been revised recently)
        # For Milestone 2, we just pick the lowest accuracy active concepts
        cursor.execute("""
            SELECT m.concept_id, c.topic, c.est_revision_time_mins, m.accuracy 
            FROM mastery_states m
            JOIN concepts c ON m.concept_id = c.concept_id
            WHERE m.state_level > 1 AND m.state_level < 8
            ORDER BY m.accuracy ASC LIMIT 3
        """)
        
        revisions = cursor.fetchall()
        for rev in revisions:
            cid, topic, time_req, acc = rev
            if time_used + time_req <= available_minutes * 0.4:  # Max 40% time on revision
                schedule["revision_tasks"].append({"concept_id": cid, "topic": topic, "task_type": "Revise"})
                time_used += time_req
        
        # 2. Fetch New Learning Candidates
        # Get the absolute next optimal concept from the Curriculum Engine
        next_concept_id = CurriculumEngine.get_next_optimal_concept()
        
        if next_concept_id:
            cursor.execute("SELECT topic, est_learning_time_mins FROM concepts WHERE concept_id = ?", (next_concept_id,))
            new_topic_data = cursor.fetchone()
            if new_topic_data:
                topic_name, time_req = new_topic_data
                if time_used + time_req <= available_minutes:
                    schedule["learning_tasks"].append({
                        "concept_id": next_concept_id, 
                        "topic": topic_name, 
                        "task_type": "Learn"
                    })
                    time_used += time_req
                    
        conn.close()
        schedule["estimated_time_mins"] = time_used
        
        return schedule

if __name__ == "__main__":
    daily_plan = AdaptiveScheduler.generate_daily_schedule(120)
    print("Today's Adaptive Schedule:", daily_plan)
