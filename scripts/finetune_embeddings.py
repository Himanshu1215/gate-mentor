"""
scripts/finetune_embeddings.py
──────────────────────────────
(OPTIONAL, CPU-FEASIBLE) Fine-tune the BAAI/bge-base-en-v1.5 embedding model on
GATE (question -> relevant-text) pairs to improve RAG retrieval. The 109M model
trains fine on the 8 GB / 4 vCPU box for a few thousand pairs.

Use this only if scripts/eval/eval_retrieval.py shows weak recall after fixing
ingestion and adding data. It does NOT touch the LLM.

Training pairs are mined from structured PYQ JSON: the positive text for each
question is its solution (or question+options). sentence-transformers'
MultipleNegativesRankingLoss treats other questions' positives as in-batch
negatives, so only positive pairs are required.

Output: a fine-tuned model saved to models/embeddings/bge-base-gate/. Point the
ingestor at it (EMBEDDING_MODEL_NAME) and RE-EMBED the corpus before querying.

Usage
-----
    python scripts/finetune_embeddings.py
    python scripts/finetune_embeddings.py --epochs 2 --batch-size 16
"""

import os
import sys
import json
import glob
import argparse
import logging

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYQ_DIR = os.path.join(ROOT, "knowledge", "official", "pyqs")
OUT_DIR = os.path.join(ROOT, "models", "embeddings", "bge-base-gate")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def mine_pairs():
    """Build (query, positive_text) pairs from structured PYQ JSON."""
    pairs = []
    for path in sorted(glob.glob(os.path.join(PYQ_DIR, "**", "*.json"), recursive=True)):
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
        except Exception:
            continue
        q = (rec.get("question_text") or "").strip()
        positive = (rec.get("solution") or "").strip()
        if not positive and rec.get("options"):
            opts = rec["options"]
            positive = q + " " + " ".join(f"{k}: {v}" for k, v in opts.items()) \
                if isinstance(opts, dict) else q
        if q and positive:
            pairs.append((q, positive))
    return pairs


def main():
    parser = argparse.ArgumentParser(description="CPU fine-tune of bge-base on GATE pairs.")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--base", default="BAAI/bge-base-en-v1.5")
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()

    pairs = mine_pairs()
    logger.info(f"Mined {len(pairs)} (query, positive) pairs from {PYQ_DIR}")
    if len(pairs) < 20:
        logger.error(
            "Too few pairs to fine-tune usefully (need a few hundred+). Collect more "
            "PYQs with solutions first via scripts/data/parse_pyqs.py."
        )
        sys.exit(1)

    from sentence_transformers import SentenceTransformer, InputExample, losses
    from torch.utils.data import DataLoader

    model = SentenceTransformer(args.base)
    examples = [InputExample(texts=[q, p]) for q, p in pairs]
    loader = DataLoader(examples, shuffle=True, batch_size=args.batch_size)
    loss = losses.MultipleNegativesRankingLoss(model)

    warmup = int(len(loader) * args.epochs * 0.1)
    logger.info(f"Training {args.epochs} epoch(s), batch {args.batch_size}, warmup {warmup} ...")
    model.fit(
        train_objectives=[(loader, loss)],
        epochs=args.epochs,
        warmup_steps=warmup,
        show_progress_bar=True,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    model.save(args.out_dir)
    logger.info(f"✅ Fine-tuned embedding model saved -> {args.out_dir}")
    logger.info(
        "To use it: set EMBEDDING_MODEL_NAME in knowledge/ingestor.py and "
        "knowledge/ingestion.py to this path, then RE-EMBED the corpus."
    )


if __name__ == "__main__":
    main()
