"""Strategies for finding and clearing walls blocking corridors or factories."""

from typing import Tuple, List, Optional
from agent.state import Robot, ObsState
from memory.map_memory import MapMemory
from utils.walls import is_fixed_wall

def find_blocking_walls_for_factory(
    factory: Robot,
    map_memory: MapMemory,
    south_bound: int,
    north_bound: int,
    width: int
) -> List[Tuple[int, int]]:
    """Find coordinates of walls directly blocking the factory's migration path.
    
    Checks rows ahead of the factory in the same column or adjacent columns.
    """
    blocking_positions = []
    fx, fy = factory.pos
    
    # Check cells directly north of the factory
    for r in range(fy + 1, min(fy + 5, north_bound + 1)):
        pos = (fx, r)
        w = map_memory.get_wall_value(pos)
        if w == -1 or w != 0:  # Has walls or undiscovered
            blocking_positions.append(pos)
            
    # Also check slightly east/west of factory column for potential pathway clearings
    for r in range(fy + 1, min(fy + 3, north_bound + 1)):
        for dx in [-1, 1]:
            nx = fx + dx
            if 0 <= nx < width:
                pos = (nx, r)
                w = map_memory.get_wall_value(pos)
                if w == -1 or w != 0:
                    blocking_positions.append(pos)
                    
    return blocking_positions
