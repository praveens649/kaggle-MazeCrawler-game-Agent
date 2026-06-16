"""Task representation and assignment manager for Crawl robots."""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, Any

# Task Types
TASK_EXPLORE = "EXPLORE"
TASK_COLLECT_CRYSTAL = "COLLECT_CRYSTAL"
TASK_GO_TO_MINING_NODE = "GO_TO_MINING_NODE"
TASK_RETURN_TO_FACTORY = "RETURN_TO_FACTORY"
TASK_REMOVE_WALL = "REMOVE_WALL"
TASK_ESCAPE_SCROLL = "ESCAPE_SCROLL"
TASK_IDLE = "IDLE"

@dataclass
class Task:
    name: str
    target_pos: Optional[Tuple[int, int]] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class TaskAssignmentManager:
    """Tracks and updates task assignments for active robots."""
    
    def __init__(self):
        # uid -> Task
        self.assignments: Dict[str, Task] = {}

    def assign(self, uid: str, task: Task):
        """Assign a task to a robot."""
        self.assignments[uid] = task

    def get_task(self, uid: str) -> Task:
        """Get the current task for a robot. Defaults to IDLE."""
        return self.assignments.get(uid, Task(TASK_IDLE))

    def clear_inactive_robots(self, active_uids: set):
        """Remove assignments for robots that no longer exist."""
        self.assignments = {uid: task for uid, task in self.assignments.items() if uid in active_uids}

    def clear(self):
        """Reset all assignments."""
        self.assignments.clear()
