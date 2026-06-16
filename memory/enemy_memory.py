"""Enemy state memory and tracking for the Crawl AI Agent."""

from typing import Dict, Tuple, Optional
from agent.state import ObsState, Robot

class EnemyMemory:
    def __init__(self):
        # uid -> Robot (last seen state)
        self.enemy_robots: Dict[str, Robot] = {}
        # Last known enemy factory position
        self.last_known_factory_pos: Optional[Tuple[int, int]] = None
        # Step when factory was last seen
        self.factory_last_seen_step: int = 0

    def update(self, obs: ObsState, current_step: int):
        """Update enemy memory based on currently visible units."""
        south = obs.south_bound
        
        # 1. Remove enemy units that are below the southern scroll limit
        self.enemy_robots = {
            uid: r for uid, r in self.enemy_robots.items()
            if r.pos[1] >= south
        }
        
        # 2. Update visible units
        for uid, robot in obs.enemy_robots.items():
            self.enemy_robots[uid] = robot
            if robot.rtype == 0:  # Factory
                self.last_known_factory_pos = robot.pos
                self.factory_last_seen_step = current_step

        # 3. Fallback/Estimate enemy factory if not visible
        # Since the factory cannot fall behind south bound, if it was seen below south bound, push it up
        if self.last_known_factory_pos is not None:
            col, row = self.last_known_factory_pos
            if row < south:
                # Factory must have moved north to survive, estimate it at least at south + 1
                self.last_known_factory_pos = (col, south + 1)
                
    def get_estimated_enemy_factory_pos(self, south_bound: int) -> Tuple[int, int]:
        """Get the estimated position of the enemy factory.
        
        If never seen, default to opposite side at south_bound + 2.
        """
        if self.last_known_factory_pos is not None:
            # Clamp to at least south_bound + 1 to avoid predicting scroll death
            col, row = self.last_known_factory_pos
            return (col, max(row, south_bound + 1))
            
        # Default fallback (e.g. if we are player 0, start on left, enemy starts on right)
        # Assuming width = 20, enemy starts around col = 15, row = south_bound + 2
        return (15, south_bound + 2)
