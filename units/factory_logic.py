"""Factory action coordination, unit building, and scroll evasion."""

from typing import Tuple, List, Optional
from agent.state import Robot, GameConfig
from memory.map_memory import MapMemory
from strategy.survival_strategy import predict_future_boundary
from utils.geometry import get_direction_from_offset, get_manhattan_distance
from utils.geometry import is_in_bounds

def is_spawn_pocket_trapped(
    spawn_pos: Tuple[int, int],
    factory_pos: Tuple[int, int],
    map_memory: MapMemory,
    width: int,
    south_bound: int,
    north_bound: int
) -> bool:
    """Check if the spawn cell is a dead-end pocket (no exits other than back to factory)."""
    exits = 0
    col, row = spawn_pos
    for dx, dy in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
        neighbor = (col + dx, row + dy)
        if neighbor == factory_pos:
            continue
        if is_in_bounds(neighbor[0], neighbor[1], width, south_bound, north_bound):
            if map_memory.is_passable(spawn_pos, neighbor):
                exits += 1
    return exits == 0

def get_factory_action(
    factory: Robot,
    spawn_decision: Optional[int],
    escape_path: List[Tuple[int, int]],
    map_memory: MapMemory,
    width: int,
    south_bound: int,
    north_bound: int,
    config: GameConfig,
    current_step: int
) -> str:
    """Determine the action for the factory.
    
    Priority 1: Evasion of scroll boundary via movements or jumps.
    Priority 2: Unit spawning (BUILD_SCOUT, BUILD_WORKER, BUILD_MINER).
    Priority 3: Fallback migrations.
    """
    # 1. Emergency Jump Check (Highest priority survival check)
    # If the factory is within 2 cells of the predicted scroll line in 2 turns, and jump is available
    is_imminent_danger = factory.row <= predict_future_boundary(current_step, south_bound, 3)
    
    if is_imminent_danger and factory.jump_cd == 0:
        # Evaluate jump directions. Jump leaps 2 cells, ignoring walls.
        # Check North, then East, then West, then South
        for dx, dy, direction in [(0, 1, "NORTH"), (1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
            landing_col = factory.col + dx * 2
            landing_row = factory.row + dy * 2
            
            # Must land in bounds
            if is_in_bounds(landing_col, landing_row, width, south_bound + 1, north_bound):
                # Check if landing cell is safe from scroll in 6 turns
                future_sb = predict_future_boundary(current_step, south_bound, 6)
                if landing_row > future_sb:
                    # Check if landing cell is not a wall itself (though we can jump over walls, 
                    # landing inside a wall isn't possible/passable in normal movement later)
                    w_landing = map_memory.get_wall_value((landing_col, landing_row))
                    if w_landing != -1 and w_landing != 15: # Not fully enclosed wall block if known
                        return f"JUMP_{direction}"

    # 2. Movement Escape Check
    # If factory can move, and we have an escape path
    if factory.move_cd == 0 and len(escape_path) > 1:
        next_step = escape_path[1]
        direction = get_direction_from_offset(factory.pos, next_step)
        if direction != "IDLE" and map_memory.is_passable(factory.pos, next_step):
            return direction

    # 2.5 Spawn Block Evasion
    # If we want to build but the spawn position (North) is blocked, try moving to an adjacent cell that has a clear spawn space.
    if spawn_decision is not None and factory.build_cd == 0 and factory.move_cd == 0:
        spawn_pos = (factory.col, factory.row + 1)
        cost = config.scout_cost if spawn_decision == 1 else config.worker_cost if spawn_decision == 2 else config.miner_cost
        if factory.energy >= cost:
            is_spawn_blocked = (
                spawn_pos[1] > north_bound 
                or not map_memory.is_passable(factory.pos, spawn_pos)
                or is_spawn_pocket_trapped(spawn_pos, factory.pos, map_memory, width, south_bound, north_bound)
            )
            if is_spawn_blocked:
                # Try moving EAST, WEST, or SOUTH to clear spawn block
                for dx, dy, direction in [(1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
                    neighbor = (factory.col + dx, factory.row + dy)
                    if is_in_bounds(neighbor[0], neighbor[1], width, south_bound + 1, north_bound):
                        if map_memory.is_passable(factory.pos, neighbor):
                            neighbor_spawn = (neighbor[0], neighbor[1] + 1)
                            if (neighbor_spawn[1] <= north_bound 
                                    and map_memory.is_passable(neighbor, neighbor_spawn)
                                    and not is_spawn_pocket_trapped(neighbor_spawn, neighbor, map_memory, width, south_bound, north_bound)):
                                return direction

    # 3. Unit Spawning Check
    # Spawn decision is active and factory has energy + cooldown is ready
    if spawn_decision is not None and factory.build_cd == 0:
        spawn_pos = (factory.col, factory.row + 1)
        cost = config.scout_cost if spawn_decision == 1 else config.worker_cost if spawn_decision == 2 else config.miner_cost
        
        if factory.energy >= cost:
            # Check if there is a wall blocking the spawn cell (North of factory)
            # In addition, spawn pos must be in bounds
            if (spawn_pos[1] <= north_bound 
                    and map_memory.is_passable(factory.pos, spawn_pos)
                    and not is_spawn_pocket_trapped(spawn_pos, factory.pos, map_memory, width, south_bound, north_bound)):
                if spawn_decision == 1:
                    return "BUILD_SCOUT"
                elif spawn_decision == 2:
                    return "BUILD_WORKER"
                elif spawn_decision == 3:
                    return "BUILD_MINER"

    # 4. Fallback Migration (Factory moves North by default if cooldown is ready)
    if factory.move_cd == 0:
        # Try North
        north_pos = (factory.col, factory.row + 1)
        if north_pos[1] <= north_bound and map_memory.is_passable(factory.pos, north_pos):
            return "NORTH"
            
        # Try East/West
        for dx, direction in [(1, "EAST"), (-1, "WEST")]:
            neighbor = (factory.col + dx, factory.row)
            if 0 <= neighbor[0] < width and map_memory.is_passable(factory.pos, neighbor):
                return direction
                
        # If completely trapped, and jump cooldown is ready, jump North as escape
        if factory.jump_cd == 0:
            landing_col = factory.col
            landing_row = factory.row + 2
            if is_in_bounds(landing_col, landing_row, width, south_bound + 1, north_bound):
                return "JUMP_NORTH"

    return "IDLE"
