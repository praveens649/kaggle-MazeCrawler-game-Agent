"""Strategic wall construction coordination for workers."""

from typing import Tuple, List, Set, Optional
from agent.state import Robot, ObsState
from memory.map_memory import MapMemory
from utils.walls import is_fixed_wall

def find_chokepoint_wall_targets(
    obs: ObsState,
    map_memory: MapMemory,
    width: int
) -> List[Tuple[Tuple[int, int], str]]:
    """Identify adjacent cells where workers can build walls to separate board halves.
    
    Returns:
        List of ((col, row), direction) targets.
    """
    targets = []
    south = obs.south_bound
    north = obs.north_bound
    
    # Simple strategy: try to wall off corridors near the mirror axis to prevent intrusions
    mid_left = width // 2 - 1
    mid_right = width // 2
    
    for row in range(south + 1, north):
        # Workers can try to seal off columns adjacent to the mirror axis
        for col in [mid_left - 1, mid_right + 1]:
            pos = (col, row)
            if pos in map_memory.discovered_cells:
                # Try to build north or south walls to create chokepoints
                for direction in ["NORTH", "EAST", "WEST"]:
                    if not is_fixed_wall(col, direction, width):
                        # Verify there is no wall yet
                        w = map_memory.get_wall_value(pos)
                        if w != -1:
                            bit = 1 if direction == "NORTH" else 2 if direction == "EAST" else 8
                            if not (w & bit):
                                targets.append((pos, direction))
                                
    return targets
