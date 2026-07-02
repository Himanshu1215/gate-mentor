"""
scripts/rebuild_rag.py
────────────────────────
Pure Python — orchestrates knowledge/ingestor.py's embedding+ChromaDB
pipeline (no LLM calls of its own). Wipes and rebuilds the
'gate_knowledge_base' collection from three curated, manifest-driven
sources (knowledge/ingest_manifest.json):

  (a) extracted textbook markdown (scripts/extract_textbooks.py output),
      tagged with subject metadata.
  (b) knowledge/notes/*.md (Gemini-authored study notes) — concept_id is the
      filename stem, subject is looked up from the prefix.
  (c) knowledge/official/pyqs/cleaned/*.json question+explanation text,
      tagged source_type=PYQ with the question's real concept_id/subject.

Raw PYQ .txt dumps, knowledge/official/pyqs/parsed/*.json, and
knowledge/personal/** are never ingested — that garbled/unverified/private
data must not pollute the RAG corpus.
"""

import os
import sys
import json
import glob
import fnmatch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from core.subject_map import subject_for_concept
from knowledge.ingestor import KnowledgeIngestor

MANIFEST_PATH = os.path.join(ROOT, "knowledge", "ingest_manifest.json")


def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _to_rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def _is_excluded(path: str, exclude_globs) -> bool:
    rel = _to_rel(path)
    return any(fnmatch.fnmatch(rel, pat) for pat in exclude_globs)


def wipe_collection(ingestor: KnowledgeIngestor):
    if not ingestor.client:
        print("[MOCK] No ChromaDB client available — skipping wipe.")
        return
    try:
        ingestor.client.delete_collection("gate_knowledge_base")
    except Exception:
        pass
    ingestor.collection = ingestor.client.get_or_create_collection("gate_knowledge_base")
    print("Wiped and recreated collection 'gate_knowledge_base'.")


def ingest_textbooks(ingestor: KnowledgeIngestor, manifest: dict, exclude_globs) -> int:
    total = 0
    for rule in manifest.get("textbook_rules", []):
        pattern = os.path.join(ROOT, rule["glob"])
        for path in sorted(glob.glob(pattern, recursive=True)):
            if _is_excluded(path, exclude_globs):
                continue
            ingestor.ingest_file(path, concept_id="", subject=rule["subject"])
            total += 1
    print(f"Ingested {total} textbook markdown file(s).")
    return total


def ingest_notes(ingestor: KnowledgeIngestor, manifest: dict, exclude_globs) -> int:
    pattern = os.path.join(ROOT, manifest.get("notes_glob", "knowledge/notes/*.md"))
    total = 0
    for path in sorted(glob.glob(pattern)):
        if _is_excluded(path, exclude_globs):
            continue
        concept_id = os.path.splitext(os.path.basename(path))[0]
        subject = subject_for_concept(concept_id) or ""
        ingestor.ingest_file(path, concept_id=concept_id, subject=subject)
        total += 1
    print(f"Ingested {total} study-notes file(s).")
    return total


def ingest_cleaned_pyqs(ingestor: KnowledgeIngestor, manifest: dict, exclude_globs) -> int:
    pattern = os.path.join(ROOT, manifest.get("cleaned_pyqs_glob", "knowledge/official/pyqs/cleaned/*.json"))
    total_files = 0
    total_chunks = 0
    for path in sorted(glob.glob(pattern)):
        if os.path.basename(path) == "_manifest.json" or _is_excluded(path, exclude_globs):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
        except Exception:
            continue
        text = f"{rec.get('question_text', '')}\n\n{rec.get('explanation', '')}".strip()
        if not text:
            continue
        n = ingestor.ingest_text(
            text,
            source=rec.get("id") or os.path.splitext(os.path.basename(path))[0],
            concept_id=rec.get("concept_id"),
            subject=rec.get("subject"),
            source_type="PYQ",
        )
        total_files += 1
        total_chunks += n
    print(f"Ingested {total_files} cleaned PYQ(s) ({total_chunks} chunk(s)).")
    return total_files


def main():
    manifest = load_manifest()
    exclude_globs = manifest.get("exclude_globs", [])

    ingestor = KnowledgeIngestor()
    wipe_collection(ingestor)

    n_textbooks = ingest_textbooks(ingestor, manifest, exclude_globs)
    n_notes = ingest_notes(ingestor, manifest, exclude_globs)
    n_pyqs = ingest_cleaned_pyqs(ingestor, manifest, exclude_globs)

    print(f"\nRebuild complete: {n_textbooks} textbook file(s), {n_notes} notes file(s), {n_pyqs} cleaned PYQ(s).")
    if n_textbooks == 0 and n_notes == 0 and n_pyqs == 0:
        print("WARNING: nothing was ingested. Run scripts/extract_textbooks.py and the "
              "Gemini notes/PYQ pipelines first, or check knowledge/ingest_manifest.json.")


if __name__ == "__main__":
    main()
