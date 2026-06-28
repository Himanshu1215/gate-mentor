import unittest
from planner.goal_engine import GoalEngine
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class TestGoalEngine(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def tearDown(self):
        self.conn.close()

    def test_goal_projection_keys(self):
        projection = GoalEngine.get_current_projection()
        
        # Assert all keys are present
        self.assertIn("avg_mastery_level", projection)
        self.assertIn("avg_accuracy", projection)
        self.assertIn("projected_score", projection)
        self.assertIn("projected_air", projection)
        self.assertIn("risk_level", projection)

    def test_goal_projection_bounds(self):
        projection = GoalEngine.get_current_projection()
        
        # Projected Score should be between 0 and 100
        self.assertTrue(0 <= projection["projected_score"] <= 100)
        
        # Projected AIR should be >= 1
        self.assertTrue(projection["projected_air"] >= 1)
        
        # Risk Level should be one of High, Medium, Low
        self.assertIn(projection["risk_level"], ["High", "Medium", "Low"])

if __name__ == "__main__":
    unittest.main()
