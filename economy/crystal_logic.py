"""Logic for targeting and gathering energy crystals."""

from typing import Dict, Tuple, List, Set, Optional
from agent.state import Robot
from pathfinding.bfs import find_shortest_path
from memory.map_memory import MapMemory
from utils.geometry import get_manhattan_distance

def assign_crystal_targets(
    scouts: List[Robot],
    crystals: Dict[Tuple[int, int], int],
    map_memory: MapMemory,
    enemy_robots: Dict[str, Robot],
    my_factory: Robot,
    current_step: int,
    width: int,
    south_bound: int,
    north_bound: int
) -> Dict[str, Tuple[int, int]]:
    """Smartly assign scouts to the nearest available safe crystals.
    
    Filters:
    1. Home side: Restricts scouts to columns on our half of the board in early/mid game.
    2. Path Reachability: Uses BFS to verify the crystal is reachable through known space.
    3. Enemy Threat: Skips crystals close to enemy units or closer to them than us.
    """
    assignments: Dict[str, Tuple[int, int]] = {}
    if not scouts or not crystals:
        return assignments

    available_crystals = set(crystals.keys())
    
    # Identify our home side column range
    is_left_side = my_factory.col < (width // 2)
    home_cols = range(0, width // 2) if is_left_side else range(width // 2, width)
    
    for scout in scouts:
        if not available_crystals:
            break
            
        best_crystal = None
        best_dist = float('inf')
        
        for crystal_pos in available_crystals:
            cx, cy = crystal_pos
            # 1. Skip crystals below the south bound
            if cy <= south_bound:
                continue
                
            # 2. Territorial constraint (early/mid game, step < 300)
            if current_step < 300 and cx not in home_cols:
                continue
                
            # 3. Enemy threat checks
            is_threatened = False
            for enemy in enemy_robots.values():
                e_dist = get_manhattan_distance(enemy.pos, crystal_pos)
                # If an enemy is adjacent or on it, or closer to it than our scout, skip
                if e_dist <= 1 or e_dist < get_manhattan_distance(scout.pos, crystal_pos):
                    is_threatened = True
                    break
            if is_threatened:
                continue
                
            # 4. Path reachability and distance check
            is_passable_fn = lambda f, t: map_memory.is_passable(f, t)
            path = find_shortest_path(
                start=scout.pos,
                goals={crystal_pos},
                is_passable_fn=is_passable_fn,
                width=width,
                south_bound=south_bound,
                north_bound=north_bound
            )
            if path is None:
                continue # Unreachable by known path
                
            path_dist = len(path) - 1
            if path_dist < best_dist:
                best_dist = path_dist
                best_crystal = crystal_pos
                
        if best_crystal is not None:
            assignments[scout.uid] = best_crystal
            available_crystals.remove(best_crystal)
            
    return assignments
