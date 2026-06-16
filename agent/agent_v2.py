"""Enhanced autonomous agent v2 implementing task-based control, intelligent resource assignment, and advanced pathfinding."""

from typing import Dict, List, Tuple, Set, Optional, Any
from collections import deque

from agent.state import ObsState, GameConfig, Robot
from agent.parser import parse_config, parse_obs
from memory.memory import GameMemory
from strategy.macro_strategy import MacroStrategy
from strategy.survival_strategy import SurvivalStrategy, predict_future_boundary
from strategy.task_assignment import (
    TaskAssignmentManager,
    Task,
    TASK_EXPLORE,
    TASK_COLLECT_CRYSTAL,
    TASK_GO_TO_MINING_NODE,
    TASK_RETURN_TO_FACTORY,
    TASK_REMOVE_WALL,
    TASK_ESCAPE_SCROLL,
    TASK_IDLE
)
from economy.crystal_logic import assign_crystal_targets
from economy.mining_logic import assign_mining_nodes, should_transform
from economy.transfer_logic import find_transfer_opportunities
from combat.collision import resolve_friendly_collisions
from pathfinding.astar import find_safe_path
from units.factory_logic import get_factory_action
from units.scout_logic import get_scout_action
from units.worker_logic import get_worker_action
from units.miner_logic import get_miner_action
from agent.agent import get_clear_gate_action
from exploration.frontier import find_frontier_cells
from utils.geometry import get_manhattan_distance
from debug.logger import StateLogger
from debug.visualizer import log_ascii_map

# Persistent states across steps
memory = GameMemory()
task_manager = TaskAssignmentManager()
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


def agent_v2(obs: Any, config: Any) -> Dict[str, str]:
    """The enhanced agent function implementing task-based autonomous architecture."""
    global memory, task_manager, current_step

    # 1. Parse observation and config
    config_state = parse_config(config)
    obs_state = parse_obs(obs)

    # Keep internal turn counter in sync
    current_step = getattr(obs, 'step', current_step)

    # Initialize memory at step 0
    if current_step == 0:
        memory = GameMemory()
        task_manager = TaskAssignmentManager()

    # 2. Update memory systems
    update_memory(obs_state, memory, current_step)

    # 3. Clean up task list for active robots
    active_uids = set(obs_state.my_robots.keys())
    task_manager.clear_inactive_robots(active_uids)

    # 4. Group units by type
    my_robots = obs_state.my_robots
    my_factory = obs_state.my_factory

    scouts = [r for r in my_robots.values() if r.rtype == 1]
    workers = [r for r in my_robots.values() if r.rtype == 2]
    miners = [r for r in my_robots.values() if r.rtype == 3]

    # 5. Check for scroll safety and assign ESCAPE_SCROLL task if threatened
    for robot in my_robots.values():
        if robot.rtype == 0:  # Factory has custom survival logic
            continue

        # If in danger of being consumed by scroll in 5 turns, assign escape task
        if survival.is_cell_in_danger(robot.pos, current_step, obs_state.south_bound, 5):
            future_sb = predict_future_boundary(current_step, obs_state.south_bound, 6)

            # Identify safe reachable coordinates (any discovered non-enclosed cell above future_sb)
            safe_goals = set()
            for col in range(config_state.width):
                for row in range(future_sb + 1, obs_state.north_bound + 1):
                    pos = (col, row)
                    if pos in memory.map.discovered_cells:
                        w = memory.map.get_wall_value(pos)
                        if w != -1 and w != 15:
                            safe_goals.add(pos)

            if safe_goals:
                path = find_safe_path(
                    start=robot.pos,
                    goals=safe_goals,
                    map_memory=memory.map,
                    enemy_memory=memory.enemy,
                    unit_type=robot.rtype,
                    current_step=current_step,
                    width=config_state.width,
                    south_bound=obs_state.south_bound,
                    north_bound=obs_state.north_bound
                )
                if path:
                    task_manager.assign(robot.uid, Task(TASK_ESCAPE_SCROLL, target_pos=path[-1]))
                    continue

    # 6. Assign mining nodes to miners
    mine_nodes = obs_state.mining_nodes
    miner_assignments = assign_mining_nodes(
        miners=miners,
        mining_nodes=mine_nodes,
        map_memory=memory.map,
        enemy_robots=obs_state.enemy_robots,
        my_factory=my_factory,
        south_bound=obs_state.south_bound,
        north_bound=obs_state.north_bound,
        current_step=current_step,
        width=config_state.width
    )
    for miner in miners:
        if task_manager.get_task(miner.uid).name == TASK_ESCAPE_SCROLL:
            continue
        if miner.uid in miner_assignments:
            task_manager.assign(miner.uid, Task(TASK_GO_TO_MINING_NODE, target_pos=miner_assignments[miner.uid]))
        else:
            task_manager.assign(miner.uid, Task(TASK_RETURN_TO_FACTORY, target_pos=my_factory.pos))

    # 7. Assign crystals to scouts
    crystals = obs_state.crystals
    scout_assignments = assign_crystal_targets(
        scouts=scouts,
        crystals=crystals,
        map_memory=memory.map,
        enemy_robots=obs_state.enemy_robots,
        my_factory=my_factory,
        current_step=current_step,
        width=config_state.width,
        south_bound=obs_state.south_bound,
        north_bound=obs_state.north_bound
    )

    known_passable = memory.map.get_known_passable_cells(obs_state.south_bound, obs_state.north_bound)
    frontier_cells = find_frontier_cells(
        known_passable_cells=known_passable,
        is_unknown_fn=memory.map.is_unknown,
        width=config_state.width,
        south_bound=obs_state.south_bound,
        north_bound=obs_state.north_bound
    )

    # Filter frontier cells to home side in early/mid game
    is_left_side = my_factory.col < (config_state.width // 2)
    home_cols = range(0, config_state.width // 2) if is_left_side else range(config_state.width // 2, config_state.width)

    if current_step < 300:
        frontier_cells = [f for f in frontier_cells if f[0] in home_cols]

    for scout in scouts:
        if task_manager.get_task(scout.uid).name == TASK_ESCAPE_SCROLL:
            continue
        if scout.uid in scout_assignments:
            task_manager.assign(scout.uid, Task(TASK_COLLECT_CRYSTAL, target_pos=scout_assignments[scout.uid]))
        elif frontier_cells:
            # Target the nearest frontier cell
            frontier_cells.sort(key=lambda f: get_manhattan_distance(scout.pos, f))
            best_frontier = frontier_cells[0]
            task_manager.assign(scout.uid, Task(TASK_EXPLORE, target_pos=best_frontier))
        else:
            task_manager.assign(scout.uid, Task(TASK_IDLE))

    # 8. Assign workers tasks
    # Verify if factory has escape paths
    survivable, escape_path = survival.verify_factory_survivability(
        my_factory, memory.map, current_step, obs_state.south_bound, obs_state.north_bound
    )

    blocking_wall_pos = None
    if not survivable:
        # Find the nearest wall in front of factory to remove
        for r in range(my_factory.row + 1, obs_state.north_bound + 1):
            pos = (my_factory.col, r)
            w = memory.map.get_wall_value(pos)
            if w != -1 and w != 0:
                blocking_wall_pos = pos
                break

    # Proactive path clearing corridor scan (even if factory is currently survivable)
    if blocking_wall_pos is None:
        # Scan a 3-column corridor: [factory.col - 1, factory.col, factory.col + 1]
        # From factory's row + 1 up to factory's row + 8 (or north_bound)
        # Find the lowest row that has a vertical blocking wall.
        found_wall = False
        for r in range(my_factory.row + 1, min(my_factory.row + 9, obs_state.north_bound + 1)):
            for c in [my_factory.col, my_factory.col - 1, my_factory.col + 1]:
                if 0 <= c < config_state.width:
                    w_prev = memory.map.get_wall_value((c, r - 1))
                    w_curr = memory.map.get_wall_value((c, r))

                    has_blocking_wall = False
                    if w_prev != -1 and (w_prev & 1):
                        has_blocking_wall = True
                    elif w_curr != -1 and (w_curr & 4):
                        has_blocking_wall = True

                    if has_blocking_wall:
                        blocking_wall_pos = (c, r)
                        found_wall = True
                        break
            if found_wall:
                break

    # If still no blocking wall, look for walls blocking crystals or mining nodes on our home side
    if blocking_wall_pos is None:
        resources = list(obs_state.crystals.keys()) + list(obs_state.mining_nodes)
        best_resource_wall = None
        best_dist = float('inf')

        for res_pos in resources:
            rx, ry = res_pos
            if ry <= obs_state.south_bound or rx not in home_cols:
                continue
            w_res = memory.map.get_wall_value(res_pos)
            if w_res != -1 and w_res != 0 and w_res != 15:
                for dx, dy, direction in [(0, 1, "NORTH"), (1, 0, "EAST"), (0, -1, "SOUTH"), (-1, 0, "WEST")]:
                    neighbor = (rx + dx, ry + dy)
                    if 0 <= neighbor[0] < config_state.width and obs_state.south_bound <= neighbor[1] <= obs_state.north_bound:
                        from agent.constants import DIR_TO_BIT
                        bit = DIR_TO_BIT[direction]
                        if w_res & bit:
                            from utils.walls import is_fixed_wall
                            if not is_fixed_wall(rx, direction, config_state.width):
                                dist = get_manhattan_distance(my_factory.pos, res_pos)
                                if dist < best_dist:
                                    best_dist = dist
                                    best_resource_wall = res_pos

        if best_resource_wall is not None:
            blocking_wall_pos = best_resource_wall

    for worker in workers:
        if task_manager.get_task(worker.uid).name == TASK_ESCAPE_SCROLL:
            continue
        if blocking_wall_pos is not None:
            task_manager.assign(worker.uid, Task(TASK_REMOVE_WALL, target_pos=blocking_wall_pos))
        else:
            task_manager.assign(worker.uid, Task(TASK_RETURN_TO_FACTORY, target_pos=my_factory.pos))

    # 9. Generate raw decisions
    proposed_actions = {}
    spawn_decision = macro.get_spawn_decision(obs_state, config_state, current_step)

    # Factory logic
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

    # Spawning gate definition
    spawning_gate = (my_factory.col, my_factory.row + 1)

    # Scout logic
    for scout in scouts:
        if scout.pos == spawning_gate and scout.move_cd == 0:
            proposed_actions[scout.uid] = get_clear_gate_action(
                scout.pos, memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
            )
        else:
            task = task_manager.get_task(scout.uid)
            proposed_actions[scout.uid] = get_scout_action(
                scout=scout,
                task=task,
                map_memory=memory.map,
                enemy_memory=memory.enemy,
                current_step=current_step,
                width=config_state.width,
                south_bound=obs_state.south_bound,
                north_bound=obs_state.north_bound
            )

        # Miner logic
    for miner in miners:
        if miner.pos == spawning_gate and miner.move_cd == 0:
            proposed_actions[miner.uid] = get_clear_gate_action(
                miner.pos, memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
            )
        else:
            task = task_manager.get_task(miner.uid)
            proposed_actions[miner.uid] = get_miner_action(
                miner=miner,
                task=task,
                mining_nodes=mine_nodes,
                map_memory=memory.map,
                enemy_memory=memory.enemy,
                width=config_state.width,
                south_bound=obs_state.south_bound,
                north_bound=obs_state.north_bound,
                config=config_state,
                current_step=current_step
            )

        # Worker logic
    for worker in workers:
        if worker.pos == spawning_gate and worker.move_cd == 0:
            proposed_actions[worker.uid] = get_clear_gate_action(
                worker.pos, memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
            )
        else:
            task = task_manager.get_task(worker.uid)
            proposed_actions[worker.uid] = get_worker_action(
                worker=worker,
                task=task,
                map_memory=memory.map,
                enemy_memory=memory.enemy,
                current_step=current_step,
                width=config_state.width,
                south_bound=obs_state.south_bound,
                north_bound=obs_state.north_bound,
                config=config_state
            )

    # 10. Apply energy transfers (Priority over movement if transfer is active)
    transfer_actions = find_transfer_opportunities(
        obs=obs_state,
        map_memory=memory.map,
        config=config_state,
        current_step=current_step
    )
    for uid, trans_act in transfer_actions.items():
        proposed_actions[uid] = trans_act

    # 11. Run friendly collision resolution
    final_actions = resolve_friendly_collisions(
        proposed_actions=proposed_actions,
        obs=obs_state,
        width=config_state.width
    )

    # 12. Logging and ASCII visualizer diagnostics
    unit_counts = {1: len(scouts), 2: len(workers), 3: len(miners)}
    StateLogger.log_step(
        step=current_step,
        energy=my_factory.energy,
        unit_counts=unit_counts,
        mine_count=len(obs_state.mines),
        known_cells_count=len(memory.map.discovered_cells),
        tasks=task_manager.assignments
    )
    # Render ASCII map every 20 steps to avoid excessive stdout/stderr logs
    if current_step % 20 == 0:
        log_ascii_map(obs_state, memory.map, config_state.width)

    return final_actions

# Alias for backward compatibility with any code that might import 'agent'
agent = agent_v2