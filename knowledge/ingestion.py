import os
import logging
from typing import List

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    logger.warning("PyMuPDF not installed. PDF ingestion unavailable.")

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    logger.warning("ChromaDB not installed.")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("LangChain not installed — using basic splitter.")

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False
    logger.warning("sentence-transformers not installed.")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

# Embedding model: BAAI/bge-base-en-v1.5
#   - 109M params, ~440 MB RAM, MIT licence, top MTEB score for its size
#   - Cached to models/embeddings/ after first download
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBEDDING_CACHE_DIR  = os.path.join(os.path.dirname(__file__), "..", "models", "embeddings")

# BGE models perform better with this prefix on queries (not documents)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class KnowledgeIngestor:
    """
    PDF ingestion pipeline:
      Extract (PyMuPDF)  →  Chunk (LangChain)  →  Embed (BGE)  →  Index (ChromaDB)

    Embedding model: BAAI/bge-base-en-v1.5  (replaces all-mpnet-base-v2)
      Advantages for GATE content:
        - Superior performance on technical/scientific text (MTEB 63.5)
        - 3× faster than mpnet on CPU (33M vs 109M params for small variant)
        - Supports instruction-prefix for improved retrieval quality
    """

    def __init__(self):
        self.chroma_client = None
        self.collection    = None
        self.embedding_model = None
        self.text_splitter   = None

        if HAS_CHROMA:
            os.makedirs(CHROMA_DB_PATH, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            # NOTE: must match the collection used by knowledge/ingestor.py and the
            # API retriever, otherwise PDFs ingested here are never retrieved.
            self.collection    = self.chroma_client.get_or_create_collection(
                name="gate_knowledge_base"
            )
            logger.info("ChromaDB collection 'gate_knowledge_base' ready.")

        if HAS_ST:
            os.makedirs(EMBEDDING_CACHE_DIR, exist_ok=True)
            logger.info(f"Loading embedding model '{EMBEDDING_MODEL_NAME}' ...")
            self.embedding_model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                cache_folder=EMBEDDING_CACHE_DIR,
            )
            logger.info("Embedding model loaded.")

        if HAS_LANGCHAIN:
            # Slightly larger chunk for GATE content (derivations need context)
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=512,
                chunk_overlap=64,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len,
            )
        else:
            # Fallback: naive fixed-size splitter
            self.text_splitter = None

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------
    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Encode document chunks (no prefix needed for document side)."""
        return self.embedding_model.encode(
            texts,
            normalize_embeddings=True,   # cosine similarity ready
            show_progress_bar=len(texts) > 20,
            batch_size=32,
        ).tolist()

    def _embed_query(self, query: str) -> List[float]:
        """Encode a user query with BGE instruction prefix for better retrieval."""
        return self.embedding_model.encode(
            BGE_QUERY_PREFIX + query,
            normalize_embeddings=True,
        ).tolist()

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract and clean text from a PDF using PyMuPDF."""
        if not HAS_FITZ:
            raise RuntimeError("PyMuPDF (fitz) not installed. Cannot extract PDF.")

        text = ""
        doc  = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page     = doc.load_page(page_num)
            raw_text = page.get_text("text")

            # Basic cleaning: skip pure-digit lines (page numbers) and very short lines
            lines = raw_text.split("\n")
            cleaned = [
                line for line in lines
                if not line.strip().isdigit() and len(line.strip()) > 2
            ]
            text += "\n".join(cleaned) + "\n"

        logger.info(f"Extracted {len(text)} characters from {pdf_path}")
        return text

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------
    def _split_text(self, text: str) -> List[str]:
        if self.text_splitter:
            return self.text_splitter.split_text(text)
        # Naive fallback
        return [text[i : i + 512] for i in range(0, len(text), 448)]

    # ------------------------------------------------------------------
    # Main ingestion entry point
    # ------------------------------------------------------------------
    def ingest_document(self, pdf_path: str, concept_id: str, source_name: str):
        """
        Full pipeline: Extract → Chunk → Embed → Index
        Upserts into ChromaDB so re-running is idempotent.
        """
        if not self.collection or not self.embedding_model:
            logger.error("ChromaDB or embedding model not available. Aborting ingestion.")
            return

        logger.info(f"Ingesting '{pdf_path}' for concept '{concept_id}' ...")

        # 1. Extract
        full_text = self.extract_text_from_pdf(pdf_path)

        # 2. Chunk
        chunks = self._split_text(full_text)
        logger.info(f"Generated {len(chunks)} chunks.")

        if not chunks:
            logger.warning("No chunks generated — document may be empty.")
            return

        # 3. Metadata
        # Infer source_type from the path so PDF metadata matches the text
        # ingestor's schema (source / source_type / concept_id / chunk_index).
        lower = pdf_path.lower()
        if   "pyqs"      in lower: source_type = "PYQ"
        elif "textbooks" in lower: source_type = "Textbook"
        elif "nptel"     in lower: source_type = "NPTEL"
        elif "formulas"  in lower: source_type = "Formula"
        elif "syllabus"  in lower: source_type = "Syllabus"
        else:                      source_type = "Personal"

        ids      = [f"{concept_id}_pdf_chunk_{i}" for i in range(len(chunks))]
        metadata = [
            {
                "concept_id":  concept_id,
                "source":      source_name,
                "source_type": source_type,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        # 4. Embed (document side — no prefix)
        embeddings = self._embed_documents(chunks)

        # 5. Upsert into ChromaDB (safe to re-run)
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadata,
            ids=ids,
        )
        logger.info(
            f"✅ Ingested {len(chunks)} vectors into ChromaDB "
            f"for concept '{concept_id}' from '{source_name}'."
        )

    def query(self, query_text: str, concept_id: str = None, top_k: int = 5) -> List[dict]:
        """
        Retrieve top-k relevant chunks for a query using BGE embeddings.
        Optionally filter by concept_id.
        """
        if not self.collection or not self.embedding_model:
            logger.error("ChromaDB or embedding model not available.")
            return []

        query_embedding = self._embed_query(query_text)

        where_filter = {"concept_id": concept_id} if concept_id else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
        )

        chunks = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                chunks.append({
                    "content":  doc,
                    "metadata": results["metadatas"][0][i],
                    "score":    results["distances"][0][i] if results.get("distances") else None,
                })
        return chunks


if __name__ == "__main__":
    ingestor = KnowledgeIngestor()
    print("KnowledgeIngestor (PDF) initialized with BAAI/bge-base-en-v1.5 embeddings.")
    # ingestor.ingest_document("path/to/GATE_PYQ.pdf", "ML_NB_001", "GATE 2024 PYQ")
