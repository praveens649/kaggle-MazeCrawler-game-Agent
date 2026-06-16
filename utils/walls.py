"""Wall decoding and check utilities for the Crawl AI Agent."""

from typing import Tuple, List
from agent.constants import DIR_TO_BIT, ALL_DIRECTIONS

def has_wall(wall_bitfield: int, direction: str) -> bool:
    """Check if the wall bitfield has a wall in the specified direction.
    
    If the bitfield is -1 (undiscovered), we treat it as unknown/wall for safety 
    or let higher-level systems decide. This function checks the bitmask directly.
    """
    if wall_bitfield == -1:
        return False  # Not checked here, handled by map memory/pathfinder
    bit = DIR_TO_BIT.get(direction, 0)
    return bool(wall_bitfield & bit)

def get_passable_directions(wall_bitfield: int) -> List[str]:
    """Get all directions that are not blocked by a wall in this bitfield.
    
    Assumes bitfield is valid (not -1).
    """
    if wall_bitfield == -1:
        return []
    passable = []
    for d in ALL_DIRECTIONS:
        if not has_wall(wall_bitfield, d):
            passable.append(d)
    return passable

def is_fixed_wall(col: int, direction: str, width: int) -> bool:
    """Check if a potential wall is a fixed perimeter wall or the central mirror axis.
    
    Fixed walls:
    - E/W of the leftmost (0) and rightmost (width-1) columns.
    - E of col = width // 2 - 1 and W of col = width // 2.
    """
    # Outer boundaries
    if col == 0 and direction == "WEST":
        return True
    if col == width - 1 and direction == "EAST":
        return True
    
    # Mirror axis
    mid_left = width // 2 - 1
    mid_right = width // 2
    if col == mid_left and direction == "EAST":
        return True
    if col == mid_right and direction == "WEST":
        return True
        
    return False
