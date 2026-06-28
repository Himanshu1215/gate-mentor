import logging
from typing import List, Dict

from learning.concept_drift import ConceptDriftEngine
from analytics.advanced_metrics import AdvancedMetrics
from planner.goal_engine import GoalEngine

logger = logging.getLogger(__name__)

class AutonomousCoach:
    """Background daemon that proactively monitors the user and generates alerts."""
    
    @staticmethod
    def run_health_check() -> List[Dict[str, str]]:
        """
        Runs a full check across drift, calibration, and goals.
        Returns a list of push notifications/alerts for the UI.
        """
        alerts = []
        
        # 1. Check Concept Drift
        drifted = ConceptDriftEngine.apply_drift()
        if drifted:
            alerts.append({
                "type": "WARNING",
                "title": "Memory Decay Detected",
                "message": f"Your mastery degraded in {len(drifted)} topics due to lack of revision. They have been added to your daily schedule."
            })
            
        # 2. Check Confidence Calibration
        calibration = AdvancedMetrics.calculate_confidence_calibration()
        if "Overconfident" in calibration["status"]:
            alerts.append({
                "type": "CRITICAL",
                "title": "High Risk of Negative Marks",
                "message": f"You are highly confident but incorrect on {calibration['overconfident_rate']}% of questions. Slow down and read carefully."
            })
            
        # 3. Check Goal Trajectory
        goals = GoalEngine.get_current_projection()
        if goals["risk_level"] == "High":
            alerts.append({
                "type": "INFO",
                "title": "AIR Projection Dropping",
                "message": f"Your projected AIR is currently {goals['projected_air']}. You need to increase your accuracy to bring this down."
            })
            
        if not alerts:
            alerts.append({
                "type": "SUCCESS",
                "title": "On Track",
                "message": "All metrics look great. Keep up the good work!"
            })
            
        return alerts

if __name__ == "__main__":
    notifications = AutonomousCoach.run_health_check()
    for n in notifications:
        print(f"[{n['type']}] {n['title']}: {n['message']}")
