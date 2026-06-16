"""Logic for targeting mining nodes and transforming miners into mines."""

from typing import Dict, Tuple, List, Set, Optional
from agent.state import Robot, GameConfig
from strategy.survival_strategy import predict_future_boundary
from utils.geometry import get_manhattan_distance
from pathfinding.bfs import find_shortest_path
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
    """Smartly assign miners to the nearest safe, reachable, and non-threatened mining nodes using bipartite matching."""
    assignments: Dict[str, Tuple[int, int]] = {}
    if not miners or not mining_nodes:
        return assignments

    # Filter for nodes that are safe to mine (predicted to survive at least 25 turns)
    # AND don't already have active mines (belonging to us or enemy)
    safe_nodes = set()
    for node in mining_nodes:
        # Check if predicted to survive at least 25 turns
        if node[1] <= predict_future_boundary(current_step, south_bound, 25):
            continue

        # Check if there's already an active mine on this node (belonging to us or enemy)
        if node in map_memory.mines:
            mine = map_memory.mines[node]
            # Skip if there's already an active mine here (whether ours or enemy's)
            continue

        safe_nodes.add(node)

    # Identify our home side column range
    is_left_side = my_factory.col < (width // 2)
    home_cols = range(0, width // 2) if is_left_side else range(width // 2, width)

    # Generate all valid (miner, mining_node) pairs with their distances
    miner_node_pairs = []

    for miner in miners:
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

            # 3. Path reachability and distance check
            is_passable_fn = lambda f, t: map_memory.is_passable(f, t)
            path = find_shortest_path(
                start=miner.pos,
                goals={node},
                is_passable_fn=is_passable_fn,
                width=width,
                south_bound=south_bound,
                north_bound=north_bound
            )
            if path is None:
                continue  # Unreachable by known path

            path_dist = len(path) - 1
            # Store the pair with distance and references
            miner_node_pairs.append((path_dist, miner, node))

    # Sort pairs by distance (closest first)
    miner_node_pairs.sort(key=lambda x: x[0])

    # Greedily match pairs, ensuring each miner and node is used at most once
    matched_miners = set()
    matched_nodes = set()

    for distance, miner, node in miner_node_pairs:
        if miner.uid not in matched_miners and node not in matched_nodes:
            assignments[miner.uid] = node
            matched_miners.add(miner.uid)
            matched_nodes.add(node)

    return assignments
