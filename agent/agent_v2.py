"""Autonomous agent v2 implementing intelligent pathing, persistent memory, and target prioritization."""

from collections import deque
from typing import Dict, List, Tuple, Set, Optional, Any

from agent.state import ObsState, GameConfig, Robot
from agent.parser import parse_config, parse_obs
from memory.memory import GameMemory
from strategy.macro_strategy import MacroStrategy
from strategy.survival_strategy import SurvivalStrategy, predict_future_boundary
from combat.collision import resolve_friendly_collisions
from economy.transfer_logic import find_transfer_opportunities
from units.factory_logic import get_factory_action
from agent.agent import get_clear_gate_action
from utils.geometry import get_manhattan_distance, get_direction_from_offset, is_in_bounds
from debug.logger import StateLogger
from debug.visualizer import log_ascii_map

# Persistent states across steps
memory = GameMemory()
robot_states = {}  # uid -> {'target': pos, 'current_path': path, 'mode': mode}
current_step = 0
macro = MacroStrategy()
survival = SurvivalStrategy()


def update_memory(obs_state: ObsState, memory_obj: GameMemory, step: int):
    """Remember every discovered cell, update walls, resources, and visit counts."""
    # 1. Update standard map and enemy memories
    memory_obj.update(obs_state, step)

    # 2. Increment visit counts for cells currently occupied by our robots
    for robot in obs_state.my_robots.values():
        pos = robot.pos
        if pos not in memory_obj.map.visit_counts:
            memory_obj.map.visit_counts[pos] = 0
        memory_obj.map.visit_counts[pos] += 1


def find_frontiers(memory_obj: GameMemory, width: int, south_bound: int, north_bound: int) -> List[Tuple[int, int]]:
    """Identify discovered passable cells adjacent to undiscovered/unknown cells."""
    known_passable = memory_obj.map.get_known_passable_cells(south_bound, north_bound)
    frontiers = []
    for cell in known_passable:
        col, row = cell
        has_unknown_neighbor = False
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (col + dc, row + dr)
            if 0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound + 5:
                if memory_obj.map.is_unknown(neighbor):
                    has_unknown_neighbor = True
                    break
        if has_unknown_neighbor:
            frontiers.append(cell)
    return frontiers


def compute_bfs_distances(start: Tuple[int, int], memory_obj: GameMemory, south_bound: int, north_bound: int) -> Dict[Tuple[int, int], int]:
    """Run a single BFS from start to find distances to all reachable cells."""
    queue = deque([(start, 0)])
    distances = {start: 0}
    visited = {start}
    width = memory_obj.map.width

    while queue:
        curr, dist = queue.popleft()
        cx, cy = curr
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (cx + dx, cy + dy)
            nx, ny = neighbor
            if 0 <= nx < width and south_bound <= ny <= north_bound:
                if neighbor not in visited and memory_obj.map.is_passable(curr, neighbor):
                    visited.add(neighbor)
                    distances[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))
    return distances


def score_targets(robot: Robot, targets: List[Tuple[int, int]], memory_obj: GameMemory, obs_state: ObsState, step: int) -> Dict[Tuple[int, int], float]:
    """Score every target based on resource value, exploration bonus, distance, and revisit penalties."""
    scores = {}
    
    # Pre-calculate reachable distances
    distances = compute_bfs_distances(robot.pos, memory_obj, obs_state.south_bound, obs_state.north_bound)

    for target in targets:
        # 1. resource_value
        resource_value = 0.0
        if target in obs_state.crystals:
            resource_value = float(obs_state.crystals[target]) * 4.0
        elif target in obs_state.mining_nodes:
            # Miners focus on mining nodes, others ignore or score lower
            if robot.rtype == 3:
                resource_value = 800.0
            else:
                resource_value = 100.0

        # 2. exploration_bonus
        exploration_bonus = 0.0
        is_frontier_cell = False
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (target[0] + dc, target[1] + dr)
            if 0 <= neighbor[0] < memory_obj.map.width and obs_state.south_bound <= neighbor[1] <= obs_state.north_bound + 5:
                if memory_obj.map.is_unknown(neighbor):
                    is_frontier_cell = True
                    break

        if is_frontier_cell:
            if robot.rtype == 1:  # Scout
                exploration_bonus = 300.0
            elif robot.rtype == 2:  # Worker
                exploration_bonus = 150.0
            else:
                exploration_bonus = 50.0

        # 3. distance_penalty
        d = distances.get(target, float('inf'))
        if d == float('inf'):
            scores[target] = -999999.0
            continue
        distance_penalty = d * 15.0

        # 4. revisit_penalty
        visit_count = memory_obj.map.visit_counts.get(target, 0)
        revisit_penalty = visit_count * 30.0

        # Anti-oscillation & side priority rules
        is_left_side = obs_state.my_factory.col < (memory_obj.map.width // 2)
        home_cols = range(0, memory_obj.map.width // 2) if is_left_side else range(memory_obj.map.width // 2, memory_obj.map.width)
        if step < 300 and target[0] not in home_cols:
            revisit_penalty += 300.0  # Encourage early territorial stay

        # Avoid dead ends for non-workers
        exits = 0
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            n = (target[0] + dc, target[1] + dr)
            if 0 <= n[0] < memory_obj.map.width and obs_state.south_bound <= n[1] <= obs_state.north_bound:
                if memory_obj.map.is_passable(target, n):
                    exits += 1
        if exits <= 1 and robot.rtype != 2:
            revisit_penalty += 100.0

        # Avoid enemy factory proximity danger
        if obs_state.has_enemy_factory():
            enemy_factory_pos = obs_state.enemy_factory.pos
            dist_to_enemy = abs(target[0] - enemy_factory_pos[0]) + abs(target[1] - enemy_factory_pos[1])
            if dist_to_enemy < 5:
                revisit_penalty += (5 - dist_to_enemy) * 100.0

        score = resource_value + exploration_bonus - distance_penalty - revisit_penalty
        scores[target] = score

    return scores


def choose_goal(robot: Robot, rstate: Dict[str, Any], memory_obj: GameMemory, obs_state: ObsState, width: int, south_bound: int, north_bound: int) -> Tuple[Tuple[int, int], str]:
    """Select the highest scoring goal according to strict priority hierarchy and unit specialization."""
    # 1. Miner specialization: Miner prioritizes mining nodes
    if robot.rtype == 3:
        nodes = [n for n in obs_state.mining_nodes if n[1] > south_bound]
        if nodes:
            scores = score_targets(robot, nodes, memory_obj, obs_state, current_step)
            valid_nodes = [n for n in nodes if scores[n] > -900000]
            if valid_nodes:
                best_node = max(valid_nodes, key=lambda n: scores[n])
                return best_node, "COLLECT"
        # No mining nodes left, return to factory to transfer energy
        return obs_state.my_factory.pos, "RETURN"

    # 2. Worker specialization: Worker prioritizes clearing walls corridor / home-side walls
    if robot.rtype == 2:
        blocking_wall_pos = None
        # Corridor ahead of factory (scan 3 columns, 8 rows ahead)
        my_factory = obs_state.my_factory
        for r in range(my_factory.row + 1, min(my_factory.row + 9, obs_state.north_bound + 1)):
            for c in [my_factory.col, my_factory.col - 1, my_factory.col + 1]:
                if 0 <= c < width:
                    w_curr = memory_obj.map.get_wall_value((c, r))
                    if w_curr != -1 and w_curr != 0 and w_curr != 15:
                        blocking_wall_pos = (c, r)
                        break
            if blocking_wall_pos:
                break
                
        # Wall blocking crystals or mining nodes
        if not blocking_wall_pos:
            resources = list(obs_state.crystals.keys()) + list(obs_state.mining_nodes)
            for res_pos in resources:
                if res_pos[1] <= south_bound:
                    continue
                w_res = memory_obj.map.get_wall_value(res_pos)
                if w_res != -1 and w_res != 0 and w_res != 15:
                    blocking_wall_pos = res_pos
                    break
                    
        if blocking_wall_pos:
            return blocking_wall_pos, "EXPLORE"
            
        # No walls to clear, return to factory if energy is high
        if robot.energy >= 200:
            return obs_state.my_factory.pos, "RETURN"

    # 3. Scout high-energy return check
    if robot.rtype == 1 and robot.energy >= 80:
        return obs_state.my_factory.pos, "RETURN"

    # Priority 1: VISIBLE CRYSTAL
    crystals = [c for c in obs_state.crystals.keys() if c[1] > south_bound]
    if crystals:
        scores = score_targets(robot, crystals, memory_obj, obs_state, current_step)
        valid_crystals = [c for c in crystals if scores[c] > -900000]
        if valid_crystals:
            best_crystal = max(valid_crystals, key=lambda c: scores[c])
            return best_crystal, "COLLECT"

    # Priority 2: NEAREST FRONTIER CELL
    frontiers = find_frontiers(memory_obj, width, south_bound, north_bound)
    if frontiers:
        scores = score_targets(robot, frontiers, memory_obj, obs_state, current_step)
        valid_frontiers = [f for f in frontiers if scores[f] > -900000]
        if valid_frontiers:
            best_frontier = max(valid_frontiers, key=lambda f: scores[f])
            return best_frontier, "EXPLORE"

    # Priority 3: RESOURCE CELLS (mining nodes for others)
    nodes = [n for n in obs_state.mining_nodes if n[1] > south_bound]
    if nodes:
        scores = score_targets(robot, nodes, memory_obj, obs_state, current_step)
        valid_nodes = [n for n in nodes if scores[n] > -900000]
        if valid_nodes:
            best_node = max(valid_nodes, key=lambda n: scores[n])
            return best_node, "EXPLORE"

    # Priority 4: UNEXPLORED REGIONS
    unexplored = [c for c in memory_obj.map.discovered_cells if c[1] > south_bound and memory_obj.map.visit_counts.get(c, 0) == 0]
    if unexplored:
        scores = score_targets(robot, unexplored, memory_obj, obs_state, current_step)
        valid_unexplored = [c for c in unexplored if scores[c] > -900000]
        if valid_unexplored:
            best_unexplored = max(valid_unexplored, key=lambda c: scores[c])
            return best_unexplored, "EXPLORE"

    # Priority 5: IDLE
    return obs_state.my_factory.pos, "IDLE"


def bfs(start: Tuple[int, int], goals: Set[Tuple[int, int]], memory_obj: GameMemory, width: int, south_bound: int, north_bound: int) -> Optional[List[Tuple[int, int]]]:
    """BFS shortest pathfinder returning list of cells [start, ..., goal]."""
    if not goals:
        return None
    if start in goals:
        return [start]

    queue = deque([start])
    parent = {}
    visited = {start}
    found_goal = None

    while queue:
        curr = queue.popleft()
        if curr in goals:
            found_goal = curr
            break

        x, y = curr
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            if 0 <= nx < width and south_bound <= ny <= north_bound:
                if neighbor not in visited and memory_obj.map.is_passable(curr, neighbor):
                    visited.add(neighbor)
                    parent[neighbor] = curr
                    queue.append(neighbor)

    if found_goal is None:
        return None

    path = []
    curr_node = found_goal
    while curr_node != start:
        path.append(curr_node)
        curr_node = parent[curr_node]
    path.append(start)
    path.reverse()
    return path


def check_factory_jump(factory: Robot, target: Tuple[int, int], memory_obj: GameMemory, obs_state: ObsState, width: int, south_bound: int, north_bound: int) -> Optional[str]:
    """Smart Factory jump coordination to bypass obstacles or escape traps."""
    if factory.jump_cd > 0:
        return None

    fx, fy = factory.pos
    tx, ty = target

    # Jump North if blocked North by a wall and target is North
    north_pos = (fx, fy + 1)
    is_blocked_north = not memory_obj.map.is_passable(factory.pos, north_pos)
    if is_blocked_north and ty > fy:
        landing = (fx, fy + 2)
        if is_in_bounds(landing[0], landing[1], width, south_bound + 1, north_bound):
            w_val = memory_obj.map.get_wall_value(landing)
            if w_val != -1 and w_val != 15:
                return "JUMP_NORTH"

    # Trap escape jump (if no regular moves are passable)
    has_passable_move = False
    for dx, dy in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
        neighbor = (fx + dx, fy + dy)
        if is_in_bounds(neighbor[0], neighbor[1], width, south_bound, north_bound):
            if memory_obj.map.is_passable(factory.pos, neighbor):
                has_passable_move = True
                break

    if not has_passable_move:
        for dx, dy, direction in [(0, 1, "NORTH"), (1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH")]:
            landing = (fx + dx * 2, fy + dy * 2)
            if is_in_bounds(landing[0], landing[1], width, south_bound + 1, north_bound):
                w_val = memory_obj.map.get_wall_value(landing)
                if w_val != -1 and w_val != 15:
                    return f"JUMP_{direction}"

    # Objective jump to travel significantly faster
    if ty - fy >= 2 and fx == tx:
        landing = (fx, fy + 2)
        if is_in_bounds(landing[0], landing[1], width, south_bound + 1, north_bound):
            w_val = memory_obj.map.get_wall_value(landing)
            if w_val != -1 and w_val != 15:
                normal_path = bfs(factory.pos, {target}, memory_obj, width, south_bound, north_bound)
                if normal_path is None or len(normal_path) > 4:
                    return "JUMP_NORTH"

    return None


def follow_path(robot: Robot, rstate: Dict[str, Any], memory_obj: GameMemory, obs_state: ObsState, width: int, south_bound: int, north_bound: int) -> str:
    """Consume cached path, recalculating only on target disappearance or blockage."""
    target = rstate.get('target')
    path = rstate.get('current_path', [])

    # 1. Check target invalidity
    target_invalid = False
    if target is None:
        target_invalid = True
    else:
        # If crystal collected/depleted or target fell below scroll
        if target in memory_obj.map.discovered_cells and target not in obs_state.crystals and target not in obs_state.mining_nodes and target != obs_state.my_factory.pos:
            target_invalid = True
        if target[1] <= south_bound:
            target_invalid = True

    # 2. Check path blockage
    path_blocked = False
    if not target_invalid and path:
        if path[0] != robot.pos:
            try:
                idx = path.index(robot.pos)
                path = path[idx:]
                rstate['current_path'] = path
            except ValueError:
                path_blocked = True

        for cell in path:
            if cell[1] <= south_bound:
                path_blocked = True
                break

        if not path_blocked and len(path) > 1:
            if not memory_obj.map.is_passable(robot.pos, path[1]):
                path_blocked = True

    # 3. Target Re-evaluation
    # Replan if invalid/blocked/empty or if a scout detects a crystal
    re_evaluate = (
        target_invalid or path_blocked or not path or len(path) <= 1
        or (robot.rtype == 1 and rstate.get('mode') == 'EXPLORE' and obs_state.crystals)
    )

    if re_evaluate:
        new_target, new_mode = choose_goal(robot, rstate, memory_obj, obs_state, width, south_bound, north_bound)
        if new_target != target or new_mode != rstate.get('mode') or not path:
            target = new_target
            rstate['target'] = target
            rstate['mode'] = new_mode
            new_path = bfs(robot.pos, {target}, memory_obj, width, south_bound, north_bound)
            path = new_path if new_path else []
            rstate['current_path'] = path

    # Cooldown check
    if robot.move_cd > 0:
        return "IDLE"

    # Miner specialization: TRANSFORM on node
    if robot.rtype == 3 and robot.pos in obs_state.mining_nodes and robot.energy >= 100:
        if robot.pos not in obs_state.mines:
            return "TRANSFORM"

    # Worker specialization: Clear wall obstacles
    if robot.rtype == 2 and target is not None:
        dist = get_manhattan_distance(robot.pos, target)
        if dist == 1:
            from agent.constants import DELTA_TO_DIR
            dx, dy = target[0] - robot.pos[0], target[1] - robot.pos[1]
            direction = DELTA_TO_DIR.get((dx, dy), "IDLE")
            w_val = memory_obj.map.get_wall_value(robot.pos)
            from agent.constants import DIR_TO_BIT
            bit = DIR_TO_BIT.get(direction, 0)
            if w_val != -1 and (w_val & bit) and robot.energy >= 100:
                return f"REMOVE_{direction}"

    if len(path) > 1:
        next_cell = path[1]
        direction = get_direction_from_offset(robot.pos, next_cell)
        if memory_obj.map.is_passable(robot.pos, next_cell):
            rstate['current_path'] = path[1:]
            return direction

    return "IDLE"


def agent_v2(obs: Any, config: Any) -> Dict[str, str]:
    """The unified agent function implementing the layered autonomous architecture."""
    global memory, robot_states, current_step

    # 1. Parse observation and config
    config_state = parse_config(config)
    obs_state = parse_obs(obs)

    current_step = getattr(obs, 'step', current_step)
    if current_step == 0:
        memory = GameMemory()
        robot_states = {}

    # 2. Update memory
    update_memory(obs_state, memory, current_step)

    # Cleanup inactive robots
    active_uids = set(obs_state.my_robots.keys())
    for uid in list(robot_states.keys()):
        if uid not in active_uids:
            del robot_states[uid]

    my_robots = obs_state.my_robots
    my_factory = obs_state.my_factory

    # 3. Handle Factory survival and migrations
    survivable, escape_path = survival.verify_factory_survivability(
        my_factory, memory.map, current_step, obs_state.south_bound, obs_state.north_bound
    )
    spawn_decision = macro.get_spawn_decision(obs_state, config_state, current_step)

    # Factory JUMP coordination
    jump_action = None
    if not survivable:
        if escape_path:
            jump_action = check_factory_jump(my_factory, escape_path[-1], memory, obs_state, config_state.width, obs_state.south_bound, obs_state.north_bound)
    else:
        if my_factory.row + 3 <= obs_state.north_bound:
            jump_action = check_factory_jump(my_factory, (my_factory.col, my_factory.row + 3), memory, obs_state, config_state.width, obs_state.south_bound, obs_state.north_bound)

    proposed_actions = {}
    if jump_action:
        proposed_actions[my_factory.uid] = jump_action
    else:
        proposed_actions[my_factory.uid] = get_factory_action(
            factory=my_factory,
            spawn_decision=spawn_decision,
            escape_path=escape_path,
            map_memory=memory.map,
            width=config_state.width,
            south_bound=obs_state.south_bound,
            north_bound=obs_state.north_bound,
            config=config_state,
            current_step=current_step
        )

    spawning_gate = (my_factory.col, my_factory.row + 1)

    # 4. Handle Robot targets and movements
    for robot in my_robots.values():
        if robot.rtype == 0:
            continue

        uid = robot.uid
        if uid not in robot_states:
            robot_states[uid] = {'target': None, 'current_path': [], 'mode': 'IDLE'}

        # Escape scroll override
        if survival.is_cell_in_danger(robot.pos, current_step, obs_state.south_bound, 5):
            future_sb = predict_future_boundary(current_step, obs_state.south_bound, 6)
            safe_goals = {
                (c, r) for c in range(config_state.width)
                for r in range(future_sb + 1, obs_state.north_bound + 1)
                if (c, r) in memory.map.discovered_cells and memory.map.get_wall_value((c, r)) not in [-1, 15]
            }
            if safe_goals:
                path = bfs(robot.pos, safe_goals, memory, config_state.width, obs_state.south_bound, obs_state.north_bound)
                if path:
                    robot_states[uid]['target'] = path[-1]
                    robot_states[uid]['current_path'] = path
                    robot_states[uid]['mode'] = 'RETURN'

        # Spawning gate clearance check
        if robot.pos == spawning_gate and robot.move_cd == 0:
            proposed_actions[uid] = get_clear_gate_action(
                robot.pos, memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
            )
            continue

        act = follow_path(robot, robot_states[uid], memory, obs_state, config_state.width, obs_state.south_bound, obs_state.north_bound)
        proposed_actions[uid] = act

    # 5. Energy transfer execution
    transfer_actions = find_transfer_opportunities(
        obs=obs_state,
        map_memory=memory.map,
        config=config_state,
        current_step=current_step
    )
    for uid, trans_act in transfer_actions.items():
        proposed_actions[uid] = trans_act

    # 6. Friendly collision resolution
    final_actions = resolve_friendly_collisions(
        proposed_actions=proposed_actions,
        obs=obs_state,
        width=config_state.width
    )

    # 7. Logging & Visualizing
    scouts_count = sum(1 for r in my_robots.values() if r.rtype == 1)
    workers_count = sum(1 for r in my_robots.values() if r.rtype == 2)
    miners_count = sum(1 for r in my_robots.values() if r.rtype == 3)
    StateLogger.log_step(
        step=current_step,
        energy=my_factory.energy,
        unit_counts={1: scouts_count, 2: workers_count, 3: miners_count},
        mine_count=len(memory.map.mines),
        known_cells_count=len(memory.map.discovered_cells),
        tasks=robot_states
    )

    if current_step % 20 == 0:
        log_ascii_map(obs_state, memory.map, config_state.width)

    return final_actions
