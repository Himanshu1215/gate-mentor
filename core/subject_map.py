"""
core/subject_map.py
────────────────────
Single source of truth for concept_id-prefix -> subject mapping, replacing the
duplicated PREFIX_SUBJECT dicts in knowledge/pyq_repository.py and
presentation/api.py.

SUBJECT_KEYWORDS is used ONLY to classify free-text chat queries into a
subject for RAG retrieval filtering — never to guess a PYQ's display subject
(that must come from a real, verified concept_id).
"""

from core.syllabus_data import GATE_DA_SYLLABUS

# concept_id prefix -> subject
PREFIX_SUBJECT = {
    "PROB": "Probability and Statistics",
    "LA": "Linear Algebra",
    "CALC": "Calculus and Optimization",
    "DSA": "Programming, DS & Algorithms",
    "DB": "Database Management and Warehousing",
    "ML": "Machine Learning",
    "AI": "Artificial Intelligence",
    "GA": "General Aptitude",
}

# Keyword -> subject, used ONLY for classifying chat/RAG queries.
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

# Every concept_id defined in the syllabus — the only IDs a cleaned PYQ or a
# study note may legally be tagged with.
VALID_CONCEPT_IDS = {c["concept_id"] for c in GATE_DA_SYLLABUS}


def subject_for_concept(concept_id):
    """Look up the syllabus subject for a concept_id prefix, or None."""
    if not concept_id:
        return None
    prefix = concept_id.split("_")[0].upper()
    return PREFIX_SUBJECT.get(prefix)


def classify_query_subject(text):
    """Best-effort subject guess for a free-text chat query, or None."""
    low = (text or "").lower()
    for kw, subj in SUBJECT_KEYWORDS:
        if kw in low:
            return subj
    return None
