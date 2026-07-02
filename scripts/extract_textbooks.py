"""
scripts/extract_textbooks.py
────────────────────────────
Pure Python (PyMuPDF only, NO LLM/API calls). Extracts every PDF under
knowledge/textbooks/** into Markdown, chunked into ~10-page blocks, so
rebuild_rag.py can ingest real textbook prose instead of garbled PYQ dumps.

Output: knowledge/textbooks/<subject>/extracted/<pdf-stem>/<pages>.md
Idempotent — a PDF whose extracted/<stem>/ dir already has .md files is
skipped, so re-running after adding one new textbook is cheap.

Headings are detected via a font-size heuristic (larger than the page's
dominant body-text size -> heading), and lines that repeat across most pages
of a PDF (running headers/footers, "Page N of M", etc.) are dropped.
"""

import os
import re
import sys
import glob
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF is required: pip install pymupdf")
    sys.exit(1)

TEXTBOOKS_DIR = os.path.join(ROOT, "knowledge", "textbooks")
PAGES_PER_BLOCK = 10


def _page_lines_with_sizes(page):
    """Return [(text, max_font_size), ...] for every non-empty line on a page."""
    lines = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            size = max(s.get("size", 0) for s in spans)
            lines.append((text, size))
    return lines


def _normalize_for_repeat_check(text: str) -> str:
    return re.sub(r"\d+", "#", text.strip().lower())


def _find_repeated_lines(all_pages_lines, n_pages) -> set:
    """Lines appearing (once each) on >=50% of pages are headers/footers."""
    if n_pages < 3:
        return set()
    counts = Counter()
    for lines in all_pages_lines:
        seen_this_page = set()
        for text, _ in lines:
            norm = _normalize_for_repeat_check(text)
            if norm and norm not in seen_this_page:
                counts[norm] += 1
                seen_this_page.add(norm)
    threshold = max(2, int(n_pages * 0.5))
    return {norm for norm, c in counts.items() if c >= threshold}


def _dominant_body_size(all_pages_lines) -> float:
    sizes = Counter()
    for lines in all_pages_lines:
        for _, size in lines:
            sizes[round(size, 1)] += 1
    return sizes.most_common(1)[0][0] if sizes else 10.0


def _page_to_markdown(lines, body_size, repeated_lines) -> str:
    out = []
    for text, size in lines:
        if _normalize_for_repeat_check(text) in repeated_lines:
            continue
        if size >= body_size + 4:
            out.append(f"## {text}")
        elif size >= body_size + 1.5:
            out.append(f"### {text}")
        else:
            out.append(text)
    return "\n\n".join(out)


def extract_pdf(pdf_path: str) -> int:
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    out_dir = os.path.join(os.path.dirname(pdf_path), "extracted", stem)
    if os.path.isdir(out_dir) and glob.glob(os.path.join(out_dir, "*.md")):
        print(f"Skip (already extracted): {pdf_path}")
        return 0

    doc = fitz.open(pdf_path)
    n_pages = len(doc)
    all_pages_lines = [_page_lines_with_sizes(doc.load_page(i)) for i in range(n_pages)]
    repeated_lines = _find_repeated_lines(all_pages_lines, n_pages)
    body_size = _dominant_body_size(all_pages_lines)

    os.makedirs(out_dir, exist_ok=True)
    n_written = 0
    for start in range(0, n_pages, PAGES_PER_BLOCK):
        end = min(start + PAGES_PER_BLOCK, n_pages)
        block_parts = [
            _page_to_markdown(all_pages_lines[i], body_size, repeated_lines)
            for i in range(start, end)
        ]
        content = "\n\n".join(p for p in block_parts if p.strip()).strip()
        if not content:
            continue
        out_path = os.path.join(out_dir, f"{start + 1:04d}-{end:04d}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        n_written += 1

    doc.close()
    print(f"Extracted {pdf_path} -> {n_written} block(s) in {out_dir}")
    return n_written


def main():
    pdfs = sorted(glob.glob(os.path.join(TEXTBOOKS_DIR, "**", "*.pdf"), recursive=True))
    print(f"Found {len(pdfs)} textbook PDF(s) under {TEXTBOOKS_DIR}")
    total_blocks = 0
    for pdf_path in pdfs:
        total_blocks += extract_pdf(pdf_path)
    print(f"Done. Wrote {total_blocks} markdown block file(s) total.")


if __name__ == "__main__":
    main()
