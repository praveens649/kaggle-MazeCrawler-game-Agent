"""A* pathfinder with support for weighted cost functions and dynamic safety constraints."""

import heapq
from typing import Dict, List, Tuple, Set, Optional, Callable
from utils.geometry import get_manhattan_distance

def find_path_astar(
    start: Tuple[int, int],
    goal: Tuple[int, int],
    is_passable_fn,  # Callable[[Tuple[int, int], Tuple[int, int]], bool]
    cost_fn,  # Callable[[Tuple[int, int], Tuple[int, int]], float]
    width: int,
    south_bound: int,
    north_bound: int
) -> Optional[List[Tuple[int, int]]]:
    """Find the optimal path from start to goal using A* search.
    
    cost_fn takes (from_pos, to_pos) and returns a float cost weight.
    """
    if start == goal:
        return [start]
        
    # Priority queue storing: (f_score, cost, x, y, path)
    open_set = []
    heapq.heappush(open_set, (get_manhattan_distance(start, goal), 0.0, start[0], start[1], [start]))
    
    # Store visited coordinates with their g_score (cost)
    g_score: Dict[Tuple[int, int], float] = {start: 0.0}
    
    while open_set:
        _, current_cost, x, y, path = heapq.heappop(open_set)
        curr = (x, y)
        
        if curr == goal:
            return path
            
        # If we found a cheaper way to get here since insertion, skip
        if current_cost > g_score.get(curr, float('inf')):
            continue
            
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            
            # Boundary check
            if not (0 <= nx < width and south_bound <= ny <= north_bound):
                continue
                
            if is_passable_fn(curr, neighbor):
                weight = cost_fn(curr, neighbor)
                tentative_g_score = current_cost + weight
                
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    g_score[neighbor] = tentative_g_score
                    f_score = tentative_g_score + get_manhattan_distance(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g_score, nx, ny, path + [neighbor]))
                    
    return None

def get_safe_cell_cost(
    from_pos: Tuple[int, int],
    to_pos: Tuple[int, int],
    current_step: int,
    south_bound: int,
    enemy_robots: dict,
    unit_type: int,
    influence_map = None
) -> float:
    """Calculate cell traversal cost prioritizing scroll boundary evasion and enemy avoidance.
    
    Crush rules: Factory > Miner > Worker > Scout.
    Same-type collisions are also mutually destructive.
    """
    cost = 1.0
    
    # 1. Proximity to scroll boundary (heavy exponential penalty for bottom rows)
    dist_to_scroll = to_pos[1] - south_bound
    if dist_to_scroll < 1:
        cost += 500.0  # Standing on the scroll boundary line is extremely dangerous
    elif dist_to_scroll < 2:
        cost += 200.0
    elif dist_to_scroll < 4:
        cost += (4 - dist_to_scroll) * 50.0
        
    # 2. Avoidance of enemy units
    for enemy in enemy_robots.values():
        e_pos = enemy.pos
        e_type = enemy.rtype
        
        # Determine if this enemy can destroy us (or same-type mutual annihilation)
        is_threat = False
        if unit_type == 0:  # If we are Factory
            if e_type == 0:  # Enemy factory is fatal
                is_threat = True
        else:  # For other units
            if e_type == unit_type:  # Same type (mutual destruction)
                is_threat = True
            elif e_type == 0:  # Factory crushes everyone
                is_threat = True
            elif e_type == 3 and unit_type in [1, 2]:  # Miner crushes Worker/Scout
                is_threat = True
            elif e_type == 2 and unit_type == 1:  # Worker crushes Scout
                is_threat = True
            
        if is_threat:
            # If directly on the cell, make it extremely costly (impassable)
            if to_pos == e_pos:
                cost += 5000.0
            # If adjacent to the cell, add a large penalty to prevent walking into its potential next step
            elif get_manhattan_distance(to_pos, e_pos) == 1:
                cost += 300.0
                
    # 3. Add influence map threat and attraction costs
    if influence_map is not None:
        threat = influence_map.get_threat(to_pos)
        attract = influence_map.get_attraction(to_pos)
        # Threat adds cost, attraction reduces cost (but not below 0.1 to avoid negative weights)
        cost += threat
        cost = max(0.1, cost - attract)
        
    return cost

def find_safe_path(
    start: Tuple[int, int],
    goals: Set[Tuple[int, int]],
    map_memory,  # MapMemory
    enemy_memory,  # EnemyMemory
    unit_type: int,
    current_step: int,
    width: int,
    south_bound: int,
    north_bound: int,
    influence_map = None
) -> Optional[List[Tuple[int, int]]]:
    """Find a path using A* that minimizes danger from the scroll and enemy units."""
    if not goals:
        return None
        
    if start in goals:
        return [start]
        
    def is_passable_fn(f, t):
        return map_memory.is_passable(f, t)
        
    def cost_fn(f, t):
        return get_safe_cell_cost(f, t, current_step, south_bound, enemy_memory.enemy_robots, unit_type, influence_map)
        
    # Sort goals by Manhattan distance to the start cell
    sorted_goals = list(goals)
    sorted_goals.sort(key=lambda g: get_manhattan_distance(start, g))
    
    # Try finding path to the nearest goals first
    for goal in sorted_goals:
        path = find_path_astar(
            start=start,
            goal=goal,
            is_passable_fn=is_passable_fn,
            cost_fn=cost_fn,
            width=width,
            south_bound=south_bound,
            north_bound=north_bound
        )
        if path:
            return path
            
    return None
