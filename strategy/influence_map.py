"""Dynamic threat influence maps and resource attractiveness heatmaps."""

from typing import Dict, Tuple, Any
from agent.state import ObsState, GameConfig
from strategy.bayesian_predictor import BayesianResourcePredictor
from utils.geometry import get_manhattan_distance

class InfluenceMap:
    def __init__(self):
        self.threat_map: Dict[Tuple[int, int], float] = {}
        self.attraction_map: Dict[Tuple[int, int], float] = {}

    def compute(
        self,
        obs: ObsState,
        config: GameConfig,
        predictor: BayesianResourcePredictor,
        south_bound: int,
        north_bound: int
    ):
        """Compute threat and attraction fields on the active grid area."""
        self.threat_map.clear()
        self.attraction_map.clear()
        
        width = config.width
        my_factory = obs.my_factory
        
        # 1. Threat Map Generation
        # Enemy units project threat fields (decays exponentially with Manhattan distance)
        for enemy in obs.enemy_robots.values():
            ex, ey = enemy.pos
            e_type = enemy.rtype
            
            # Determine base threat power based on unit type
            # Factory and Miners are highly threatening
            if e_type == 0:
                base_threat = 500.0
                threat_range = 5
            elif e_type == 3:
                base_threat = 300.0
                threat_range = 4
            elif e_type == 2:
                base_threat = 150.0
                threat_range = 3
            else:  # Scout
                base_threat = 80.0
                threat_range = 2
                
            # Populate threat field around enemy
            for dx in range(-threat_range, threat_range + 1):
                for dy in range(-threat_range, threat_range + 1):
                    dist = abs(dx) + abs(dy)
                    if dist <= threat_range:
                        tx, ty = ex + dx, ey + dy
                        if 0 <= tx < width and south_bound <= ty <= north_bound:
                            # Exponential decay: threat = base * (0.5 ^ dist)
                            threat_val = base_threat * (0.5 ** dist)
                            self.threat_map[(tx, ty)] = self.threat_map.get((tx, ty), 0.0) + threat_val

        # 2. Attraction/Heatmap Map Generation
        # Known crystals and mining nodes project positive attraction fields
        for pos, energy in obs.crystals.items():
            cx, cy = pos
            base_attract = float(energy) * 5.0
            self._apply_attraction(cx, cy, base_attract, 4, width, south_bound, north_bound)
            
        for pos in obs.mining_nodes:
            nx, ny = pos
            self._apply_attraction(nx, ny, 100.0, 3, width, south_bound, north_bound)

        # Apply predicted resource attraction from Bayesian Predictor for unexplored cells
        # Only check a window near the factory and active scouts
        for y in range(south_bound, north_bound + 1):
            for x in range(width):
                pos = (x, y)
                prob = predictor.predict_resource_probability(pos, config, obs)
                if prob > 0.1:
                    base_attract = prob * 30.0
                    self.attraction_map[pos] = self.attraction_map.get(pos, 0.0) + base_attract

    def _apply_attraction(
        self,
        cx: int,
        cy: int,
        base_value: float,
        radius: int,
        width: int,
        south_bound: int,
        north_bound: int
    ):
        """Helper to spread attraction values around a center cell."""
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                dist = abs(dx) + abs(dy)
                if dist <= radius:
                    tx, ty = cx + dx, cy + dy
                    if 0 <= tx < width and south_bound <= ty <= north_bound:
                        attract_val = base_value * (0.6 ** dist)
                        self.attraction_map[(tx, ty)] = self.attraction_map.get((tx, ty), 0.0) + attract_val

    def get_threat(self, pos: Tuple[int, int]) -> float:
        """Get the threat influence value at pos."""
        return self.threat_map.get(pos, 0.0)

    def get_attraction(self, pos: Tuple[int, int]) -> float:
        """Get the resource attraction value at pos."""
        return self.attraction_map.get(pos, 0.0)
