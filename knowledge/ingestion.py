import os
import logging
from typing import List

# NOTE: The following dependencies need to be installed via requirements.txt
try:
    import fitz  # PyMuPDF
    import chromadb
    from chromadb.config import Settings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from sentence_transformers import SentenceTransformer
except ImportError:
    logging.warning("Dependencies not installed. Run: pip install -r requirements.txt")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

class KnowledgeIngestor:
    def __init__(self):
        # Set up ChromaDB Persistent Client explicitly as requested
        try:
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            self.collection = self.chroma_client.get_or_create_collection(name="gate_knowledge")
            
            # Sentence Transformers for local embeddings
            self.embedding_model = SentenceTransformer('all-mpnet-base-v2')
            
            # Semantic chunking via LangChain (chunk size 400 as per spec)
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=50,
                length_function=len,
                is_separator_regex=False,
            )
        except NameError:
            logger.error("Libraries not loaded.")

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extracts text from a given PDF using PyMuPDF and cleans headers/footers."""
        text = ""
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            raw_text = page.get_text("text")
            
            # Basic cleaning (mock logic for removing standard headers)
            lines = raw_text.split('\n')
            cleaned_lines = [line for line in lines if "Chapter" not in line and not line.isdigit()]
            text += "\n".join(cleaned_lines)
            
        return text

    def ingest_document(self, pdf_path: str, concept_id: str, source_name: str):
        """Full pipeline: Extract -> Chunk -> Metadata -> Embed -> Index"""
        logger.info(f"Starting ingestion for {pdf_path} mapped to concept {concept_id}")
        
        # 1. Extraction & Cleaning
        full_text = self.extract_text_from_pdf(pdf_path)
        
        # 2. Semantic Chunking
        chunks = self.text_splitter.split_text(full_text)
        logger.info(f"Generated {len(chunks)} chunks.")
        
        # 3. Metadata Generation
        metadata = [{"concept_id": concept_id, "source": source_name} for _ in chunks]
        ids = [f"{concept_id}_chunk_{i}" for i in range(len(chunks))]
        
        # 4. Embedding Generation
        embeddings = self.embedding_model.encode(chunks).tolist()
        
        # 5. Indexing (Upsert into ChromaDB)
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadata,
            ids=ids
        )
        logger.info(f"Successfully ingested {len(chunks)} vectors into ChromaDB for concept {concept_id}.")

if __name__ == "__main__":
    # Example usage for testing
    logger.info("Initializing Knowledge Ingestor...")
    # ingestor = KnowledgeIngestor()
    # ingestor.ingest_document("path/to/ISLR.pdf", "ML_NB_001", "ISLR Chapter 4")
