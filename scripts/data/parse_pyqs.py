"""
scripts/data/parse_pyqs.py
──────────────────────────
Heuristically parse extracted PYQ text into the structured QA JSON schema used
by knowledge/official/pyqs/gate_2024_bayes.json:

    {
      "year": int, "exam": "GATE DA", "question_id": "Q45",
      "question_type": "MCQ" | "MSQ" | "NAT",
      "marks": int | null, "difficulty": int | null,
      "concept_id": "PROB_003",
      "question_text": "...",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "answer": "A" | null,
      "solution": "..." | null
    }

Input is the cleaned `.txt` produced by scripts/data/collect_pdfs.py (or any raw
text). PDF text is noisy, so this is a FIRST-PASS extractor: every parsed
question is written to knowledge/official/pyqs/parsed/<stem>_qNN.json for a
quick human review. `answer`/`solution` are left null unless an answer-key file
(--answers a.json, mapping question_id -> answer) is supplied.

Usage
-----
    python scripts/data/parse_pyqs.py knowledge/official/pyqs/gate_da_2024.txt --year 2024
    python scripts/data/parse_pyqs.py knowledge/official/pyqs/gate_da_2024.txt \
        --year 2024 --answers knowledge/official/answer_keys/gate_da_2024.json
"""

import os
import re
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Keyword -> concept_id. Keep aligned with scripts/seed_syllabus.py concept_ids.
# Order matters: more specific phrases first.
CONCEPT_KEYWORDS = [
    ("naive bayes",                 "ML_002"),
    ("bayes",                       "PROB_003"),
    ("conditional probability",     "PROB_002"),
    ("posterior",                   "PROB_003"),
    ("principal component",         "ML_002"),   # PCA / dimensionality reduction
    ("pca",                         "ML_002"),
    ("linear regression",           "ML_001"),
    ("logistic regression",         "ML_001"),
    ("regression",                  "ML_001"),
    ("classifier",                  "ML_002"),
    ("classification",              "ML_002"),
    ("eigenvalue",                  "LA_002"),
    ("eigenvector",                 "LA_002"),
    ("determinant",                 "LA_002"),
    ("vector space",                "LA_001"),
    ("subspace",                    "LA_001"),
    ("matrix",                      "LA_001"),
    ("random variable",             "PROB_001"),
    ("distribution",                "PROB_001"),
    ("probability",                 "PROB_001"),
]

# Question header patterns — covers all three observed formats:
#   "Q.45 text"  "Q45."  "Q. 45"  and the official "Q.1\n" (trailing newline)
Q_HEADER = re.compile(
    r"(?:^|\n)\s*Q\.?\s*(\d{1,3})\s*[\).\s]",
    re.IGNORECASE,
)
# Option: handles "(A) text", "A) text", "(a)\ntext" (option letter alone on line)
# Covers uppercase and lowercase a-d/A-D.
OPTION = re.compile(
    r"(?:^|\n)\s*\(?([A-Da-d])\)?\s*[.:\-]?\s*(.+?)(?=\n\s*\(?[A-Da-d]\)?\s*[.:\-]?\s*\S|\Z)",
    re.DOTALL,
)
MARKS = re.compile(r"\b([12])\s*marks?\b", re.IGNORECASE)
# Inline answer/solution — handles "Correct Answer:", "Ans.", "Ans :"
SOLUTION_SPLIT = re.compile(r"\bsolution\s*:", re.IGNORECASE)
ANSWER_SPLIT   = re.compile(
    r"\b(?:correct\s+answer|answer\s+key|ans\.?)\s*:?", re.IGNORECASE
)
ANSWER_LETTER  = re.compile(r"\(?([A-Da-d])\)?", re.IGNORECASE)
ANSWER_NUMERIC = re.compile(r"(-?\d+(?:\.\d+)?(?:\s*(?:to|-|–)\s*-?\d+(?:\.\d+)?)?)")

# Matches a line consisting ONLY of one option letter  e.g. "(A)" or "A)" alone
OPTION_ALONE = re.compile(r"^\s*\(?([A-Da-d])\)?\s*$")


# Page header/footer patterns common in official GATE PDFs and Made Easy books.
_NOISE = re.compile(
    r"(?:organizing institute|made\s*easy|www\.\S+|corporate office|"
    r"page\s+\d+\s+of\s+\d+|ph:\s*\d|delhi\s*\||\bgate\s+20\d\d\b|"
    r"general aptitude\s*\(ga\)|statistics\s*\(st\)|computer science\s*&?\s*(?:it|ai)"
    r"|click here for|scroll down|date of (?:exam|test)\s*:)",
    re.IGNORECASE,
)


# Matches PDF preamble headers before actual questions begin.
_PREAMBLE_END = re.compile(
    r"(?:general aptitude\s*\(ga\)|statistics\s*\(st\)|subject\s*(?:section|questions))",
    re.IGNORECASE,
)
# Matches bare numbered question lines: "1. " at line start (no Q. prefix).
_BARE_NUM = re.compile(r"(?m)^(\d{1,3})\. (?=[A-Z(])")


def preprocess(text):
    """
    Normalise raw PDF text before parsing:
    1. Strip page header/footer noise lines.
    2. Deduplicate consecutive repeated lines (Made Easy PDFs repeat each line 5×).
    3. Join lone option-letter lines with the following line:
         "(A)\nagnostic"  ->  "(A) agnostic"
    4. Strip instruction preamble before General Aptitude / Statistics section.
    5. Normalise bare "1. " question numbering to "Q.1 " so Q_HEADER matches.
    """
    # --- 1. Strip noise lines ---
    lines = text.split("\n")
    lines = [l for l in lines if not _NOISE.search(l)]

    # --- 2. Deduplicate consecutive identical lines ---
    deduped = []
    prev = None
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line

    # --- 3. Join lone option letter with next line ---
    joined = []
    i = 0
    while i < len(deduped):
        line = deduped[i]
        m = OPTION_ALONE.match(line)
        if m and i + 1 < len(deduped):
            next_line = deduped[i + 1].strip()
            if next_line and not OPTION_ALONE.match(deduped[i + 1]):
                joined.append(f"({m.group(1).upper()}) {next_line}")
                i += 2
                continue
        joined.append(line)
        i += 1
    text = "\n".join(joined)

    # --- 4. Strip preamble: keep only text from first GA/ST/Subject section marker ---
    m = _PREAMBLE_END.search(text)
    if m:
        text = text[m.start():]

    # --- 5. Normalise bare numbering "1. " -> "Q.1 " (e.g. official IIT PDFs) ---
    # Only do this when the text has no Q. patterns already.
    if not re.search(r"\bQ\.\s*\d", text, re.IGNORECASE):
        text = _BARE_NUM.sub(r"Q.\1 ", text)

    return text


def tag_concept(text):
    low = text.lower()
    for kw, cid in CONCEPT_KEYWORDS:
        if kw in low:
            return cid
    return "GENERAL"


def split_questions(text):
    """Split the document into (number, body) blocks on question headers."""
    matches = list(Q_HEADER.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((num, text[start:end].strip()))
    return blocks


def _extract_answer_and_solution(body):
    """
    Split a question block into (question_body, answer, solution).
    Handles PDFs that inline 'Correct Answer: B' and 'Solution: ...' after options.
    Returns (cleaned_body, answer_str_or_None, solution_str_or_None).
    """
    answer = None
    solution = None

    # Find 'Solution:' marker first (it comes after the answer).
    sol_m = SOLUTION_SPLIT.search(body)
    if sol_m:
        solution = body[sol_m.end():].strip()
        body = body[:sol_m.start()]

    # Find 'Correct Answer:' / 'Answer Key:' marker.
    ans_m = ANSWER_SPLIT.search(body)
    if ans_m:
        ans_text = body[ans_m.end(): ans_m.end() + 60].strip()
        # MCQ: look for a single letter
        al = ANSWER_LETTER.search(ans_text)
        if al:
            answer = al.group(1).upper()
        else:
            # NAT: numeric answer
            nm = ANSWER_NUMERIC.search(ans_text)
            if nm:
                answer = nm.group(1).strip()
        body = body[:ans_m.start()]

    # Clean trailing noise from option D that spills into the answer line
    if answer:
        for letter in ["D", "C", "B", "A"]:
            # Remove "answer: X" fragment absorbed into option text
            body = re.sub(
                r"(\([A-D]\)|[A-D][).:])\s*" + re.escape(answer) + r"\s*$",
                r"\1", body, flags=re.IGNORECASE
            )

    return body.strip(), answer, solution


def parse_block(num, body, year, answers, seq, exam="GATE DA"):
    """Parse a single question block into the schema dict (best-effort)."""
    # First split out inline answer/solution (common in compiled solution PDFs)
    body, inline_answer, inline_solution = _extract_answer_and_solution(body)

    options = {}
    for om in OPTION.finditer(body):
        letter = om.group(1).upper()  # normalise a->A etc.
        opt_text = " ".join(om.group(2).split())
        options.setdefault(letter, opt_text)

    # Question text = everything before the first option marker.
    first_opt = OPTION.search(body)
    qtext = (body[: first_opt.start()] if first_opt else body).strip()
    qtext = " ".join(qtext.split())

    qtype = "MCQ" if len(options) >= 2 else "NAT"
    marks_m = MARKS.search(body)
    qid = f"Q{num}"

    # Priority: answer-key file > inline extraction
    final_answer = answers.get(qid) or inline_answer

    return {
        "year": year,
        "exam": exam,
        "question_id": qid,
        "question_seq": seq,   # global sequence — unique even across multi-year PDFs
        "question_type": qtype,
        "marks": int(marks_m.group(1)) if marks_m else None,
        "difficulty": None,
        "concept_id": tag_concept(qtext),
        "question_text": qtext,
        "options": options if options else None,
        "answer": final_answer,
        "solution": inline_solution,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse PYQ text into structured QA JSON.")
    parser.add_argument("inputs", nargs="+", help=".txt file(s) of extracted PYQ text")
    parser.add_argument("--year", type=int, required=True, help="Exam year")
    parser.add_argument("--exam", default="GATE DA", help="Exam label (e.g. 'GATE ST', 'GATE DA')")
    parser.add_argument("--answers", help="Optional JSON file: {question_id: answer_letter}")
    args = parser.parse_args()

    answers = {}
    if args.answers:
        with open(args.answers, encoding="utf-8") as f:
            answers = json.load(f)
        logger.info(f"Loaded {len(answers)} answers from {args.answers}")

    files = []
    for inp in args.inputs:
        files.extend(glob.glob(inp))
    if not files:
        logger.error("No input files matched.")
        sys.exit(1)

    os.makedirs(PARSED_DIR, exist_ok=True)
    total = 0
    with_answer = 0
    with_solution = 0
    global_seq = 0  # monotonically increasing — prevents filename collisions in multi-year PDFs

    for path in files:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        text = preprocess(text)
        stem = os.path.splitext(os.path.basename(path))[0]
        blocks = split_questions(text)
        logger.info(f"{path}: detected {len(blocks)} question block(s).")

        for num, body in blocks:
            global_seq += 1
            rec = parse_block(num, body, args.year, answers, global_seq, exam=args.exam)
            if not rec["question_text"]:
                global_seq -= 1
                continue
            # Use global_seq in filename so multi-year PDFs never overwrite each other
            out = os.path.join(PARSED_DIR, f"{stem}_{global_seq:04d}_q{num.zfill(3)}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2, ensure_ascii=False)
            total += 1
            if rec["answer"]:
                with_answer += 1
            if rec["solution"]:
                with_solution += 1

    logger.info(
        f"Wrote {total} question file(s) to {PARSED_DIR}\n"
        f"  With answer:   {with_answer}/{total}\n"
        f"  With solution: {with_solution}/{total}\n"
        "Review a sample before building the training dataset."
    )


if __name__ == "__main__":
    main()
