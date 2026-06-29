"""
scripts/data/scrape_webpage_pyqs.py
────────────────────────────────────
Scrape GATE PYQ questions + solutions from a webpage (collegedunia, testbook,
byju's, etc.) and convert them to the same structured JSON schema as the PDF
parser.

Uses Selenium with a real Chrome browser so the site sees a real user visit,
not a bot. Alternatively works with a saved HTML file (pass --html).

Install:
    pip install selenium webdriver-manager beautifulsoup4
    # Chrome must be installed on your system

Usage
-----
    # Scrape live URL (opens Chrome briefly):
    python scripts/data/scrape_webpage_pyqs.py \
        --url "https://collegedunia.com/articles/e-60-gate-2024-statistics-question-paper" \
        --year 2024 --exam "GATE ST"

    # From a saved HTML file (save the page in browser: Ctrl+S -> Webpage, Complete):
    python scripts/data/scrape_webpage_pyqs.py \
        --html gate_stat_2024.html --year 2024 --exam "GATE ST"

Output: knowledge/official/pyqs/parsed/web_gate_st_2024_NNNN_qXXX.json
Then run: python train/build_dataset.py
"""

import os
import re
import sys
import json
import time
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PARSED_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs", "parsed")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── concept tagging (same as parse_pyqs.py) ──────────────────────────────────
CONCEPT_KEYWORDS = [
    ("naive bayes", "ML_002"), ("bayes", "PROB_003"),
    ("conditional probability", "PROB_002"), ("posterior", "PROB_003"),
    ("principal component", "ML_002"), ("pca", "ML_002"),
    ("linear regression", "ML_001"), ("logistic regression", "ML_001"),
    ("regression", "ML_001"), ("eigenvalue", "LA_002"),
    ("eigenvector", "LA_002"), ("determinant", "LA_002"),
    ("vector space", "LA_001"), ("subspace", "LA_001"),
    ("matrix", "LA_001"), ("random variable", "PROB_001"),
    ("distribution", "PROB_001"), ("probability", "PROB_001"),
]

def tag_concept(text):
    low = text.lower()
    for kw, cid in CONCEPT_KEYWORDS:
        if kw in low:
            return cid
    return "GENERAL"


# ── HTML fetching ─────────────────────────────────────────────────────────────

def fetch_with_selenium(url, wait=5):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        logger.error("Run: pip install selenium webdriver-manager")
        sys.exit(1)

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    logger.info("Launching Chrome (headless)...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=opts
    )
    try:
        driver.get(url)
        time.sleep(wait)  # let JS render
        # scroll to load lazy content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        html = driver.page_source
        logger.info(f"Fetched {len(html):,} chars from {url}")
        return html
    finally:
        driver.quit()


def fetch_from_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


# ── Parsing strategies ────────────────────────────────────────────────────────

def clean(text):
    return " ".join(text.split()).strip()


def parse_html(html, year, exam):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("Run: pip install beautifulsoup4")
        sys.exit(1)

    soup = BeautifulSoup(html, "html.parser")
    records = []

    # Strategy 1: look for numbered question blocks (most sites use divs/sections)
    # Common patterns across edtech sites:
    #   <div class="question">  or  <div class="ques-block">  etc.
    question_containers = (
        soup.find_all(attrs={"class": re.compile(r"question|ques|quest|problem", re.I)})
        or soup.find_all(["li", "div", "section"],
                         string=re.compile(r"Q\.\s*\d+|Question\s+\d+", re.I))
    )

    if question_containers:
        logger.info(f"Strategy 1: found {len(question_containers)} question containers.")
        for i, block in enumerate(question_containers):
            rec = parse_block_html(block, i + 1, year, exam)
            if rec:
                records.append(rec)

    # Strategy 2: fall back to plain text extraction + reuse parse_pyqs logic
    if len(records) < 3:
        logger.info("Strategy 1 yielded few results — falling back to text extraction.")
        text = soup.get_text("\n")
        records = parse_from_text(text, year, exam)

    return records


def parse_block_html(block, seq, year, exam):
    """Extract one question record from a BeautifulSoup tag."""
    from bs4 import BeautifulSoup

    text = block.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines or len(" ".join(lines)) < 20:
        return None

    # Find question number
    qnum_m = re.search(r"Q\.?\s*(\d+)", lines[0], re.I)
    qnum = qnum_m.group(1) if qnum_m else str(seq)

    # Split into question text / options / answer / solution
    full = "\n".join(lines)
    return _extract_record(full, qnum, seq, year, exam)


def parse_from_text(text, year, exam):
    """Reuse the same split logic as parse_pyqs.py but on webpage text."""
    # Import from project
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        from scripts.data.parse_pyqs import split_questions, parse_block, preprocess
        text = preprocess(text)
        blocks = split_questions(text)
        logger.info(f"Text fallback: detected {len(blocks)} question blocks.")
        records = []
        for seq, (num, body) in enumerate(blocks, 1):
            rec = parse_block(num, body, year, {}, seq)
            if rec.get("question_text"):
                rec["exam"] = exam
                records.append(rec)
        return records
    except Exception as e:
        logger.warning(f"Text fallback failed: {e}")
        return []


def _extract_record(text, qnum, seq, year, exam):
    """Extract structured record from raw question text block."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from scripts.data.parse_pyqs import (
        _extract_answer_and_solution, OPTION, MARKS, tag_concept
    )

    text, answer, solution = _extract_answer_and_solution(text)

    options = {}
    for m in OPTION.finditer(text):
        letter = m.group(1).upper()
        options.setdefault(letter, clean(m.group(2)))

    first_opt = OPTION.search(text)
    qtext = clean(text[: first_opt.start()] if first_opt else text)
    # Strip leading "Q.N" from question text
    qtext = re.sub(r"^Q\.?\s*\d+\s*[.:\-]?\s*", "", qtext).strip()

    if not qtext or len(qtext) < 10:
        return None

    marks_m = MARKS.search(text)
    return {
        "year": year,
        "exam": exam,
        "question_id": f"Q{qnum}",
        "question_seq": seq,
        "question_type": "MCQ" if len(options) >= 2 else "NAT",
        "marks": int(marks_m.group(1)) if marks_m else None,
        "difficulty": None,
        "concept_id": tag_concept(qtext),
        "question_text": qtext,
        "options": options if options else None,
        "answer": answer,
        "solution": solution,
    }


# ── Save records ──────────────────────────────────────────────────────────────

def save(records, stem):
    os.makedirs(PARSED_DIR, exist_ok=True)
    saved, with_ans, with_sol = 0, 0, 0
    for rec in records:
        seq = rec.get("question_seq", saved + 1)
        qid = rec.get("question_id", f"Q{seq}")
        path = os.path.join(PARSED_DIR, f"web_{stem}_{seq:04d}_{qid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        saved += 1
        if rec.get("answer"): with_ans += 1
        if rec.get("solution"): with_sol += 1

    logger.info(
        f"Saved {saved} questions to {PARSED_DIR}\n"
        f"  With answer:   {with_ans}/{saved}\n"
        f"  With solution: {with_sol}/{saved}"
    )
    if saved:
        logger.info("Next: python train/build_dataset.py")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape GATE PYQs from a webpage.")
    parser.add_argument("--url", help="Live URL to scrape (needs Chrome + selenium)")
    parser.add_argument("--html", help="Path to locally saved HTML file (Ctrl+S in browser)")
    parser.add_argument("--year", type=int, required=True, help="Exam year")
    parser.add_argument("--exam", default="GATE ST", help="Exam label (e.g. 'GATE ST')")
    parser.add_argument("--stem", default=None, help="Output filename stem (default: auto)")
    parser.add_argument("--wait", type=int, default=5,
                        help="Seconds to wait after page load (for JS rendering)")
    args = parser.parse_args()

    if not args.url and not args.html:
        parser.error("Provide --url or --html")

    if args.html:
        html = fetch_from_file(args.html)
        stem = args.stem or os.path.splitext(os.path.basename(args.html))[0]
    else:
        html = fetch_with_selenium(args.url, wait=args.wait)
        stem = args.stem or f"gate_st_{args.year}"

    records = parse_html(html, args.year, args.exam)
    logger.info(f"Extracted {len(records)} question records.")

    if not records:
        logger.error(
            "No questions extracted. Try:\n"
            "  1. Save the page manually in Chrome (Ctrl+S -> 'Webpage, Complete')\n"
            "  2. Pass the saved file with --html gate_stat_2024.html"
        )
        sys.exit(1)

    save(records, stem)


if __name__ == "__main__":
    main()
