"""Scout decision making and action generation."""

from typing import Tuple, List, Optional
from agent.state import Robot
from strategy.task_assignment import Task
from memory.map_memory import MapMemory
from pathfinding.bfs import find_shortest_path
from utils.geometry import get_direction_from_offset

def get_scout_action(
    scout: Robot,
    task: Task,
    map_memory: MapMemory,
    enemy_memory,
    current_step: int,
    width: int,
    south_bound: int,
    north_bound: int
) -> str:
    """Determine action for a scout based on its assigned task.
    
    Uses A* safe pathfinding to navigate towards the task's target position.
    """
    # 1. If we are on cooldown, we must stay idle
    if scout.move_cd > 0:
        return "IDLE"
        
    # 2. Check if we have a valid task and target position
    target = task.target_pos
    if target is None:
        # Fallback: explore north or idle
        return get_fallback_scout_action(scout, map_memory, width, south_bound, north_bound)

    # Calculate safe path using A*
    from pathfinding.astar import find_safe_path
    path = find_safe_path(
        start=scout.pos,
        goals={target},
        map_memory=map_memory,
        enemy_memory=enemy_memory,
        unit_type=1, # Scout
        current_step=current_step,
        width=width,
        south_bound=south_bound,
        north_bound=north_bound
    )
    
    if path and len(path) > 1:
        next_step = path[1]
        direction = get_direction_from_offset(scout.pos, next_step)
        if direction != "IDLE":
            return direction

    # Fallback if pathfinding fails or target reached
    return get_fallback_scout_action(scout, map_memory, width, south_bound, north_bound)

def get_fallback_scout_action(
    scout: Robot,
    map_memory: MapMemory,
    width: int,
    south_bound: int,
    north_bound: int
) -> str:
    """Fallback action if pathfinding fails: head north if passable, else choose random open direction."""
    x, y = scout.pos
    
    # Try North
    north_pos = (x, y + 1)
    if y + 1 <= north_bound and map_memory.is_passable(scout.pos, north_pos):
        return "NORTH"
        
    # Try East/West/South
    for dx, dy, direction in [(1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
        neighbor = (x + dx, y + dy)
        if 0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound:
            if map_memory.is_passable(scout.pos, neighbor):
                return direction
                
    return "IDLE"
