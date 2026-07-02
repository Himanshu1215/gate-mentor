"""
scripts/gemini/export_concepts.py
────────────────────────────────────
Pure Python (NO LLM/API calls). Dumps work/concepts.json — the full GATE DA
syllabus list — for the study-notes-writing agent (PLAN_DATA_FIX.md PART 1
Prompt B) to iterate over.
"""

import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core.syllabus_data import GATE_DA_SYLLABUS

WORK_DIR = os.path.join(ROOT, "work")
OUT_FILE = os.path.join(WORK_DIR, "concepts.json")


def export_concepts():
    os.makedirs(WORK_DIR, exist_ok=True)
    concepts = [
        {
            "concept_id": c["concept_id"],
            "subject": c["subject"],
            "topic": c["topic"],
            "subtopic": c["subtopic"],
            "prerequisites": c["prerequisites"],
            "difficulty": c["difficulty"],
        }
        for c in GATE_DA_SYLLABUS
    ]
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(concepts, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(concepts)} concepts -> {OUT_FILE}")


if __name__ == "__main__":
    export_concepts()
