"""
scripts/eval/eval_retrieval.py
──────────────────────────────
Measure RAG retrieval quality (recall@k and MRR) on the CPU VM. Run it before
and after any change to embeddings / ingestion to know if retrieval actually
improved.

Eval set: a JSON list of {query, expected} pairs, where `expected` matches a
chunk's metadata `concept_id` OR a substring of its `source` filename. Default
path: scripts/eval/eval_set.json. A starter file is auto-created if missing.

Usage
-----
    python scripts/eval/eval_retrieval.py
    python scripts/eval/eval_retrieval.py --k 5 --eval-set path/to/eval_set.json
"""

import os
import sys
import json
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_EVAL_SET = os.path.join(os.path.dirname(__file__), "eval_set.json")

STARTER = [
    {"query": "What is Bayes theorem and how is posterior probability computed?",
     "expected": "PROB_003"},
    {"query": "Define a vector space and a subspace.", "expected": "LA_001"},
    {"query": "How are eigenvalues related to the determinant of a matrix?",
     "expected": "LA_002"},
]


def matches(chunk, expected):
    meta = chunk.get("metadata", {})
    if meta.get("concept_id") == expected:
        return True
    src = str(meta.get("source", "")).lower()
    return expected.lower() in src


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval (recall@k, MRR).")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--eval-set", default=DEFAULT_EVAL_SET)
    args = parser.parse_args()

    if not os.path.exists(args.eval_set):
        os.makedirs(os.path.dirname(args.eval_set), exist_ok=True)
        with open(args.eval_set, "w", encoding="utf-8") as f:
            json.dump(STARTER, f, indent=2)
        logger.info(f"Created starter eval set -> {args.eval_set}. Expand it with real pairs.")

    with open(args.eval_set, encoding="utf-8") as f:
        eval_pairs = json.load(f)

    from knowledge.ingestor import KnowledgeIngestor
    retriever = KnowledgeIngestor()

    hits, rr_sum, n = 0, 0.0, len(eval_pairs)
    for pair in eval_pairs:
        chunks = retriever.query(pair["query"], top_k=args.k)
        rank = next((i + 1 for i, c in enumerate(chunks) if matches(c, pair["expected"])), 0)
        if rank:
            hits += 1
            rr_sum += 1.0 / rank
        status = f"rank {rank}" if rank else "MISS"
        logger.info(f"[{status}] {pair['query'][:60]}  (expected {pair['expected']})")

    if n == 0:
        logger.warning("Empty eval set.")
        return

    logger.info("─" * 50)
    logger.info(f"Recall@{args.k}: {hits}/{n} = {hits / n:.3f}")
    logger.info(f"MRR@{args.k}:    {rr_sum / n:.3f}")


if __name__ == "__main__":
    main()
