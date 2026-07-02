"""
scripts/ingest_knowledge.py
"""
import os
import sys
import glob

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(ROOT_DIR)

from knowledge.ingestor import KnowledgeIngestor as MDIngestor
from knowledge.ingestion import KnowledgeIngestor as PDFIngestor

def main():
    print("Initializing ingestors...")
    md_ingestor = MDIngestor()
    pdf_ingestor = PDFIngestor()

    existing_sources = set()
    if md_ingestor.collection:
        results = md_ingestor.collection.get(include=["metadatas"])
        if results and results.get("metadatas"):
            for meta in results["metadatas"]:
                if meta and "source" in meta:
                    existing_sources.add(meta["source"])
    
    print(f"Found {len(existing_sources)} already ingested sources.")
    count_md = 0
    count_pdf = 0

    original_ingest_file = md_ingestor.ingest_file
    def skipped_ingest_file(file_path, concept_id):
        nonlocal count_md
        if os.path.basename(file_path) in existing_sources:
            return
        original_ingest_file(file_path, concept_id)
        count_md += 1
    
    md_ingestor.ingest_file = skipped_ingest_file

    print("Ingesting MD/TXT via ingest_directory()...")
    md_ingestor.ingest_directory()

    print("Ingesting PDFs...")
    pdf_files = glob.glob(os.path.join(ROOT_DIR, "knowledge", "textbooks", "**", "*.pdf"), recursive=True)
    pdf_files += glob.glob(os.path.join(ROOT_DIR, "knowledge", "official", "syllabus", "**", "*.pdf"), recursive=True)

    for pdf_path in pdf_files:
        basename = os.path.basename(pdf_path)
        if basename in existing_sources:
            continue
        print(f"Ingesting {basename}...")
        pdf_ingestor.ingest_document(pdf_path, "GENERAL", basename)
        count_pdf += 1

    print(f"Summary: Ingested {count_md} new MD/TXT files, {count_pdf} new PDF files.")

if __name__ == "__main__":
    main()
