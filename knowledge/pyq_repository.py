"""
knowledge/pyq_repository.py
───────────────────────────
In-memory repository over the parsed PYQ JSONs in
knowledge/official/pyqs/parsed/*.json (~754 small files). Loaded once at import
and reused by the /api/pyqs, /api/quiz/next and /api/mock/* endpoints.

Each PYQ JSON looks like:
    {"year": 2024, "exam": "GATE DA", "question_id": "Q45", "question_seq": 399,
     "question_type": "MCQ", "marks": 2, "difficulty": 8, "concept_id": "PROB_003",
     "question_text": "...", "options": {"A": "...", ...}, "answer": "A",
     "solution": "..."}

The on-disk `question_id`/`question_seq` are not globally unique, so the file
stem is used as the stable public `id`.
"""

import os
import re
import json
import glob
import random
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")

# concept_id prefix -> subject (matches scripts/seed_syllabus.py)
PREFIX_SUBJECT = {
    "PROB": "Probability and Statistics",
    "LA": "Linear Algebra",
    "CALC": "Calculus and Optimization",
    "DSA": "Programming, DS & Algorithms",
    "DB": "Database Management and Warehousing",
    "ML": "Machine Learning",
    "AI": "Artificial Intelligence",
}

# Fallback keyword -> subject for questions tagged GENERAL / unmapped.
SUBJECT_KEYWORDS = [
    ("bayes", "Probability and Statistics"),
    ("probability", "Probability and Statistics"),
    ("random variable", "Probability and Statistics"),
    ("distribution", "Probability and Statistics"),
    ("variance", "Probability and Statistics"),
    ("expectation", "Probability and Statistics"),
    ("hypothesis", "Probability and Statistics"),
    ("eigen", "Linear Algebra"),
    ("matrix", "Linear Algebra"),
    ("determinant", "Linear Algebra"),
    ("vector", "Linear Algebra"),
    ("derivative", "Calculus and Optimization"),
    ("integral", "Calculus and Optimization"),
    ("gradient", "Calculus and Optimization"),
    ("maxima", "Calculus and Optimization"),
    ("algorithm", "Programming, DS & Algorithms"),
    ("array", "Programming, DS & Algorithms"),
    ("sorting", "Programming, DS & Algorithms"),
    ("graph", "Programming, DS & Algorithms"),
    ("complexity", "Programming, DS & Algorithms"),
    ("sql", "Database Management and Warehousing"),
    ("relation", "Database Management and Warehousing"),
    ("normal form", "Database Management and Warehousing"),
    ("regression", "Machine Learning"),
    ("classifier", "Machine Learning"),
    ("clustering", "Machine Learning"),
    ("neural", "Machine Learning"),
    ("gradient descent", "Machine Learning"),
    ("heuristic", "Artificial Intelligence"),
    ("search", "Artificial Intelligence"),
    ("logic", "Artificial Intelligence"),
]


def subject_for(concept_id: Optional[str], question_text: str = "") -> str:
    """Derive a subject from concept_id prefix, else keyword-match the text."""
    if concept_id and concept_id != "GENERAL":
        prefix = concept_id.split("_")[0].upper()
        if prefix in PREFIX_SUBJECT:
            return PREFIX_SUBJECT[prefix]
    low = (question_text or "").lower()
    for kw, subj in SUBJECT_KEYWORDS:
        if kw in low:
            return subj
    return "General"


class PYQRepository:
    """Loads and queries the parsed PYQ bank."""

    def __init__(self, parsed_dir: str = PARSED_DIR):
        self.parsed_dir = parsed_dir
        self._items: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        files = sorted(glob.glob(os.path.join(self.parsed_dir, "*.json")))
        for path in files:
            try:
                with open(path, encoding="utf-8") as f:
                    rec = json.load(f)
            except Exception as e:
                logger.warning(f"Skipping unreadable PYQ {path}: {e}")
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            rec["id"] = stem
            rec["subject"] = subject_for(rec.get("concept_id"), rec.get("question_text", ""))
            rec["has_answer"] = bool(rec.get("answer"))
            rec["has_solution"] = bool(rec.get("solution"))
            self._items.append(rec)
            self._by_id[stem] = rec
        logger.info(
            f"PYQRepository loaded {len(self._items)} questions "
            f"({sum(i['has_answer'] for i in self._items)} answerable, "
            f"{sum(i['has_solution'] for i in self._items)} with solutions)."
        )

    # ── lookups ──────────────────────────────────────────────────────────────
    def get(self, pyq_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(pyq_id)

    def subjects(self) -> List[str]:
        return sorted({i["subject"] for i in self._items})

    def years(self) -> List[int]:
        return sorted({i["year"] for i in self._items if i.get("year")}, reverse=True)

    def exams(self) -> List[str]:
        return sorted({i["exam"] for i in self._items if i.get("exam")})

    def stats(self) -> Dict[str, int]:
        return {
            "total": len(self._items),
            "answerable": sum(i["has_answer"] for i in self._items),
            "with_solution": sum(i["has_solution"] for i in self._items),
        }

    # ── filtering / search ─────────────────────────────────────────────────
    def filter(
        self,
        q: str = "",
        year: Optional[int] = None,
        exam: Optional[str] = None,
        subject: Optional[str] = None,
        qtype: Optional[str] = None,
        marks: Optional[int] = None,
        concept_id: Optional[str] = None,
        has_solution: Optional[bool] = None,
        has_answer: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        ql = (q or "").strip().lower()
        out = []
        for it in self._items:
            if year and it.get("year") != year:
                continue
            if exam and it.get("exam") != exam:
                continue
            if subject and it.get("subject") != subject:
                continue
            if qtype and it.get("question_type") != qtype:
                continue
            if marks is not None and it.get("marks") != marks:
                continue
            if concept_id and it.get("concept_id") != concept_id:
                continue
            if has_solution is not None and it["has_solution"] != has_solution:
                continue
            if has_answer is not None and it["has_answer"] != has_answer:
                continue
            if ql:
                hay = (it.get("question_text", "") + " " +
                       " ".join((it.get("options") or {}).values())).lower()
                if ql not in hay:
                    continue
            out.append(it)
        return out

    def paginate(self, items: List[Dict[str, Any]], limit: int, offset: int) -> Dict[str, Any]:
        total = len(items)
        page = items[offset: offset + limit]
        return {"total": total, "limit": limit, "offset": offset, "items": page}

    # ── question selection for quizzes / mocks ──────────────────────────────
    def answerable(self, **filters) -> List[Dict[str, Any]]:
        filters["has_answer"] = True
        return self.filter(**filters)

    def random_question(self, exclude_ids=None, **filters) -> Optional[Dict[str, Any]]:
        pool = self.answerable(**filters)
        if exclude_ids:
            pool = [p for p in pool if p["id"] not in exclude_ids]
        return random.choice(pool) if pool else None

    def sample(self, n: int, **filters) -> List[Dict[str, Any]]:
        pool = self.answerable(**filters)
        if len(pool) <= n:
            random.shuffle(pool)
            return pool
        return random.sample(pool, n)


# Module-level singleton (loaded once)
_repo: Optional[PYQRepository] = None


def get_repository() -> PYQRepository:
    global _repo
    if _repo is None:
        _repo = PYQRepository()
    return _repo
