import asyncio
import logging
import sys
import os

# Add project root to path so internal package imports work when running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from presentation.api import ChatRequest, QuizSubmitRequest, chat_endpoint, quiz_submit_endpoint
from learning.intelligence_engine import LearningIntelligenceEngine
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("E2ETest")

async def test_learning_loop():
    print("Initializing Intelligence Engine...")
    engine = LearningIntelligenceEngine()
    
    session_id = "test_session_001"
    concept_id = "ML_NB_001"
    
    print("\n--- Phase 1: Retrieval & Teaching ---")
    chat_req = ChatRequest(session_id=session_id, query="What is Naive Bayes?")
    response = await chat_endpoint(chat_req, authorization="Bearer mock_token")
    print(f"AI Reasoner Output:\n{response.reply}")
    print(f"Citations: {response.citations}")
    
    print("\n--- Phase 2: Quiz & Evaluation ---")
    print("Simulating user taking a quiz and submitting a correct answer...")
    quiz_req = QuizSubmitRequest(
        session_id=session_id,
        concept_id=concept_id,
        is_correct=True,
        confidence=4
    )
    quiz_resp = await quiz_submit_endpoint(quiz_req, authorization="Bearer mock_token")
    print(f"Quiz Submit Success: {quiz_resp.success}, New Mastery Level: {quiz_resp.new_mastery_level}")
    
    # Wait briefly for async event bus to propagate
    await asyncio.sleep(0.5)
    
    print("\n--- Phase 3: Mastery Verification ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT state_level FROM mastery_states WHERE concept_id = ?", (concept_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] == quiz_resp.new_mastery_level:
        print(f"✅ End-to-End Test Passed. Mastery level accurately updated to {row[0]}.")
    else:
        print("❌ End-to-End Test Failed. Database not updated.")

if __name__ == "__main__":
    asyncio.run(test_learning_loop())
