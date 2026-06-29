import os
import uuid
from typing import Dict, Any, List

from knowledge.pyq_repository import get_repository

# In-memory cache of generated mocks (exam_id -> full paper incl. answer key).
# Keeps answers off the client during the test; lost on restart (acceptable).
_MOCK_CACHE: Dict[str, Dict[str, Any]] = {}

# GATE pattern: ~65 questions, mix of 1- and 2-mark, negative marking on MCQ.
SUBJECT_QUOTA = [
    ("Probability and Statistics", 16),
    ("Linear Algebra", 10),
    ("Calculus and Optimization", 8),
    ("Programming, DS & Algorithms", 10),
    ("Database Management and Warehousing", 7),
    ("Machine Learning", 9),
    ("Artificial Intelligence", 5),
]


class SimulationEngine:
    """Generates GATE DA mock exams from the real PYQ bank and grades them."""

    @staticmethod
    def generate_mock_exam(num_questions: int = 65) -> Dict[str, Any]:
        repo = get_repository()

        # Draw questions per subject quota, then top up from anywhere answerable.
        picked: List[Dict[str, Any]] = []
        seen = set()
        for subject, quota in SUBJECT_QUOTA:
            for q in repo.sample(quota, subject=subject):
                if q["id"] not in seen:
                    picked.append(q)
                    seen.add(q["id"])

        if len(picked) < num_questions:
            for q in repo.sample(num_questions * 2):
                if q["id"] not in seen:
                    picked.append(q)
                    seen.add(q["id"])
                if len(picked) >= num_questions:
                    break

        picked = picked[:num_questions]

        public_questions = []
        answer_key = {}
        for i, q in enumerate(picked, 1):
            q_id = f"Q_{i}"
            marks = q.get("marks") or (2 if i % 2 == 0 else 1)
            qtype = q.get("question_type") or "MCQ"
            # Negative marking only applies to MCQ in GATE (none for MSQ/NAT).
            neg = 0.0
            if qtype == "MCQ":
                neg = -(marks / 3.0)
            public_questions.append({
                "q_id": q_id,
                "pyq_id": q["id"],
                "concept_id": q.get("concept_id"),
                "subject": q.get("subject"),
                "marks_if_correct": marks,
                "negative_marks": round(neg, 2),
                "type": qtype,
                "question": q.get("question_text", ""),
                "options": q.get("options") or {},
            })
            answer_key[q_id] = {
                "answer": q.get("answer"),
                "marks": marks,
                "negative": round(neg, 2),
                "type": qtype,
                "subject": q.get("subject"),
                "solution": q.get("solution"),
            }

        exam_id = "MOCK_" + uuid.uuid4().hex[:8]
        paper = {
            "exam_id": exam_id,
            "duration_mins": 180,
            "total_marks": sum(q["marks_if_correct"] for q in public_questions),
            "questions": public_questions,
        }
        _MOCK_CACHE[exam_id] = {"key": answer_key, "paper": paper}
        return paper

    @staticmethod
    def grade_mock_exam(exam_id: str, user_answers: Dict[str, str]) -> Dict[str, Any]:
        """Grade a cached mock by exam_id, applying GATE negative marking."""
        cached = _MOCK_CACHE.get(exam_id)
        if not cached:
            raise KeyError(f"Unknown or expired exam_id: {exam_id}")
        key = cached["key"]

        score = 0.0
        correct = incorrect = unattempted = 0
        per_subject: Dict[str, Dict[str, float]] = {}
        review = []

        for q_id, meta in key.items():
            subj = meta.get("subject") or "General"
            ps = per_subject.setdefault(subj, {"correct": 0, "incorrect": 0, "unattempted": 0, "score": 0.0})
            u = (user_answers or {}).get(q_id)
            if not u:
                unattempted += 1
                ps["unattempted"] += 1
                verdict = "unattempted"
            elif str(u).strip().upper() == str(meta["answer"]).strip().upper():
                score += meta["marks"]
                ps["score"] += meta["marks"]
                correct += 1
                ps["correct"] += 1
                verdict = "correct"
            else:
                score += meta["negative"]
                ps["score"] += meta["negative"]
                incorrect += 1
                ps["incorrect"] += 1
                verdict = "incorrect"
            review.append({
                "q_id": q_id, "your_answer": u, "correct_answer": meta["answer"],
                "verdict": verdict, "subject": subj, "solution": meta.get("solution"),
            })

        attempted = correct + incorrect
        return {
            "exam_id": exam_id,
            "total_score": round(score, 2),
            "max_score": round(sum(m["marks"] for m in key.values()), 2),
            "correct_answers": correct,
            "incorrect_answers": incorrect,
            "unattempted": unattempted,
            "accuracy": round(correct / attempted * 100, 2) if attempted else 0,
            "per_subject": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in per_subject.items()},
            "review": review,
        }


if __name__ == "__main__":
    exam = SimulationEngine.generate_mock_exam(10)
    print("Generated:", exam["exam_id"], exam["total_marks"], "marks,", len(exam["questions"]), "questions")
    ans = {q["q_id"]: "A" for q in exam["questions"][:5]}
    print("Graded:", SimulationEngine.grade_mock_exam(exam["exam_id"], ans))
