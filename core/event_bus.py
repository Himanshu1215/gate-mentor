from typing import Callable, Dict, List, Any
import asyncio

class EventBus:
    """
    A simple async Pub/Sub Event Bus for the GATE DA Mentor.
    Allows components to communicate asynchronously without tight coupling.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers: Dict[str, List[Callable]] = {}
        return cls._instance
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe a callback to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
            
    def unsubscribe(self, event_type: str, callback: Callable):
        """Remove a callback from an event type."""
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            
    async def publish(self, event_type: str, data: Any = None):
        """
        Publish an event asynchronously.
        All subscribed callbacks will be executed concurrently.
        """
        if event_type not in self.subscribers:
            return
            
        callbacks = self.subscribers[event_type]
        # Run all callbacks concurrently
        await asyncio.gather(*(callback(data) for callback in callbacks))

# Global instance
bus = EventBus()

# Defined Event Constants
class Events:
    QUIZ_COMPLETED = "quiz_completed"
    TOPIC_MASTERY_UPDATED = "topic_mastery_updated"
    CONCEPT_MASTERED = "concept_mastered"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    SCHEDULE_UPDATED = "schedule_updated"
    USER_GOAL_UPDATED = "user_goal_updated"
