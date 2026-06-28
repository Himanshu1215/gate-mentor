import asyncio
import json
import sys
import os

# Add project root to path so internal package imports work when running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from presentation.api import mock_generate_endpoint, coach_alerts_endpoint
from assessment.simulation_engine import SimulationEngine

async def test_milestone3():
    print("--- 1. Autonomous Coach Health Check ---")
    coach_resp = await coach_alerts_endpoint(authorization="Bearer mock")
    print(f"Push Alerts Generated:\n{json.dumps(coach_resp.alerts, indent=2)}")
    
    print("\n--- 2. Generating Full Mock Exam ---")
    mock_resp = await mock_generate_endpoint(authorization="Bearer mock")
    print(f"Generated Mock Exam: {mock_resp.exam_id} | Total Marks: {mock_resp.total_marks} | Qs: {len(mock_resp.questions)}")
    
    print("\n--- 3. Simulating Exam Submission (Negative Marking) ---")
    # Simulate answering some right, some wrong
    user_answers = {}
    for i, q in enumerate(mock_resp.questions):
        if i % 3 == 0:
            user_answers[q["q_id"]] = q["answer"]  # Correct
        elif i % 3 == 1:
            user_answers[q["q_id"]] = "X" # Wrong
        else:
            pass # Unattempted
            
    # Need a raw dict of the mock exam to pass into grade_mock_exam
    raw_exam = {
        "exam_id": mock_resp.exam_id,
        "duration_mins": mock_resp.duration_mins,
        "total_marks": mock_resp.total_marks,
        "questions": mock_resp.questions
    }
            
    result = SimulationEngine.grade_mock_exam(raw_exam, user_answers)
    print(f"Exam Graded:\n{json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_milestone3())
