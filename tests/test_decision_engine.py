import pytest
from learning.decision_engine import MasteryCalculator
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

@pytest.fixture(autouse=True)
def setup_db():
    # Insert a mock concept for testing
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO concepts (concept_id, subject, topic) VALUES ('TEST_001', 'Test', 'Test')")
    # Reset mastery to Unknown (1)
    cursor.execute("INSERT OR REPLACE INTO mastery_states (concept_id, state_level, accuracy) VALUES ('TEST_001', 1, 0.0)")
    conn.commit()
    conn.close()
    yield

def test_correct_answer_high_confidence_promotes_level():
    new_lvl = MasteryCalculator.update_mastery("TEST_001", is_correct=True, confidence=4)
    assert new_lvl == 2

def test_correct_answer_low_confidence_does_not_promote():
    # Start at 1
    new_lvl = MasteryCalculator.update_mastery("TEST_001", is_correct=True, confidence=2)
    assert new_lvl == 1

def test_incorrect_answer_demotes_level():
    # Promote to 2 first
    MasteryCalculator.update_mastery("TEST_001", is_correct=True, confidence=5)
    
    # Demote it
    new_lvl = MasteryCalculator.update_mastery("TEST_001", is_correct=False, confidence=1)
    assert new_lvl == 1

def test_incorrect_answer_cannot_demote_below_1():
    new_lvl = MasteryCalculator.update_mastery("TEST_001", is_correct=False, confidence=1)
    assert new_lvl == 1
