"""
scripts/ingest_knowledge.py
────────────────────────────
Thin wrapper kept for backwards-compatible invocation
(`python scripts/ingest_knowledge.py`). The real implementation —
manifest-driven, wipe-and-rebuild ingestion of textbooks/notes/cleaned
PYQs — lives in scripts/rebuild_rag.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.rebuild_rag import main

if __name__ == "__main__":
    main()
