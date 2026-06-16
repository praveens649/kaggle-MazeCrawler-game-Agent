"""Miner decision making and action generation."""

from typing import Tuple, Set, Optional
from agent.state import Robot, GameConfig
from strategy.task_assignment import Task
from memory.map_memory import MapMemory
from economy.mining_logic import should_transform
from pathfinding.bfs import find_shortest_path
from utils.geometry import get_direction_from_offset

def get_miner_action(
    miner: Robot,
    task: Task,
    mining_nodes: Set[Tuple[int, int]],
    map_memory: MapMemory,
    enemy_memory,
    width: int,
    south_bound: int,
    north_bound: int,
    config: GameConfig,
    current_step: int
) -> str:
    """Determine action for a miner.
    
    Transforms into a mine if on a safe node, otherwise navigates to its assigned target node.
    """
    # 1. Transform check (requires no cooldown since it's a special action)
    if should_transform(miner, mining_nodes, south_bound, current_step, config):
        return "TRANSFORM"
        
    # 2. Movement Cooldown check
    if miner.move_cd > 0:
        return "IDLE"
        
    # 3. Path to target node or escape target
    target = task.target_pos
    if target is None:
        return get_fallback_miner_action(miner, map_memory, width, south_bound, north_bound)

    from pathfinding.astar import find_safe_path
    path = find_safe_path(
        start=miner.pos,
        goals={target},
        map_memory=map_memory,
        enemy_memory=enemy_memory,
        unit_type=3, # Miner
        current_step=current_step,
        width=width,
        south_bound=south_bound,
        north_bound=north_bound
    )
    
    if path and len(path) > 1:
        next_step = path[1]
        direction = get_direction_from_offset(miner.pos, next_step)
        if direction != "IDLE":
            return direction
            
    return get_fallback_miner_action(miner, map_memory, width, south_bound, north_bound)

def get_fallback_miner_action(
    miner: Robot,
    map_memory: MapMemory,
    width: int,
    south_bound: int,
    north_bound: int
) -> str:
    """Fallback action for miner if stuck: head north or wander."""
    x, y = miner.pos
    north_pos = (x, y + 1)
    if y + 1 <= north_bound and map_memory.is_passable(miner.pos, north_pos):
        return "NORTH"
        
    for dx, dy, direction in [(1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
        neighbor = (x + dx, y + dy)
        if 0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound:
            if map_memory.is_passable(miner.pos, neighbor):
                return direction
                
    return "IDLE"
