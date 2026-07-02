"""
scripts/gemini/validate_pyqs.py
─────────────────────────────────
Pure-Python (NO LLM/API calls) validator + publisher for the Gemini agent's
work/pyq_cleaned/batch_NNN.json output (see scripts/gemini/clean_pyqs.py and
PLAN_DATA_FIX.md PART 1 Prompt A).

--check-only : validate every batch, print rejected ids + reasons, exit.
--publish    : validate, then write one JSON file per accepted question to
               knowledge/official/pyqs/cleaned/{id}.json plus a _manifest.json
               summary, and print the kept/dropped/rejected/unverified histogram.
"""

import os
import re
import sys
import json
import glob
import argparse
import logging
from typing import Optional, Dict, Literal, List
from collections import Counter

from pydantic import BaseModel, ValidationError, model_validator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core.subject_map import VALID_CONCEPT_IDS, PREFIX_SUBJECT

WORK_DIR = os.path.join(ROOT, "work")
CLEANED_BATCHES_DIR = os.path.join(WORK_DIR, "pyq_cleaned")
PUBLISH_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "cleaned")
MANIFEST_FILE = os.path.join(PUBLISH_DIR, "_manifest.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_MANGLE_MARKERS = re.compile(r"(−→|(?<![A-Za-z0-9_])i=1(?![A-Za-z0-9_]))")


class CleanedPYQ(BaseModel):
    id: str
    status: Literal["ok", "drop"]
    drop_reason: Optional[str] = None
    exam: Optional[str] = None
    year: Optional[int] = None
    question_type: Optional[Literal["MCQ", "MSQ", "NAT"]] = None
    marks: Optional[int] = None
    question_text: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    answer: Optional[str] = None
    answer_verified: Optional[bool] = None
    explanation: Optional[str] = None
    concept_id: Optional[str] = None
    subject: Optional[str] = None
    difficulty: Optional[int] = None
    source: Optional[str] = None

    @model_validator(mode="after")
    def _required_by_status(self):
        if self.status == "drop":
            if not self.drop_reason:
                raise ValueError("status=drop requires drop_reason")
        else:
            missing = [
                f for f in ("question_text", "question_type", "concept_id", "subject", "source")
                if not getattr(self, f)
            ]
            if missing:
                raise ValueError(f"status=ok missing required field(s): {missing}")
        return self


def semantic_errors(rec: CleanedPYQ) -> List[str]:
    """Cross-field / cross-reference checks pydantic alone can't express."""
    errors = []
    text = rec.question_text or ""

    if len(text) < 30:
        errors.append("question_text_too_short")

    if rec.concept_id not in VALID_CONCEPT_IDS:
        errors.append(f"invalid_concept_id:{rec.concept_id}")
    else:
        prefix = rec.concept_id.split("_")[0].upper()
        expected_subject = PREFIX_SUBJECT.get(prefix)
        if expected_subject and rec.subject != expected_subject:
            errors.append(f"subject_mismatch: expected '{expected_subject}' got '{rec.subject}'")

    options = rec.options or {}
    if rec.question_type == "MCQ":
        if rec.answer and rec.answer.strip().upper() not in options:
            errors.append(f"mcq_answer_not_in_options:{rec.answer}")
    elif rec.question_type == "MSQ":
        if rec.answer:
            letters = [l.strip().upper() for l in rec.answer.split(";") if l.strip()]
            if not letters or any(l not in options for l in letters):
                errors.append(f"msq_answer_invalid:{rec.answer}")
    elif rec.question_type == "NAT":
        if rec.answer and not _is_numeric_or_range(rec.answer):
            errors.append(f"nat_answer_non_numeric:{rec.answer}")

    combined = text + " " + (rec.explanation or "")
    if combined.count("$") % 2 != 0:
        errors.append("unbalanced_latex_dollar")

    if rec.answer and not (rec.explanation or "").strip():
        errors.append("explanation_empty_with_answer_set")

    if _MANGLE_MARKERS.search(text):
        errors.append("mangled_text")

    return errors


def _is_numeric_or_range(answer: str) -> bool:
    a = answer.strip()
    try:
        float(a)
        return True
    except ValueError:
        pass
    m = re.match(r"^-?\d+(\.\d+)?\s*(?:to|-|–)\s*-?\d+(\.\d+)?$", a)
    return bool(m)


def _iter_cleaned_items():
    """Yields (batch_file, raw_index, raw_dict) for every item across all batches."""
    files = sorted(glob.glob(os.path.join(CLEANED_BATCHES_DIR, "*.json")))
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            logger.error(f"Could not read {path}: {e}")
            continue
        if not isinstance(items, list):
            logger.error(f"{path} does not contain a JSON array — skipping")
            continue
        for i, raw in enumerate(items):
            yield path, i, raw


def validate_all():
    """Runs schema + semantic validation over every cleaned batch item.

    Returns (accepted: list[CleanedPYQ], dropped: list[dict], rejected: list[dict])
    """
    accepted, dropped, rejected = [], [], []

    for path, i, raw in _iter_cleaned_items():
        raw_id = raw.get("id", f"{os.path.basename(path)}[{i}]") if isinstance(raw, dict) else f"{os.path.basename(path)}[{i}]"
        try:
            rec = CleanedPYQ.model_validate(raw)
        except ValidationError as e:
            rejected.append({"id": raw_id, "reasons": [str(e)]})
            continue

        if rec.status == "drop":
            dropped.append({"id": rec.id, "reason": rec.drop_reason})
            continue

        errors = semantic_errors(rec)
        if errors:
            rejected.append({"id": rec.id, "reasons": errors})
            continue

        accepted.append(rec)

    return accepted, dropped, rejected


def _print_report(accepted, dropped, rejected, verb):
    unverified = [r for r in accepted if not r.answer_verified]
    total = len(accepted) + len(dropped) + len(rejected)
    print(f"\n=== validate_pyqs.py --{verb} ===")
    print(f"Processed: {total}")
    print(f"  Kept:      {len(accepted)}")
    print(f"  Dropped:   {len(dropped)}  (agent-flagged unrecoverable)")
    print(f"  Rejected:  {len(rejected)}  (schema/semantic failures — fix and re-run)")
    print(f"  Unverified within kept: {len(unverified)}")
    if rejected:
        print("\nRejected items:")
        for r in rejected:
            print(f"  - {r['id']}: {'; '.join(r['reasons'])}")


def cmd_check_only():
    accepted, dropped, rejected = validate_all()
    _print_report(accepted, dropped, rejected, "check-only")


def cmd_publish():
    accepted, dropped, rejected = validate_all()
    _print_report(accepted, dropped, rejected, "publish")

    if rejected:
        print("\nRefusing to publish while rejected items remain. Fix them and re-run --check-only first.")
        return

    os.makedirs(PUBLISH_DIR, exist_ok=True)
    # Clear any stale published files from a previous run so removed/renamed
    # questions don't linger.
    for stale in glob.glob(os.path.join(PUBLISH_DIR, "*.json")):
        if os.path.basename(stale) != "_manifest.json":
            os.remove(stale)

    by_subject = Counter()
    by_concept = Counter()
    by_year = Counter()

    for rec in accepted:
        out_path = os.path.join(PUBLISH_DIR, f"{rec.id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rec.model_dump(exclude={"status", "drop_reason"}), f, indent=2, ensure_ascii=False)
        by_subject[rec.subject] += 1
        by_concept[rec.concept_id] += 1
        if rec.year:
            by_year[str(rec.year)] += 1

    manifest = {
        "total_kept": len(accepted),
        "total_dropped": len(dropped),
        "total_rejected": len(rejected),
        "total_unverified": sum(1 for r in accepted if not r.answer_verified),
        "by_subject": dict(by_subject),
        "by_concept": dict(by_concept),
        "by_year": dict(by_year),
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nPublished {len(accepted)} question(s) -> {PUBLISH_DIR}")
    print(f"Manifest -> {MANIFEST_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Validate/publish Gemini-cleaned PYQ batches (no LLM calls here).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-only", action="store_true")
    group.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    if args.check_only:
        cmd_check_only()
    elif args.publish:
        cmd_publish()


if __name__ == "__main__":
    main()
