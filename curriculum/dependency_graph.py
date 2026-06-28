import sqlite3
import json
import os
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class CurriculumEngine:
    """Manages the Concept DAG and calculates the next optimal topic."""
    
    @staticmethod
    def get_all_concepts() -> Dict[str, Dict]:
        """Loads the entire concept registry and current mastery states into memory as a DAG."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.concept_id, c.subject, c.topic, c.prerequisites, c.importance_weight,
                   m.state_level
            FROM concepts c
            LEFT JOIN mastery_states m ON c.concept_id = m.concept_id
        """)
        
        graph = {}
        for row in cursor.fetchall():
            concept_id, subject, topic, prereqs_str, weight, state_level = row
            try:
                prereqs = json.loads(prereqs_str) if prereqs_str else []
            except Exception:
                prereqs = []
                
            graph[concept_id] = {
                "subject": subject,
                "topic": topic,
                "prerequisites": prereqs,
                "importance_weight": weight,
                "state_level": state_level if state_level is not None else 1
            }
            
        conn.close()
        return graph

    @staticmethod
    def _is_unlocked(concept: Dict, graph: Dict[str, Dict]) -> bool:
        """A concept is unlocked if all its prerequisites have a mastery state > 2 (Competent)."""
        for prereq_id in concept["prerequisites"]:
            prereq_data = graph.get(prereq_id)
            if not prereq_data or prereq_data["state_level"] <= 2:
                return False
        return True

    @staticmethod
    def get_next_optimal_concept() -> Optional[str]:
        """
        Traverses the graph to find the most important concept that is:
        1. Not yet mastered (state_level < 8)
        2. Has all prerequisites met (unlocked)
        Returns the concept_id.
        """
        graph = CurriculumEngine.get_all_concepts()
        
        candidates = []
        for cid, data in graph.items():
            if data["state_level"] < 8 and CurriculumEngine._is_unlocked(data, graph):
                candidates.append((cid, data["importance_weight"], data["state_level"]))
                
        if not candidates:
            return None
            
        # Sort candidates by:
        # 1. Highest importance weight (Descending)
        # 2. Lowest mastery level (Ascending) - prioritize what we don't know
        candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
        
        return candidates[0][0]

if __name__ == "__main__":
    # Test logic
    next_concept = CurriculumEngine.get_next_optimal_concept()
    print(f"The next optimal concept to study is: {next_concept}")
