"""
scripts/gemini/validate_notes.py
───────────────────────────────────
Pure Python (NO LLM/API calls). Validates knowledge/notes/*.md written by the
study-notes agent (PLAN_DATA_FIX.md PART 1 Prompt B) against the required
structure, then lists any concept_id still missing a notes file.
"""

import os
import re
import sys
import glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core.syllabus_data import GATE_DA_SYLLABUS

NOTES_DIR = os.path.join(ROOT, "knowledge", "notes")

REQUIRED_HEADINGS = [
    "Core Idea",
    "Key Definitions & Formulas",
    "Worked Example",
    "Common Mistakes & Exam Traps",
    "GATE Pattern Notes",
    "Quick Revision Box",
]

MIN_WORDS, MAX_WORDS = 500, 1600
MIN_FORMULA_LATEX = 3

REFUSAL_MARKERS = [
    "as an ai", "i cannot help", "i can't help", "i'm sorry, but",
    "i am unable to", "i cannot fulfill", "i cannot provide", "i can not provide",
    "as a language model", "i'm not able to",
]

_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
_LATEX_RE = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.DOTALL)


def _heading_positions(text: str) -> dict:
    positions = {}
    for m in _HEADING_RE.finditer(text):
        title = m.group(1).strip()
        positions.setdefault(title, m.start())
    return positions


def _section_text(text: str, heading: str) -> str:
    m = re.search(r"(?m)^##\s+" + re.escape(heading) + r"\s*$", text)
    if not m:
        return ""
    start = m.end()
    rest = text[start:]
    next_m = re.search(r"(?m)^##\s+", rest)
    end = start + next_m.start() if next_m else len(text)
    return text[start:end]


def validate_file(text: str) -> list:
    reasons = []

    positions = _heading_positions(text)
    missing = [h for h in REQUIRED_HEADINGS if h not in positions]
    if missing:
        reasons.append(f"missing_headings:{missing}")
    else:
        ordered = sorted(REQUIRED_HEADINGS, key=lambda h: positions[h])
        if ordered != REQUIRED_HEADINGS:
            reasons.append("headings_out_of_order")

    word_count = len(re.findall(r"\S+", text))
    if not (MIN_WORDS <= word_count <= MAX_WORDS):
        reasons.append(f"word_count_out_of_range:{word_count}")

    if text.count("$") % 2 != 0:
        reasons.append("unbalanced_latex_dollar")

    formulas_section = _section_text(text, "Key Definitions & Formulas")
    latex_count = len(_LATEX_RE.findall(formulas_section))
    if latex_count < MIN_FORMULA_LATEX:
        reasons.append(f"too_few_latex_in_formulas_section:{latex_count}")

    low = text.lower()
    for marker in REFUSAL_MARKERS:
        if marker in low:
            reasons.append(f"refusal_string_detected:'{marker}'")
            break

    return reasons


def main():
    os.makedirs(NOTES_DIR, exist_ok=True)
    all_ids = {c["concept_id"] for c in GATE_DA_SYLLABUS}
    files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")))
    present_ids = {os.path.splitext(os.path.basename(f))[0] for f in files}

    passing, failing = 0, []
    for path in files:
        cid = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            text = f.read()
        reasons = validate_file(text)
        if reasons:
            failing.append((cid, reasons))
        else:
            passing += 1

    missing_ids = sorted(all_ids - present_ids)

    print(f"Checked {len(files)} note file(s) against {len(all_ids)} syllabus concepts: "
          f"{passing} pass, {len(failing)} fail.")

    if failing:
        print("\nFailing files:")
        for cid, reasons in failing:
            print(f"  - {cid}: {'; '.join(reasons)}")

    if missing_ids:
        print(f"\nMissing notes for {len(missing_ids)} concept_id(s):")
        for cid in missing_ids:
            print(f"  - {cid}")
    else:
        print("\nAll concept_ids have a notes file.")


if __name__ == "__main__":
    main()
