import os
import glob
import uuid

# Mocking chromadb and langchain imports so it runs in sandbox
try:
    import chromadb
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    CHROMA_INSTALLED = True
except ImportError:
    CHROMA_INSTALLED = False

BASE_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

class KnowledgeIngestor:
    """Core pipeline for Extracting, Chunking, Metadata Generation, and Embedding."""
    
    def __init__(self):
        if CHROMA_INSTALLED:
            self.client = chromadb.PersistentClient(path=DB_PATH)
            self.collection = self.client.get_or_create_collection("gate_knowledge_base")
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", ".", " ", ""]
            )
        else:
            print("WARNING: ChromaDB/LangChain not found. Running in MOCK Mode.")

    def _determine_source_type(self, file_path: str) -> str:
        """Determines source type based on folder structure."""
        lower_path = file_path.lower()
        if "pyqs" in lower_path:
            return "PYQ"
        elif "textbooks" in lower_path:
            return "Textbook"
        elif "nptel" in lower_path:
            return "NPTEL"
        elif "formulas" in lower_path:
            return "Formula"
        elif "syllabus" in lower_path:
            return "Syllabus"
        else:
            return "Personal"

    def _generate_metadata(self, file_path: str, raw_text: str, concept_id: str) -> dict:
        """Generates rich metadata schema based on the spec."""
        source_type = self._determine_source_type(file_path)
        filename = os.path.basename(file_path)
        
        metadata = {
            "source": filename,
            "source_type": source_type,
            "concept_id": concept_id
        }
        
        # Add PYQ specific metadata if applicable (parsed from filename or text later)
        if source_type == "PYQ":
            metadata["question_type"] = "MCQ" # Mock default
            metadata["difficulty"] = 5
            
        return metadata

    def ingest_file(self, file_path: str, concept_id: str):
        """Pipeline: Load -> Chunk -> Metadata -> Embed -> Store"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f"Error reading {file_path}. Please use UTF-8 text/markdown.")
            return

        if CHROMA_INSTALLED:
            chunks = self.text_splitter.split_text(content)
        else:
            # Mock split for sandbox
            chunks = [content[i:i+500] for i in range(0, len(content), 500)]
            
        metadata_list = []
        ids = []
        for i, chunk in enumerate(chunks):
            meta = self._generate_metadata(file_path, chunk, concept_id)
            meta["chunk_index"] = i
            metadata_list.append(meta)
            ids.append(str(uuid.uuid4()))
            
        if CHROMA_INSTALLED:
            self.collection.add(
                documents=chunks,
                metadatas=metadata_list,
                ids=ids
            )
            print(f"Ingested {len(chunks)} chunks into ChromaDB from {os.path.basename(file_path)}.")
        else:
            print(f"[MOCK] Simulated ingesting {len(chunks)} chunks from {os.path.basename(file_path)} with concept_id: {concept_id}.")
            if metadata_list:
                print(f"[MOCK] Sample Metadata: {metadata_list[0]}")

if __name__ == "__main__":
    ingestor = KnowledgeIngestor()
    
    # Just an interactive test. 
    # To run this for real, we loop through folders and map them to concept_ids.
    print("Knowledge Ingestor Initialized.")
