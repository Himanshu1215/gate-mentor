import unittest
from curriculum.dependency_graph import CurriculumEngine
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class TestDependencyGraph(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def tearDown(self):
        self.conn.close()

    def test_get_all_concepts_returns_valid_graph(self):
        graph = CurriculumEngine.get_all_concepts()
        self.assertIsInstance(graph, dict)
        self.assertIn("ML_NB_001", graph)
        self.assertEqual(graph["ML_NB_001"]["subject"], "Machine Learning")

    def test_is_unlocked_logic(self):
        graph = {
            "A": {"state_level": 5},
            "B": {"state_level": 2},
            "C": {"prerequisites": ["A"]}
        }
        self.assertTrue(CurriculumEngine._is_unlocked(graph["C"], graph))

    def test_is_locked_logic(self):
        graph = {
            "A": {"state_level": 2}, 
            "C": {"prerequisites": ["A"]}
        }
        self.assertFalse(CurriculumEngine._is_unlocked(graph["C"], graph))

    def test_get_next_optimal_concept(self):
        next_concept = CurriculumEngine.get_next_optimal_concept()
        self.assertIsNotNone(next_concept)
        self.assertEqual(next_concept, "LA_EIG_001")

if __name__ == "__main__":
    unittest.main()
