"""
scripts/data/collect_pdfs.py
────────────────────────────
Extract clean text from PYQ / textbook PDFs and (optionally) ingest the result
into the RAG vector store.

Workflow
--------
1. Drop PDFs into the knowledge tree, e.g.:
     knowledge/official/pyqs/gate_da_2024.pdf
     knowledge/textbooks/linear_algebra/strang.pdf
2. Run this script. For each PDF it writes a sibling cleaned-text file
   (`<name>.txt`) next to the PDF so you can eyeball / hand-correct it before
   it ever reaches the model.
3. Pass --ingest to push the extracted text straight into ChromaDB via the
   existing KnowledgeIngestor pipeline (no duplicated extraction logic).

This reuses knowledge/ingestion.KnowledgeIngestor.extract_text_from_pdf() — the
same PyMuPDF + page-number/short-line cleaning used everywhere else.

Usage
-----
    python scripts/data/collect_pdfs.py                       # extract all PDFs -> .txt
    python scripts/data/collect_pdfs.py --ingest              # extract + ingest to RAG
    python scripts/data/collect_pdfs.py path/to/one.pdf       # single file
    python scripts/data/collect_pdfs.py --concept LA_001 ...  # tag concept on ingest
"""

import os
import sys
import glob
import argparse
import logging

# Make the project root importable (this file lives in scripts/data/).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")

# Auto-map folder path substrings -> concept_id.
# More specific entries first. Keeps in sync with seed_syllabus.py concept IDs.
FOLDER_CONCEPT_MAP = [
    ("probability/cheatsheet",  "PROB_001"),
    ("probability",             "PROB_001"),   # broad — covers Ross, All-of-Stats, etc.
    ("linear_algebra",          "LA_001"),
    ("calculus",                "LA_001"),
    ("machine_learning",        "ML_001"),
    ("dbms",                    "GENERAL"),
    ("dsa",                     "GENERAL"),
    ("ai",                      "GENERAL"),
    ("nptel",                   "GENERAL"),
    ("formulas",                "GENERAL"),
    ("pyqs",                    "GENERAL"),    # PYQs are multi-topic; tag per-question
    ("syllabus",                "GENERAL"),
]


def auto_concept(pdf_path):
    """Infer concept_id from the PDF's folder path."""
    lower = pdf_path.replace("\\", "/").lower()
    for fragment, cid in FOLDER_CONCEPT_MAP:
        if fragment in lower:
            return cid
    return "GENERAL"


def find_pdfs(targets):
    """Resolve CLI targets to a flat list of .pdf paths."""
    if not targets:
        return sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "**", "*.pdf"), recursive=True))

    pdfs = []
    for t in targets:
        if os.path.isdir(t):
            pdfs.extend(sorted(glob.glob(os.path.join(t, "**", "*.pdf"), recursive=True)))
        elif t.lower().endswith(".pdf") and os.path.isfile(t):
            pdfs.append(t)
        else:
            logger.warning(f"Skipping '{t}' — not a PDF or directory.")
    return pdfs


def extract_one(extractor, pdf_path, write_txt=True):
    """Extract cleaned text from a single PDF; optionally write a .txt sibling."""
    text = extractor.extract_text_from_pdf(pdf_path)
    if write_txt:
        txt_path = os.path.splitext(pdf_path)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Wrote cleaned text -> {txt_path} ({len(text)} chars)")
    return text


def main():
    parser = argparse.ArgumentParser(description="Extract text from GATE PDFs into the knowledge base.")
    parser.add_argument("targets", nargs="*", help="PDF files or directories (default: scan knowledge/)")
    parser.add_argument("--ingest", action="store_true", help="Also ingest extracted text into ChromaDB")
    parser.add_argument("--concept", default=None,
                        help="concept_id to tag all PDFs (default: auto-map from folder name)")
    parser.add_argument("--no-txt", action="store_true", help="Do not write sibling .txt files")
    args = parser.parse_args()

    pdfs = find_pdfs(args.targets)
    if not pdfs:
        logger.warning("No PDFs found. Drop files under knowledge/ or pass a path.")
        return

    # Import here so --help works without heavy deps installed.
    from knowledge.ingestion import KnowledgeIngestor

    ingestor = KnowledgeIngestor()
    logger.info(f"Found {len(pdfs)} PDF(s).")

    for pdf in pdfs:
        try:
            extract_one(ingestor, pdf, write_txt=not args.no_txt)
            if args.ingest:
                concept = args.concept or auto_concept(pdf)
                logger.info(f"  concept_id: {concept}")
                ingestor.ingest_document(pdf, concept, os.path.basename(pdf))
        except Exception as e:  # keep going on a single bad file
            logger.error(f"Failed on {pdf}: {e}")

    logger.info("Done.")


if __name__ == "__main__":
    main()
