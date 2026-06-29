"""
train/build_dataset.py
──────────────────────
Build a chat-format instruction dataset for fine-tuning Phi-4-mini from the
structured GATE PYQ JSON files.

This runs on the CPU VM (no GPU needed) and produces the only inputs the GPU VM
needs: train/data/train.jsonl + train/data/val.jsonl.

Each line is one example:
    {"messages": [
        {"role": "system",    "content": "..."},
        {"role": "user",      "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}

The system/user phrasing mirrors learning/ai_reasoner.py so the fine-tuned model
behaves the way the app actually prompts it. Two example types are generated per
suitable PYQ:
  1. SOLVE  — user poses the MCQ; assistant answers + explains (needs answer+solution).
  2. WRITE  — user asks for a GATE MCQ on a concept; assistant emits the MCQ JSON
              (the exact shape generate_quiz_question() expects).

Usage
-----
    python train/build_dataset.py
    python train/build_dataset.py --pyq-dir knowledge/official/pyqs --val-frac 0.1
"""

import os
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Mirrors the persona/instructions in learning/ai_reasoner.py
SOLVE_SYSTEM = (
    "You are a GATE DA AI Mentor with the persona of a 'Professor'. "
    "Solve the student's multiple-choice question. State the correct option, "
    "then give a concise, precise, GATE-exam-focused explanation of the reasoning."
)
WRITE_SYSTEM = (
    "You are a GATE DA exam question generator. Generate ONE multiple-choice "
    "question in valid JSON with exactly these keys: 'question' (string), "
    "'options' (list of 4 strings like 'A) ...'), 'answer' (single letter "
    "A/B/C/D), 'explanation' (string). Make it GATE-level difficulty. "
    "Output ONLY the JSON object."
)


def load_pyqs(pyq_dir):
    """Load all structured PYQ JSON files (recursively), skipping malformed ones."""
    records = []
    for path in sorted(glob.glob(os.path.join(pyq_dir, "**", "*.json"), recursive=True)):
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
            if isinstance(rec, dict) and rec.get("question_text"):
                records.append(rec)
        except Exception as e:
            logger.warning(f"Skipping {path}: {e}")
    return records


def _options_to_list(options):
    """Normalize options dict {'A': '0.6'} -> ['A) 0.6', ...]."""
    if not options:
        return []
    if isinstance(options, list):
        return options
    return [f"{k}) {v}" for k, v in sorted(options.items())]


def build_examples(rec):
    """Return 0-2 chat examples from one PYQ record."""
    examples = []
    opts = _options_to_list(rec.get("options"))
    q = rec["question_text"].strip()
    answer = rec.get("answer")
    solution = (rec.get("solution") or "").strip()

    # 1. SOLVE example — only if we know the answer.
    if answer:
        user = q if not opts else q + "\n\nOptions:\n" + "\n".join(opts)
        assistant = f"The correct answer is {answer}."
        if solution:
            assistant += f"\n\nExplanation: {solution}"
        examples.append({
            "messages": [
                {"role": "system", "content": SOLVE_SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ]
        })

    # 2. WRITE example — only if the record is a complete MCQ with answer.
    if answer and len(opts) >= 2:
        concept = rec.get("concept_id", "GENERAL")
        mcq_json = json.dumps({
            "question": q,
            "options": opts,
            "answer": answer,
            "explanation": solution or "",
        }, ensure_ascii=False)
        examples.append({
            "messages": [
                {"role": "system", "content": WRITE_SYSTEM},
                {"role": "user", "content": f"Generate a GATE-style MCQ for concept: {concept}"},
                {"role": "assistant", "content": mcq_json},
            ]
        })

    return examples


def main():
    parser = argparse.ArgumentParser(description="Build chat JSONL dataset from PYQ JSON.")
    parser.add_argument("--pyq-dir", default=os.path.join(ROOT, "knowledge", "official", "pyqs"))
    parser.add_argument("--val-frac", type=float, default=0.1)
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()

    records = load_pyqs(args.pyq_dir)
    logger.info(f"Loaded {len(records)} PYQ record(s) from {args.pyq_dir}")

    examples = []
    for rec in records:
        examples.extend(build_examples(rec))

    if not examples:
        logger.error(
            "No training examples produced. PYQ records need an 'answer' (and ideally "
            "'solution'). Fill those in (see scripts/data/parse_pyqs.py review step)."
        )
        sys.exit(1)

    # Deterministic split: every Nth example -> val (reproducible, no RNG).
    step = max(2, int(round(1 / args.val_frac))) if args.val_frac > 0 else 0
    train, val = [], []
    for i, ex in enumerate(examples):
        (val if step and i % step == 0 else train).append(ex)

    os.makedirs(args.out_dir, exist_ok=True)
    for name, rows in [("train.jsonl", train), ("val.jsonl", val)]:
        path = os.path.join(args.out_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info(f"Wrote {len(rows)} examples -> {path}")

    logger.info(
        f"Done. {len(train)} train / {len(val)} val from {len(records)} PYQs. "
        "Copy the train/ folder to the GPU VM next."
    )


if __name__ == "__main__":
    main()
