import os
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from knowledge.ingestor import KnowledgeIngestor

def test_textbook_ingestion():
    ingestor = KnowledgeIngestor()
    
    file_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "textbooks", "linear_algebra", "strang_ch1.md")
    concept_id = "LA_001" # Vector Space & Subspace
    
    print("\n--- Ingesting Textbook ---")
    ingestor.ingest_file(file_path, concept_id)
    
    print("\n--- Ingesting PYQ ---")
    pyq_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "official", "pyqs", "gate_2024_bayes.json")
    ingestor.ingest_file(pyq_path, "PROB_003")

if __name__ == "__main__":
    test_textbook_ingestion()
