import sqlite3
import os
import random
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class SimulationEngine:
    """Generates GATE DA Mock Exams and scores them with negative marking."""
    
    @staticmethod
    def generate_mock_exam(num_questions: int = 65) -> Dict[str, Any]:
        """Generates a full simulated GATE exam (65 questions standard)."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # In a real scenario, this would query a questions bank.
        # For our architecture, we pull the list of topics the user has introduced.
        cursor.execute("SELECT concept_id, topic FROM concepts")
        all_concepts = cursor.fetchall()
        conn.close()
        
        exam_paper = []
        for i in range(min(num_questions, len(all_concepts))):
            c_id, c_topic = all_concepts[i]
            # Mocking the questions
            exam_paper.append({
                "q_id": f"Q_{i+1}",
                "concept_id": c_id,
                "marks_if_correct": 2 if i % 2 == 0 else 1,
                "negative_marks": -0.66 if i % 2 == 0 else -0.33,
                "type": "MCQ",
                "question": f"Mock Question for {c_topic}?",
                "options": ["A", "B", "C", "D"],
                "answer": "A"
            })
            
        return {
            "exam_id": "MOCK_WK_1",
            "duration_mins": 180,
            "total_marks": sum([q["marks_if_correct"] for q in exam_paper]),
            "questions": exam_paper
        }
        
    @staticmethod
    def grade_mock_exam(exam_data: Dict[str, Any], user_answers: Dict[str, str]) -> Dict[str, Any]:
        """Grades the exam applying standard GATE negative marking rules."""
        score = 0.0
        correct = 0
        incorrect = 0
        unattempted = 0
        
        for q in exam_data["questions"]:
            u_ans = user_answers.get(q["q_id"])
            if not u_ans:
                unattempted += 1
            elif u_ans == q["answer"]:
                score += q["marks_if_correct"]
                correct += 1
            else:
                score += q["negative_marks"]
                incorrect += 1
                
        # Update goal engine projections implicitly later
        return {
            "total_score": round(score, 2),
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "unattempted": unattempted,
            "accuracy": round(correct / (correct + incorrect) * 100, 2) if (correct+incorrect) > 0 else 0
        }

if __name__ == "__main__":
    exam = SimulationEngine.generate_mock_exam(5)
    print("Generated Mock Exam:", exam["total_marks"], "marks")
    answers = {"Q_1": "A", "Q_2": "B", "Q_3": "A"}  # 2 correct, 1 wrong, 2 unattempted
    result = SimulationEngine.grade_mock_exam(exam, answers)
    print("Graded Result:", result)
