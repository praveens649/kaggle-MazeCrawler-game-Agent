"""Worker decision making, action generation, and wall manipulation."""

from typing import Tuple, List, Set, Optional
from agent.state import Robot, GameConfig
from strategy.task_assignment import Task
from memory.map_memory import MapMemory
from pathfinding.bfs import find_shortest_path
from utils.geometry import get_manhattan_distance, get_direction_from_offset
from utils.walls import is_fixed_wall

def get_worker_action(
    worker: Robot,
    task: Task,
    map_memory: MapMemory,
    enemy_memory,
    current_step: int,
    width: int,
    south_bound: int,
    north_bound: int,
    config: GameConfig
) -> str:
    """Determine action for a worker.
    
    Can remove walls adjacent to it if assigned REMOVE_WALL, or navigates to safe zones / factory.
    """
    # 1. Action Check: if adjacent to wall target and task is REMOVE_WALL
    if task.name == "REMOVE_WALL" and task.target_pos is not None:
        target = task.target_pos
        dist = get_manhattan_distance(worker.pos, target)
        
        if dist == 1:
            # We are adjacent to the target cell where we want to clear the wall
            direction = get_direction_from_offset(worker.pos, target)
            
            # Check if there is actually a wall to remove
            w_val = map_memory.get_wall_value(worker.pos)
            # Or wall from target
            w_target_val = map_memory.get_wall_value(target)
            
            has_wall_to_remove = False
            if direction == "NORTH" and ((w_val != -1 and w_val & 1) or (w_target_val != -1 and w_target_val & 4)):
                has_wall_to_remove = True
            elif direction == "EAST" and ((w_val != -1 and w_val & 2) or (w_target_val != -1 and w_target_val & 8)):
                has_wall_to_remove = True
            elif direction == "SOUTH" and ((w_val != -1 and w_val & 4) or (w_target_val != -1 and w_target_val & 1)):
                has_wall_to_remove = True
            elif direction == "WEST" and ((w_val != -1 and w_val & 8) or (w_target_val != -1 and w_target_val & 2)):
                has_wall_to_remove = True
                
            if has_wall_to_remove and worker.energy >= config.wall_remove_cost:
                # Make sure we don't try to remove a fixed perimeter/axis wall
                if not is_fixed_wall(worker.col, direction, width):
                    return f"REMOVE_{direction}"

    # 2. Movement Cooldown check
    if worker.move_cd > 0:
        return "IDLE"
        
    # 3. Pathing to target
    target = task.target_pos
    if target is None:
        return get_fallback_worker_action(worker, map_memory, width, south_bound, north_bound)

    # If the task is REMOVE_WALL, our goal is to reach a cell adjacent to target.
    # So we search for a path to any neighbor of target.
    goals = {target}
    if task.name == "REMOVE_WALL":
        goals = set()
        tx, ty = target
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            n = (tx + dx, ty + dy)
            if 0 <= n[0] < width and south_bound <= n[1] <= north_bound:
                goals.add(n)
        # Add target itself as fallback
        if not goals:
            goals.add(target)

    from pathfinding.astar import find_safe_path
    path = find_safe_path(
        start=worker.pos,
        goals=goals,
        map_memory=map_memory,
        enemy_memory=enemy_memory,
        unit_type=2, # Worker
        current_step=current_step,
        width=width,
        south_bound=south_bound,
        north_bound=north_bound
    )
    
    if path and len(path) > 1:
        next_step = path[1]
        direction = get_direction_from_offset(worker.pos, next_step)
        if direction != "IDLE":
            return direction
            
    return get_fallback_worker_action(worker, map_memory, width, south_bound, north_bound)

def get_fallback_worker_action(
    worker: Robot,
    map_memory: MapMemory,
    width: int,
    south_bound: int,
    north_bound: int
) -> str:
    """Fallback action for worker if stuck: head north or wander."""
    x, y = worker.pos
    north_pos = (x, y + 1)
    if y + 1 <= north_bound and map_memory.is_passable(worker.pos, north_pos):
        return "NORTH"
        
    for dx, dy, direction in [(1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
        neighbor = (x + dx, y + dy)
        if 0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound:
            if map_memory.is_passable(worker.pos, neighbor):
                return direction
                
    return "IDLE"
