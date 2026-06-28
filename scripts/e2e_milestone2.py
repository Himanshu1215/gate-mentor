import asyncio
import json
import sys
import os

# Add project root to path so internal package imports work when running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from presentation.api import SessionStartRequest, session_start_endpoint, curriculum_next_endpoint
from analytics.dashboard_metrics import DashboardAnalytics
from planner.goal_engine import GoalEngine
from planner.adaptive_scheduler import AdaptiveScheduler
from learning.session_manager import SessionManager

async def test_milestone2():
    print("--- 1. Starting a New Learning Session ---")
    req = SessionStartRequest(goals="Focus on Linear Algebra prerequisites")
    resp = await session_start_endpoint(req, authorization="Bearer mock")
    session_id = resp.session_id
    print(f"Session Started successfully: {session_id}")
    
    print("\n--- 2. Fetching Next Optimal Concept from Curriculum DAG ---")
    next_concept = await curriculum_next_endpoint(authorization="Bearer mock")
    print(f"Next Concept to learn: {next_concept.concept_id} ({next_concept.topic})")
    
    print("\n--- 3. Generating Adaptive Daily Schedule ---")
    schedule = AdaptiveScheduler.generate_daily_schedule(120)
    print(f"Schedule Generated: {json.dumps(schedule, indent=2)}")
    
    print("\n--- 4. Computing Goal Projections (Target AIR) ---")
    goals = GoalEngine.get_current_projection()
    print(f"Current Projections: {json.dumps(goals, indent=2)}")
    
    print("\n--- 5. Computing Dashboard Analytics ---")
    stats = DashboardAnalytics.get_dashboard_stats()
    print(f"Dashboard Stats: {json.dumps(stats, indent=2)}")
    
    print("\n--- 6. Ending Learning Session ---")
    SessionManager.end_session(session_id, reflection="Understood Eigenvalues perfectly.")
    print("Session closed and saved.")
    
if __name__ == "__main__":
    asyncio.run(test_milestone2())
