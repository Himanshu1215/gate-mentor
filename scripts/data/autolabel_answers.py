"""
scripts/data/autolabel_answers.py
──────────────────────────────────
Use the local Phi-4-mini model (already running on the VM) to auto-answer
questions that have no answer yet. Writes answers back into the parsed JSON
files in-place.

This is "pseudo-labeling" — ~70-80% accuracy. Good enough to bootstrap more
training examples, not good enough to trust for real exam prep.

Run this ON THE VM where the model is downloaded.

Usage
-----
    python scripts/data/autolabel_answers.py                    # all unanswered
    python scripts/data/autolabel_answers.py --prefix gate_stat # only STAT
    python scripts/data/autolabel_answers.py --dry-run          # preview only
"""

import os
import re
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")
MODEL_FILE = os.path.join(ROOT, "models", "llm", "phi-4-mini-instruct-q4_k_m.gguf")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a GATE exam expert. Answer the multiple-choice question by returning "
    "ONLY the letter of the correct option: A, B, C, or D. "
    "For numerical answer type (NAT) questions with no options, return only the number. "
    "Do not explain. Return exactly one token."
)


def build_prompt(rec):
    q = rec["question_text"]
    opts = rec.get("options") or {}
    if opts:
        opt_str = "\n".join(f"{k}) {v}" for k, v in sorted(opts.items()))
        return f"{q}\n\n{opt_str}"
    return q


def extract_answer(raw, has_options):
    raw = raw.strip()
    if has_options:
        m = re.search(r"\b([A-Da-d])\b", raw)
        return m.group(1).upper() if m else None
    m = re.search(r"-?\d+(?:\.\d+)?", raw)
    return m.group(0) if m else None


def main():
    parser = argparse.ArgumentParser(description="Auto-label unanswered parsed PYQs using local LLM.")
    parser.add_argument("--prefix", default="", help="Only process files with this prefix (e.g. gate_stat)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done, don't write")
    parser.add_argument("--limit", type=int, default=0, help="Max questions to label (0 = all)")
    args = parser.parse_args()

    if not os.path.exists(MODEL_FILE):
        logger.error(f"Model not found at {MODEL_FILE}. Run scripts/download_models.py first.")
        sys.exit(1)

    try:
        from llama_cpp import Llama
    except ImportError:
        logger.error("llama-cpp-python not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    logger.info("Loading local LLM (this takes ~30s)...")
    llm = Llama(model_path=MODEL_FILE, n_ctx=2048, n_threads=4, n_batch=256, verbose=False)
    logger.info("Model ready.")

    pattern = os.path.join(PARSED_DIR, f"{args.prefix}*.json")
    files = sorted(glob.glob(pattern))
    unanswered = [f for f in files
                  if not json.load(open(f, encoding="utf-8")).get("answer")]
    logger.info(f"Found {len(unanswered)} unanswered questions (of {len(files)} total).")

    if args.limit:
        unanswered = unanswered[:args.limit]
        logger.info(f"Limiting to {args.limit}.")

    labelled = 0
    for path in unanswered:
        rec = json.load(open(path, encoding="utf-8"))
        if not rec.get("question_text"):
            continue

        prompt = (
            f"<|system|>\n{SYSTEM}<|end|>\n"
            f"<|user|>\n{build_prompt(rec)}<|end|>\n"
            f"<|assistant|>\n"
        )
        try:
            out = llm(prompt, max_tokens=10, temperature=0.0, stop=["<|end|>", "\n"], echo=False)
            raw = out["choices"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"LLM error on {os.path.basename(path)}: {e}")
            continue

        has_options = bool(rec.get("options"))
        answer = extract_answer(raw, has_options)
        if not answer:
            logger.warning(f"No answer parsed from '{raw}' for {os.path.basename(path)}")
            continue

        logger.info(f"{'[DRY]' if args.dry_run else '[SET]'} {os.path.basename(path)} -> {answer}  (raw: '{raw}')")
        if not args.dry_run:
            rec["answer"] = answer
            rec["answer_source"] = "autolabel_phi4"  # marks pseudo-labels for future review
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)
        labelled += 1

    logger.info(f"Done. {'Would label' if args.dry_run else 'Labelled'} {labelled} questions.")
    if not args.dry_run and labelled:
        logger.info("Re-run train/build_dataset.py to include these in the training set.")


if __name__ == "__main__":
    main()
