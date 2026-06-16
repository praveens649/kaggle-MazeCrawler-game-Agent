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
    current_step: int,
    dp_action: Optional[str] = None
) -> str:
    """Determine the action for the factory.
    
    Priority 1: Emergency Jump or Trap Escape Evasion of scroll boundary.
    Priority 2: Movement Escape Check / Scroll Buffer Migration.
    Priority 3: Unit Spawning Check (BUILD_SCOUT, BUILD_WORKER, BUILD_MINER).
    Priority 4: Fallback Migration / Smart Jumps to bypass blocking walls.
    """
    fx, fy = factory.pos
    is_near_scroll = factory.row <= south_bound + 5

    # 1. Emergency Jump Check (Highest priority survival check)
    is_imminent_danger = factory.row <= predict_future_boundary(current_step, south_bound, 3)
    
    if is_imminent_danger and factory.jump_cd == 0:
        # Evaluate jump directions. Jump leaps 2 cells, ignoring walls.
        for dx, dy, direction in [(0, 1, "NORTH"), (1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
            landing_col = fx + dx * 2
            landing_row = fy + dy * 2
            
            if is_in_bounds(landing_col, landing_row, width, south_bound + 1, north_bound):
                future_sb = predict_future_boundary(current_step, south_bound, 6)
                if landing_row > future_sb:
                    w_landing = map_memory.get_wall_value((landing_col, landing_row))
                    if w_landing != -1 and w_landing != 15: # Not solid wall
                        return f"JUMP_{direction}"

    # 1.5 Multi-directional Trap Escape Jump (If factory is completely trapped by walls)
    has_passable_move = False
    for dx, dy in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
        neighbor = (fx + dx, fy + dy)
        if is_in_bounds(neighbor[0], neighbor[1], width, south_bound, north_bound):
            if map_memory.is_passable(factory.pos, neighbor):
                has_passable_move = True
                break

    if not has_passable_move and factory.jump_cd == 0:
        for dx, dy, direction in [(0, 1, "NORTH"), (1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
            landing_col = fx + dx * 2
            landing_row = fy + dy * 2
            if is_in_bounds(landing_col, landing_row, width, south_bound + 1, north_bound):
                w_landing = map_memory.get_wall_value((landing_col, landing_row))
                if w_landing != -1 and w_landing != 15:
                    return f"JUMP_{direction}"

    # 1.6 Smart Jump North to bypass horizontal wall blocks
    if factory.jump_cd == 0:
        north_pos = (fx, fy + 1)
        if not map_memory.is_passable(factory.pos, north_pos):
            landing = (fx, fy + 2)
            if is_in_bounds(landing[0], landing[1], width, south_bound + 1, north_bound):
                w_landing = map_memory.get_wall_value(landing)
                if w_landing != -1 and w_landing != 15:
                    future_sb = predict_future_boundary(current_step, south_bound, 6)
                    if landing[1] > future_sb:
                        return "JUMP_NORTH"

    # 2. Movement Escape Check / Scroll Buffer Migration
    if factory.move_cd == 0 and len(escape_path) > 1:
        next_step = escape_path[1]
        direction = get_direction_from_offset(factory.pos, next_step)
        if direction != "IDLE" and map_memory.is_passable(factory.pos, next_step):
            # If we are close to scroll (<= 5 rows buffer) or have no build option, move North.
            is_near_scroll = factory.row <= south_bound + 5
            if is_near_scroll or spawn_decision is None or factory.build_cd > 0:
                return direction

    # 2.5 Spawn Block Evasion
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
    should_spawn = (not is_near_scroll) or (factory.move_cd > 0)
    if should_spawn and spawn_decision is not None and factory.build_cd == 0:
        spawn_pos = (factory.col, factory.row + 1)
        cost = config.scout_cost if spawn_decision == 1 else config.worker_cost if spawn_decision == 2 else config.miner_cost
        
        if factory.energy >= cost:
            if (spawn_pos[1] <= north_bound 
                    and map_memory.is_passable(factory.pos, spawn_pos)
                    and not is_spawn_pocket_trapped(spawn_pos, factory.pos, map_memory, width, south_bound, north_bound)):
                if spawn_decision == 1:
                    return "BUILD_SCOUT"
                elif spawn_decision == 2:
                    return "BUILD_WORKER"
                elif spawn_decision == 3:
                    return "BUILD_MINER"

    # 4. Fallback Migration (Factory DP Path Optimizer or standard move North)
    if dp_action is not None and dp_action != "IDLE":
        if "JUMP" in dp_action and factory.jump_cd == 0:
            return dp_action
        elif "JUMP" not in dp_action and factory.move_cd == 0:
            return dp_action

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

    # Near scroll spawn fallback
    if is_near_scroll and spawn_decision is not None and factory.build_cd == 0:
        spawn_pos = (factory.col, factory.row + 1)
        cost = config.scout_cost if spawn_decision == 1 else config.worker_cost if spawn_decision == 2 else config.miner_cost
        if factory.energy >= cost:
            if (spawn_pos[1] <= north_bound 
                    and map_memory.is_passable(factory.pos, spawn_pos)
                    and not is_spawn_pocket_trapped(spawn_pos, factory.pos, map_memory, width, south_bound, north_bound)):
                if spawn_decision == 1:
                    return "BUILD_SCOUT"
                elif spawn_decision == 2:
                    return "BUILD_WORKER"
                elif spawn_decision == 3:
                    return "BUILD_MINER"

    return "IDLE"

