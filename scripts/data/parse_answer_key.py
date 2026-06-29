"""
scripts/data/parse_answer_key.py
─────────────────────────────────
Convert an official GATE answer key (PDF or text) into the JSON format that
parse_pyqs.py --answers expects:

    { "Q1": "B", "Q2": "4.50", "Q3": "A", ... }

Then use it:
    python scripts/data/parse_pyqs.py gate_stat_pyqs.txt --year 2023 \
        --answers knowledge/official/answer_keys/gate_st_2023.json

Sources for official answer keys (free, published by organizing IIT after exam):
    gate2024.iisc.ac.in  →  Answer Keys  →  ST
    gate2023.iitk.ac.in  →  Answer Keys  →  ST
    gate2022.iitb.ac.in  →  Answer Keys  →  ST
    (pattern: gate<year>.<iit-code>.ac.in)

The answer key PDF usually looks like one of these formats:
    Format A (table):   Q.No | Answer
                        1    | B
                        2    | 4.50 to 4.50
    Format B (inline):  1-B  2-C  3-4.5  ...
    Format C (text):    Q1: B  Q2: 4.50  ...

This script handles all three. If it misses some, it prints them so you can
add manually.

Usage
-----
    # Install pymupdf if not already: pip install pymupdf
    python scripts/data/parse_answer_key.py gate_st_2024_answerkey.pdf \
        --out knowledge/official/answer_keys/gate_st_2024.json

    python scripts/data/parse_answer_key.py gate_st_2024_answerkey.txt \
        --out knowledge/official/answer_keys/gate_st_2024.json
"""

import os
import re
import sys
import json
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "knowledge", "official", "answer_keys")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Matches:  "1", "01", "Q1", "Q.1", "Q. 1"
Q_NUM   = re.compile(r"Q\.?\s*(\d{1,3})", re.IGNORECASE)
Q_PLAIN = re.compile(r"^\s*(\d{1,3})\s*$")

# Answer: single letter OR numeric (NAT range "4.50 to 4.50" → take first number)
ANS_LETTER  = re.compile(r"\b([A-Da-d])\b")
ANS_NUMERIC = re.compile(r"(-?\d+(?:\.\d+)?)")
ANS_RANGE   = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:to|–|-)\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def extract_text(path):
    if path.lower().endswith(".pdf"):
        try:
            import fitz
        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install pymupdf")
            sys.exit(1)
        doc = fitz.open(path)
        return "\n".join(page.get_text("text") for page in doc)
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_answer(raw):
    """Return a normalised answer string from a raw cell/token."""
    raw = raw.strip()
    # NAT range: take midpoint or first value
    rng = ANS_RANGE.search(raw)
    if rng:
        lo, hi = float(rng.group(1)), float(rng.group(2))
        mid = (lo + hi) / 2
        return f"{mid:.2f}" if mid != int(mid) else str(int(mid))
    # Single letter
    let = ANS_LETTER.search(raw)
    if let:
        return let.group(1).upper()
    # Numeric
    num = ANS_NUMERIC.search(raw)
    if num:
        return num.group(1)
    return None


def parse_table(text):
    """
    Handle tabular format:
        Q.No  Answer
        1     B
        2     4.50 to 4.50
    """
    answers = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        # Look for a line that is just a question number
        m = Q_NUM.match(line.strip()) or Q_PLAIN.match(line.strip())
        if not m:
            continue
        qnum = int(m.group(1))
        # Answer is on the same line after the number, or on the next non-empty line
        rest = line[m.end():].strip()
        if not rest and i + 1 < len(lines):
            rest = lines[i + 1].strip()
        ans = parse_answer(rest)
        if ans:
            answers[f"Q{qnum}"] = ans
    return answers


def parse_inline(text):
    """
    Handle inline format:  1-B  2-C  3-4.5  Q1:B  Q2:4.50  ...
    """
    answers = {}
    # Pattern: (optional Q)(number)(separator)(answer)
    pattern = re.compile(
        r"Q?\.?\s*(\d{1,3})\s*[-:]\s*([A-Da-d]|\d+(?:\.\d+)?(?:\s*(?:to|–|-)\s*\d+(?:\.\d+)?)?)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        qnum = int(m.group(1))
        ans = parse_answer(m.group(2))
        if ans:
            answers[f"Q{qnum}"] = ans
    return answers


def main():
    parser = argparse.ArgumentParser(description="Parse GATE official answer key into JSON.")
    parser.add_argument("input", help="Answer key PDF or .txt file")
    parser.add_argument("--out", help="Output JSON path (default: answer_keys/<stem>.json)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"File not found: {args.input}")
        sys.exit(1)

    text = extract_text(args.input)
    logger.info(f"Extracted {len(text)} chars from {args.input}")

    # Try table parse first, fall back to inline
    answers = parse_table(text)
    if len(answers) < 5:
        logger.info("Table parse found few answers — trying inline format.")
        answers.update(parse_inline(text))

    if not answers:
        logger.error("Could not parse any answers. Check the file format and report.")
        sys.exit(1)

    logger.info(f"Parsed {len(answers)} answers: {sorted(answers.keys())[:10]} ...")

    os.makedirs(OUT_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.input))[0]
    out = args.out or os.path.join(OUT_DIR, f"{stem}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved -> {out}")
    logger.info(
        f"Now re-run the parser:\n"
        f"  python scripts/data/parse_pyqs.py knowledge/official/pyqs/gate_stat_pyqs.txt "
        f"--year 2024 --answers {out}"
    )


if __name__ == "__main__":
    main()
