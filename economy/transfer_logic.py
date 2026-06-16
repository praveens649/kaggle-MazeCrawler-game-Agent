"""Logic for scheduling energy transfers between adjacent friendly robots."""

from typing import Dict, Tuple, List, Optional, Set
from agent.state import Robot, ObsState, GameConfig
from memory.map_memory import MapMemory
from strategy.survival_strategy import predict_future_boundary
from utils.geometry import get_manhattan_distance, get_direction_from_offset

def find_transfer_opportunities(
    obs: ObsState,
    map_memory: MapMemory,
    config: GameConfig,
    current_step: int
) -> Dict[str, str]:
    """Find all valid energy transfer opportunities between adjacent friendly robots.
    
    Priority 1: Emergency transfer (if a robot is about to scroll-die and has an adjacent safe friendly).
    Priority 2: Logistical transfer (scouts/workers/miners adjacent to the factory transferring excess energy).
    
    Returns:
        Dict mapping robot_uid -> action_string (e.g. "TRANSFER_NORTH")
    """
    actions: Dict[str, str] = {}
    my_robots = obs.my_robots
    
    # Predict if units are about to die from scroll next turn
    is_dead_next_turn = {}
    next_sb = predict_future_boundary(current_step, obs.south_bound, 1)
    
    for uid, robot in my_robots.items():
        is_dead_next_turn[uid] = robot.row <= next_sb

    # Helper to find adjacent friendly robots not blocked by walls
    def get_passable_friendly_neighbors(robot: Robot) -> List[Robot]:
        neighbors = []
        for other_uid, other in my_robots.items():
            if other_uid == robot.uid:
                continue
            if get_manhattan_distance(robot.pos, other.pos) == 1:
                # Check if movement/transfer is passable (no walls between them)
                if map_memory.is_passable(robot.pos, other.pos):
                    neighbors.append(other)
        return neighbors

    # 1. Emergency Transfers
    for uid, robot in my_robots.items():
        if robot.rtype == 0:  # Factory doesn't scroll-die easily and shouldn't transfer
            continue
        if robot.energy <= 1:  # Not enough energy to make a difference
            continue
            
        if is_dead_next_turn[uid]:
            # Find an adjacent neighbor that is NOT dead next turn
            neighbors = get_passable_friendly_neighbors(robot)
            safe_neighbors = [n for n in neighbors if not is_dead_next_turn[n.uid]]
            
            if safe_neighbors:
                # Target the neighbor that has room or the factory (which has infinite capacity)
                # Sort: factories first, then units with lowest current energy
                safe_neighbors.sort(key=lambda n: (0 if n.rtype == 0 else 1, n.energy))
                target = safe_neighbors[0]
                direction = get_direction_from_offset(robot.pos, target.pos)
                if direction != "IDLE":
                    actions[uid] = f"TRANSFER_{direction}"
                    
    # 2. Logistical Transfers (from robots to factory)
    # If scout/worker/miner is adjacent to factory and has excess energy, transfer it
    factory = None
    for robot in my_robots.values():
        if robot.rtype == 0:
            factory = robot
            break
            
    if factory is not None:
        for uid, robot in my_robots.items():
            if uid in actions:  # Already doing emergency transfer
                continue
            if robot.rtype == 0:
                continue
                
            # If adjacent to factory and has collected significant energy
            if get_manhattan_distance(robot.pos, factory.pos) == 1:
                # Check if we should dump energy to factory
                should_dump = False
                if robot.rtype == 1 and robot.energy > 80:  # Scout almost full
                    should_dump = True
                elif robot.rtype == 2 and robot.energy > 250:  # Worker almost full
                    should_dump = True
                elif robot.rtype == 3 and robot.energy > 400:  # Miner almost full
                    should_dump = True
                    
                if should_dump and map_memory.is_passable(robot.pos, factory.pos):
                    direction = get_direction_from_offset(robot.pos, factory.pos)
                    if direction != "IDLE":
                        actions[uid] = f"TRANSFER_{direction}"

    return actions
