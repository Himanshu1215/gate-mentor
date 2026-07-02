import os
import glob
import uuid
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    logger.warning("ChromaDB not installed — running in MOCK mode.")

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False
    logger.warning("sentence-transformers not installed.")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_KNOWLEDGE_DIR   = os.path.join(os.path.dirname(__file__), "..", "knowledge")
DB_PATH              = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

# Embedding model: BAAI/bge-base-en-v1.5
#   - 109M params · ~440 MB · MIT licence
#   - Instruction-aware: use BGE_QUERY_PREFIX for query embeddings
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBEDDING_CACHE_DIR  = os.path.join(os.path.dirname(__file__), "..", "models", "embeddings")
BGE_QUERY_PREFIX     = "Represent this sentence for searching relevant passages: "


class KnowledgeIngestor:
    """
    Text / Markdown ingestion pipeline:
      Load  →  Chunk (LangChain)  →  Embed (BGE)  →  Store (ChromaDB)

    Collection: 'gate_knowledge_base'  (shared with PDF ingestor)
    Embedding model: BAAI/bge-base-en-v1.5  (replaces all-mpnet-base-v2)
    """

    def __init__(self):
        self.client          = None
        self.collection      = None
        self.embedding_model = None
        self.text_splitter   = None

        if HAS_CHROMA:
            os.makedirs(DB_PATH, exist_ok=True)
            self.client     = chromadb.PersistentClient(path=DB_PATH)
            self.collection = self.client.get_or_create_collection("gate_knowledge_base")
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
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=512,
                chunk_overlap=64,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
        else:
            self.text_splitter = None

        if not HAS_CHROMA or not HAS_ST:
            logger.warning("Running in MOCK mode — embeddings will be simulated.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _determine_source_type(self, file_path: str) -> str:
        lower = file_path.lower()
        if "pyqs"      in lower: return "PYQ"
        if "textbooks" in lower: return "Textbook"
        if "nptel"     in lower: return "NPTEL"
        if "formulas"  in lower: return "Formula"
        if "syllabus"  in lower: return "Syllabus"
        return "Personal"

    def _generate_metadata(self, file_path: str, concept_id: str, chunk_index: int,
                            subject: str = None, source_type_override: str = None) -> dict:
        source_type = source_type_override or self._determine_source_type(file_path)
        meta = {
            "source":      os.path.basename(file_path),
            "source_type": source_type,
            "concept_id":  concept_id or "",
            "subject":     subject or "",
            "chunk_index": chunk_index,
        }
        if source_type == "PYQ":
            meta["question_type"] = "MCQ"
        return meta

    def _split_text(self, text: str):
        if self.text_splitter:
            return self.text_splitter.split_text(text)
        return [text[i : i + 512] for i in range(0, len(text), 448)]

    def _embed_documents(self, texts):
        return self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 20,
            batch_size=32,
        ).tolist()

    def _embed_query(self, query: str):
        return self.embedding_model.encode(
            BGE_QUERY_PREFIX + query,
            normalize_embeddings=True,
        ).tolist()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def ingest_file(self, file_path: str, concept_id: str, subject: str = None):
        """Pipeline: Load → Chunk → Embed → Store (upsert, idempotent)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.error(f"Cannot read {file_path} — ensure UTF-8 encoding.")
            return

        chunks = self._split_text(content)
        if not chunks:
            logger.warning(f"No chunks from {file_path}.")
            return

        metadata_list = [
            self._generate_metadata(file_path, concept_id, i, subject=subject)
            for i in range(len(chunks))
        ]
        ids = [str(uuid.uuid4()) for _ in chunks]

        if self.collection and self.embedding_model:
            embeddings = self._embed_documents(chunks)
            self.collection.upsert(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadata_list,
                ids=ids,
            )
            logger.info(
                f"✅ Ingested {len(chunks)} chunks from "
                f"'{os.path.basename(file_path)}' (concept: {concept_id})."
            )
        else:
            # MOCK mode
            logger.info(
                f"[MOCK] Would ingest {len(chunks)} chunks from "
                f"'{os.path.basename(file_path)}' (concept: {concept_id})."
            )
            if metadata_list:
                logger.info(f"[MOCK] Sample metadata: {metadata_list[0]}")

    def ingest_text(self, text: str, source: str, concept_id: str = None,
                     subject: str = None, source_type: str = "Personal") -> int:
        """Chunk → Embed → Store raw text that has no file on disk (e.g. a
        cleaned PYQ's question+explanation). Returns the number of chunks
        ingested."""
        chunks = self._split_text(text)
        if not chunks:
            return 0

        metadata_list = [
            self._generate_metadata(source, concept_id, i, subject=subject, source_type_override=source_type)
            for i in range(len(chunks))
        ]
        ids = [str(uuid.uuid4()) for _ in chunks]

        if self.collection and self.embedding_model:
            embeddings = self._embed_documents(chunks)
            self.collection.upsert(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadata_list,
                ids=ids,
            )
        else:
            logger.info(f"[MOCK] Would ingest {len(chunks)} chunks from '{source}' (concept: {concept_id}).")
        return len(chunks)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def query(self, query_text: str, concept_id: str = None, subject: str = None, top_k: int = 5) -> list:
        """
        Retrieve relevant chunks for RAG, optionally filtered by concept_id
        and/or subject. If a filtered query returns fewer than 2 chunks, it
        retries unfiltered rather than starving the LLM of context.
        """
        if not self.collection or not self.embedding_model:
            logger.error("Collection or embedding model unavailable.")
            return []

        query_embedding = self._embed_query(query_text)
        where_filter = self._build_where(concept_id, subject)

        chunks = self._run_query(query_embedding, top_k, where_filter)
        if len(chunks) < 2 and where_filter:
            chunks = self._run_query(query_embedding, top_k, None)
        return chunks

    @staticmethod
    def _build_where(concept_id: str = None, subject: str = None):
        clauses = []
        if concept_id:
            clauses.append({"concept_id": concept_id})
        if subject:
            clauses.append({"subject": subject})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _run_query(self, query_embedding, top_k: int, where_filter) -> list:
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

    # ------------------------------------------------------------------
    # Batch ingest entire knowledge directory
    # ------------------------------------------------------------------
    def ingest_directory(self, concept_id_map: dict = None):
        """
        Scan the knowledge/ directory and ingest all .md / .txt files.
        concept_id_map: { filename_substr: concept_id }  (optional override)
        Falls back to 'GENERAL' if no mapping found.
        """
        patterns = [
            os.path.join(BASE_KNOWLEDGE_DIR, "**", "*.md"),
            os.path.join(BASE_KNOWLEDGE_DIR, "**", "*.txt"),
        ]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern, recursive=True))

        if not files:
            logger.warning("No .md or .txt files found in knowledge/")
            return

        for file_path in files:
            concept_id = "GENERAL"
            if concept_id_map:
                for key, cid in concept_id_map.items():
                    if key in file_path:
                        concept_id = cid
                        break
            self.ingest_file(file_path, concept_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingestor = KnowledgeIngestor()
    print("KnowledgeIngestor (Text/MD) initialized with BAAI/bge-base-en-v1.5 embeddings.")
    # ingestor.ingest_directory()
