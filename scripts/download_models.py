"""
scripts/download_models.py
──────────────────────────
Downloads the required local models for GATE DA Mentor:

  1. LLM  : microsoft/Phi-4-mini-instruct  (Q4_K_M GGUF, ~2.5 GB)
             Best math+reasoning model for 8 GB RAM / CPU-only setups.

  2. Embed: BAAI/bge-base-en-v1.5  (~440 MB)
             Auto-downloaded by sentence-transformers on first use,
             but this script pre-caches it for offline use.

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --llm-only
    python scripts/download_models.py --embed-only
"""

import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR     = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR   = os.path.join(ROOT_DIR, "models")
LLM_DIR      = os.path.join(MODELS_DIR, "llm")
EMBED_DIR    = os.path.join(MODELS_DIR, "embeddings")
LLM_FILENAME = "phi-4-mini-instruct-q4_k_m.gguf"
LLM_PATH     = os.path.join(LLM_DIR, LLM_FILENAME)


def download_llm():
    """Download Phi-4-mini-instruct Q4_K_M GGUF from HuggingFace Hub."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        logger.error("huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    os.makedirs(LLM_DIR, exist_ok=True)

    if os.path.exists(LLM_PATH):
        size_gb = os.path.getsize(LLM_PATH) / (1024 ** 3)
        logger.info(f"LLM already downloaded at {LLM_PATH} ({size_gb:.2f} GB). Skipping.")
        return

    logger.info("Downloading Phi-4-mini-instruct Q4_K_M GGUF (~2.5 GB)...")
    logger.info("This may take several minutes on first run.")

    try:
        path = hf_hub_download(
            repo_id="microsoft/Phi-4-mini-instruct-gguf",
            filename="Phi-4-mini-instruct-Q4_K_M.gguf",
            local_dir=LLM_DIR,
            local_dir_use_symlinks=False,
        )
        # Rename to our expected filename
        if os.path.abspath(path) != os.path.abspath(LLM_PATH):
            os.rename(path, LLM_PATH)

        size_gb = os.path.getsize(LLM_PATH) / (1024 ** 3)
        logger.info(f"✅ LLM downloaded: {LLM_PATH} ({size_gb:.2f} GB)")

    except Exception as e:
        logger.error(f"Failed to download LLM: {e}")
        logger.info("Alternative: manually download from https://huggingface.co/microsoft/Phi-4-mini-instruct-gguf")
        logger.info(f"  and place as: {LLM_PATH}")
        sys.exit(1)


def download_embeddings():
    """Pre-cache BAAI/bge-base-en-v1.5 embedding model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)

    os.makedirs(EMBED_DIR, exist_ok=True)

    logger.info("Pre-caching BAAI/bge-base-en-v1.5 (~440 MB)...")
    try:
        model = SentenceTransformer("BAAI/bge-base-en-v1.5", cache_folder=EMBED_DIR)
        # Quick test
        test_vec = model.encode("GATE DA test", normalize_embeddings=True)
        logger.info(f"✅ Embedding model ready. Vector dim: {len(test_vec)}")
    except Exception as e:
        logger.error(f"Failed to download embedding model: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Download local models for GATE DA Mentor")
    parser.add_argument("--llm-only",   action="store_true", help="Only download LLM")
    parser.add_argument("--embed-only", action="store_true", help="Only download embedding model")
    args = parser.parse_args()

    if args.embed_only:
        download_embeddings()
    elif args.llm_only:
        download_llm()
    else:
        download_embeddings()  # embeddings first (smaller, faster)
        download_llm()

    logger.info("\n✅ All models ready. You can now start the backend:")
    logger.info("   uvicorn presentation.api:app --host 0.0.0.0 --port 8000 --reload")


if __name__ == "__main__":
    main()
