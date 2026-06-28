import sqlite3
import os
import uuid
import datetime
from typing import Dict, Any

from core.event_bus import bus, Events

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

class SessionManager:
    """Manages the Learning Session lifecycle, wrapping isolated events into continuous sessions."""
    
    @staticmethod
    def start_session(goals: str) -> str:
        """Starts a new learning session and returns the session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO learning_sessions (session_id, start_time, goals) VALUES (?, ?, ?)",
            (session_id, now, goals)
        )
        conn.commit()
        conn.close()
        
        return session_id

    @staticmethod
    def end_session(session_id: str, reflection: str = ""):
        """Ends an active learning session and records reflection."""
        now = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE learning_sessions SET end_time = ?, reflection = ? WHERE session_id = ?",
            (now, reflection, session_id)
        )
        conn.commit()
        conn.close()
        
class SessionEventSubscriber:
    """Listens for events to inject session metadata if needed."""
    def __init__(self):
        bus.subscribe(Events.SESSION_STARTED, self.handle_session_started)
        bus.subscribe(Events.SESSION_ENDED, self.handle_session_ended)

    async def handle_session_started(self, data: Dict[str, Any]):
        session_id = data.get("session_id")
        print(f"[SessionManager] Session {session_id} started. Background analytics tracking engaged.")
        
    async def handle_session_ended(self, data: Dict[str, Any]):
        session_id = data.get("session_id")
        print(f"[SessionManager] Session {session_id} ended. Computing session statistics...")

if __name__ == "__main__":
    # Local test
    sid = SessionManager.start_session(goals="Master Naive Bayes and revise Linear Algebra")
    print(f"Started Session: {sid}")
    SessionManager.end_session(sid, reflection="Felt good about conditional probability, struggled with Bayes Theorem.")
    print("Session Ended.")
