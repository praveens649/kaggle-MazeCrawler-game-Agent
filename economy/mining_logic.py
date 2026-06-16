"""Logic for targeting mining nodes and transforming miners into mines."""

from typing import Dict, Tuple, List, Set, Optional
from agent.state import Robot, GameConfig
from strategy.survival_strategy import predict_future_boundary
from utils.geometry import get_manhattan_distance
from pathfinding.bfs import compute_bfs_distances
from memory.map_memory import MapMemory

def should_transform(
    miner: Robot,
    mining_nodes: Set[Tuple[int, int]],
    south_bound: int,
    current_step: int,
    config: GameConfig
) -> bool:
    """Determine if a miner should transform into a mine.
    
    Conditions:
    1. Miner is on a mining node.
    2. Miner has enough energy for the transform cost.
    3. The mine is predicted to survive long enough to recoup the investment (at least 20 steps).
    """
    if miner.pos not in mining_nodes:
        return False
        
    if miner.energy < config.transform_cost:
        return False
        
    # Recouping cost requires the mine to generate energy.
    future_sb = predict_future_boundary(current_step, south_bound, 20)
    if miner.pos[1] <= future_sb:
        return False
        
    return True

def assign_mining_nodes(
    miners: List[Robot],
    mining_nodes: Set[Tuple[int, int]],
    map_memory: MapMemory,
    enemy_robots: Dict[str, Robot],
    my_factory: Robot,
    south_bound: int,
    north_bound: int,
    current_step: int,
    width: int
) -> Dict[str, Tuple[int, int]]:
    """Smartly assign miners to the nearest safe, reachable, and non-threatened mining nodes."""
    assignments: Dict[str, Tuple[int, int]] = {}
    if not miners or not mining_nodes:
        return assignments

    # Filter for nodes that are safe to mine (predicted to survive at least 25 turns)
    safe_nodes = {
        node for node in mining_nodes 
        if node[1] > predict_future_boundary(current_step, south_bound, 25)
    }
    
    # Identify our home side column range
    is_left_side = my_factory.col < (width // 2)
    home_cols = range(0, width // 2) if is_left_side else range(width // 2, width)
    
    is_passable_fn = lambda f, t: map_memory.is_passable(f, t)
    
    for miner in miners:
        if not safe_nodes:
            break
            
        best_node = None
        best_dist = float('inf')
        
        # Compute distances from this miner to all cells in a single BFS pass
        distances = compute_bfs_distances(
            start=miner.pos,
            is_passable_fn=is_passable_fn,
            width=width,
            south_bound=south_bound,
            north_bound=north_bound
        )
        
        for node in safe_nodes:
            nx, ny = node
            
            # 1. Territorial constraint (early/mid game, step < 300)
            if current_step < 300 and nx not in home_cols:
                continue
                
            # 2. Enemy threat check (skip if enemy unit is very close to node)
            is_threatened = False
            for enemy in enemy_robots.values():
                e_dist = get_manhattan_distance(enemy.pos, node)
                # Factory or any enemy unit standing next to the node makes it hazardous
                if e_dist <= 2:
                    is_threatened = True
                    break
            if is_threatened:
                continue
                
            # 3. Distance check using pre-computed BFS distance map
            path_dist = distances.get(node, float('inf'))
            if path_dist < best_dist:
                best_dist = path_dist
                best_node = node
                
        if best_node is not None:
            assignments[miner.uid] = best_node
            safe_nodes.remove(best_node)
            
    return assignments

