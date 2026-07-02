"""
scripts/gemini/clean_pyqs.py
─────────────────────────────
Pure-Python (NO LLM/API calls) export step for the PYQ-bank cleaning pipeline.

--export-only:
    1. Loads every knowledge/official/pyqs/parsed/*.json record.
    2. Hard-drops unrecoverable junk (too-short text, unusable MCQs, exact
       duplicates) and logs each drop to work/dropped.jsonl.
    3. For every survivor, locates a best-effort raw-text context window
       around its question number in the original source .txt, to help a
       downstream LLM agent reconstruct/verify the question.
    4. Writes survivors in batches of 8 to work/pyq_batches/batch_NNN.json.
    5. Renders work/concept_table.md (concept_id | subject | topic | subtopic)
       from core.syllabus_data, for the LLM agent to pick valid concept_ids from.

A separate agent (not this script) reads the batches, reconstructs/solves each
question, and writes work/pyq_cleaned/batch_NNN.json for validate_pyqs.py.
"""

import os
import re
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core.syllabus_data import GATE_DA_SYLLABUS

PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")
SOURCE_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs")
WORK_DIR = os.path.join(ROOT, "work")
BATCHES_DIR = os.path.join(WORK_DIR, "pyq_batches")
DROPPED_FILE = os.path.join(WORK_DIR, "dropped.jsonl")
CONCEPT_TABLE_FILE = os.path.join(WORK_DIR, "concept_table.md")

BATCH_SIZE = 8

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Matches an embedded option marker like "(A)", "(a)", "A)" appearing inline
# in already-parsed question text — used to decide whether an MCQ with too
# few structured options might still be recoverable by an LLM re-read.
_EMBEDDED_OPTION = re.compile(r"\(?[A-Da-d]\)\s*\S")

# Suffix pattern that parse_pyqs.py appends to the source stem:
# "<stem>_<seq4>_q<num3>.json"
_SEQ_SUFFIX = re.compile(r"_\d{4}_q\d{3}$")


def _source_stem(parsed_stem: str) -> str:
    return _SEQ_SUFFIX.sub("", parsed_stem)


def _normalize_for_hash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _hard_drop_reason(rec: dict, seen_hashes: set) -> str:
    """Returns a drop reason string, or '' if the record should survive."""
    text = (rec.get("question_text") or "").strip()
    if len(text) < 25:
        return "text_too_short"

    if rec.get("question_type") == "MCQ":
        n_options = len(rec.get("options") or {})
        if n_options <= 1 and not _EMBEDDED_OPTION.search(text):
            return "mcq_no_recoverable_options"

    norm = _normalize_for_hash(text)
    if norm:
        if norm in seen_hashes:
            return "duplicate_text"
        seen_hashes.add(norm)

    return ""


def _find_context_window(raw_text: str, question_id: str, seq_index: int, total_in_file: int, window: int = 2200) -> str:
    """Best-effort raw-text window around a question number.

    Numbers repeat across exam sections (GA restarts at 1, subject section
    restarts at 1), so among all textual matches for the number we pick the
    one whose position in the file is proportionally closest to where this
    question falls in its file's sequence. Falls back to a proportional
    slice if no header pattern matches at all.
    """
    if not raw_text:
        return ""

    num_match = re.search(r"\d+", question_id or "")
    num = num_match.group(0) if num_match else None
    text_len = len(raw_text)
    target_frac = (seq_index / total_in_file) if total_in_file else 0.0

    if num:
        pattern = re.compile(
            r"(?:^|\n)\s*\(?Q\.?\s*" + re.escape(num) + r"\b|(?:^|\n)\s*" + re.escape(num) + r"\s*[.)]\s",
            re.IGNORECASE,
        )
        matches = [m.start() for m in pattern.finditer(raw_text)]
        if matches:
            best = min(matches, key=lambda i: abs(i / text_len - target_frac))
            return raw_text[best: best + window].strip()

    start = max(0, int(target_frac * text_len) - 200)
    return raw_text[start: start + window].strip()


def export_batches():
    os.makedirs(BATCHES_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)

    parsed_files = sorted(glob.glob(os.path.join(PARSED_DIR, "*.json")))
    logger.info(f"Loaded {len(parsed_files)} parsed PYQ files from {PARSED_DIR}")

    # Group by source stem so context-window lookups stay within one raw file
    # and the proportional-position heuristic is meaningful.
    by_source: dict = {}
    for path in parsed_files:
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
        except Exception as e:
            logger.warning(f"Skipping unreadable {path}: {e}")
            continue
        rec["_id"] = stem
        src_stem = _source_stem(stem)
        by_source.setdefault(src_stem, []).append(rec)

    survivors = []
    dropped = []
    seen_hashes = set()

    raw_text_cache: dict = {}

    for src_stem, recs in by_source.items():
        recs.sort(key=lambda r: r.get("question_seq") or 0)
        txt_path = os.path.join(SOURCE_DIR, src_stem + ".txt")
        pdf_path = os.path.join(SOURCE_DIR, src_stem + ".pdf")
        if txt_path not in raw_text_cache:
            if os.path.exists(txt_path):
                with open(txt_path, encoding="utf-8", errors="replace") as f:
                    raw_text_cache[txt_path] = f.read()
            else:
                raw_text_cache[txt_path] = ""
        raw_text = raw_text_cache[txt_path]
        total = len(recs)

        for i, rec in enumerate(recs):
            reason = _hard_drop_reason(rec, seen_hashes)
            if reason:
                dropped.append({"id": rec["_id"], "reason": reason})
                continue

            context = _find_context_window(raw_text, rec.get("question_id"), i, total)
            survivors.append({
                "id": rec["_id"],
                "parsed_text": rec.get("question_text", ""),
                "options_raw": rec.get("options"),
                "answer_hint": rec.get("answer"),
                "solution_hint": rec.get("solution"),
                "source_pdf": os.path.basename(pdf_path) if os.path.exists(pdf_path) else None,
                "source_txt": os.path.basename(txt_path) if os.path.exists(txt_path) else None,
                "question_seq": rec.get("question_seq"),
                "context_window": context,
            })

    with open(DROPPED_FILE, "w", encoding="utf-8") as f:
        for d in dropped:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    survivors.sort(key=lambda r: (r.get("source_txt") or "", r.get("question_seq") or 0))
    n_batches = 0
    for i in range(0, len(survivors), BATCH_SIZE):
        batch = survivors[i: i + BATCH_SIZE]
        n_batches += 1
        out_path = os.path.join(BATCHES_DIR, f"batch_{n_batches:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

    _write_concept_table()

    logger.info(
        f"Exported {len(survivors)} survivors into {n_batches} batch file(s) in {BATCHES_DIR}\n"
        f"Hard-dropped {len(dropped)} record(s) -> {DROPPED_FILE}\n"
        f"Concept table -> {CONCEPT_TABLE_FILE}"
    )


def _write_concept_table():
    lines = ["| concept_id | subject | topic | subtopic |", "|---|---|---|---|"]
    for c in GATE_DA_SYLLABUS:
        lines.append(f"| {c['concept_id']} | {c['subject']} | {c['topic']} | {c['subtopic']} |")
    with open(CONCEPT_TABLE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Export PYQ batches for LLM cleaning (no LLM calls here).")
    parser.add_argument("--export-only", action="store_true", required=True,
                        help="Triage parsed/*.json and write work/pyq_batches/ + work/concept_table.md")
    args = parser.parse_args()

    if args.export_only:
        export_batches()


if __name__ == "__main__":
    main()
