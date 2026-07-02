"""
knowledge/pyq_repository.py
───────────────────────────
In-memory repository over the PYQ bank. Loaded once at import and reused by
the /api/pyqs, /api/quiz/next and /api/mock/* endpoints.

Two data sources, chosen automatically:
  - knowledge/official/pyqs/cleaned/*.json  (preferred, once the Gemini
    cleaning pipeline in scripts/gemini/ has published a verified bank)
  - knowledge/official/pyqs/parsed/*.json   (pre-migration fallback — raw,
    regex-extracted, unverified questions; ~754 small files)

Each PYQ record looks like:
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

from core.subject_map import PREFIX_SUBJECT, SUBJECT_KEYWORDS

logger = logging.getLogger(__name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")
CLEANED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "cleaned")


def subject_for(concept_id: Optional[str], question_text: str = "") -> str:
    """Derive a subject from concept_id prefix, else keyword-match the text.

    Only used for the pre-migration `parsed/` fallback path — the cleaned
    bank always carries a verified subject from the Gemini agent.
    """
    if concept_id and concept_id != "GENERAL":
        prefix = concept_id.split("_")[0].upper()
        if prefix in PREFIX_SUBJECT:
            return PREFIX_SUBJECT[prefix]
    low = (question_text or "").lower()
    for kw, subj in SUBJECT_KEYWORDS:
        if kw in low:
            return subj
    return "General"


# Obvious extraction-failure markers (PDF math flattening / bad question splits).
_MANGLE = re.compile(r"(P−→|−→\s*\d|∑|∫|\bi=1\b|d\s*ensity|^\W*$)")
_STUB = {"the", "let", "if", "a", "an", "consider", "suppose"}


def _quality(rec) -> str:
    """Classify a parsed PYQ as 'ok' or 'low' so junk can be hidden."""
    t = (rec.get("question_text") or "").strip()
    if len(t) < 40:
        return "low"
    if t.lower().rstrip(".") in _STUB:
        return "low"
    # An MCQ with fewer than 2 options never parsed correctly.
    if rec.get("question_type") == "MCQ" and len(rec.get("options") or {}) < 2:
        return "low"
    # Heavy math-mangling + very short body = unusable.
    if _MANGLE.search(t) and len(t) < 80:
        return "low"
    return "ok"


class PYQRepository:
    """Loads and queries the PYQ bank (cleaned/ if published, else parsed/)."""

    def __init__(self, parsed_dir: str = PARSED_DIR, cleaned_dir: str = CLEANED_DIR):
        self.parsed_dir = parsed_dir
        self.cleaned_dir = cleaned_dir
        self._items: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self.source = "parsed"
        self._load()

    def _cleaned_files(self) -> List[str]:
        return sorted(
            p for p in glob.glob(os.path.join(self.cleaned_dir, "*.json"))
            if os.path.basename(p) != "_manifest.json"
        )

    def _load(self):
        cleaned_files = self._cleaned_files()
        if cleaned_files:
            self.source = "cleaned"
            self._load_cleaned(cleaned_files)
        else:
            self.source = "parsed"
            self._load_parsed()
        logger.info(
            f"PYQRepository loaded {len(self._items)} questions from '{self.source}' "
            f"({sum(i['has_answer'] for i in self._items)} answerable, "
            f"{sum(i['has_solution'] for i in self._items)} with solutions)."
        )

    def _load_cleaned(self, files: List[str]):
        """Load the Gemini-verified bank. Subject comes straight from the
        file — no keyword guessing — and `explanation` is exposed as
        `solution` so existing endpoints/frontend fields keep working."""
        for path in files:
            try:
                with open(path, encoding="utf-8") as f:
                    rec = json.load(f)
            except Exception as e:
                logger.warning(f"Skipping unreadable cleaned PYQ {path}: {e}")
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            rec["id"] = rec.get("id") or stem
            rec["solution"] = rec.get("explanation")
            rec["has_answer"] = bool(rec.get("answer"))
            rec["has_solution"] = bool(rec.get("solution"))
            rec["answer_verified"] = bool(rec.get("answer_verified"))
            rec["quality"] = "ok"
            self._items.append(rec)
            self._by_id[rec["id"]] = rec

    def _load_parsed(self):
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
            rec["answer_verified"] = False
            rec["quality"] = _quality(rec)
            self._items.append(rec)
            self._by_id[stem] = rec

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
            "good": sum(1 for i in self._items if i["quality"] == "ok"),
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
        quality: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ql = (q or "").strip().lower()
        out = []
        for it in self._items:
            if quality and it.get("quality") != quality:
                continue
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
        filters.setdefault("quality", "ok")  # never serve junk to quiz/mock
        pool = self.filter(**filters)
        if self.source == "cleaned":
            verified = [p for p in pool if p.get("answer_verified")]
            if len(verified) >= 10:
                return verified
        return pool

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
