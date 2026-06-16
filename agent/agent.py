"""Unified agent class orchestrating state parsing, planning, and action resolution."""

from typing import Dict, Any
from agent.state import ObsState, GameConfig
from agent.parser import parse_config, parse_obs
from memory.memory import GameMemory
from strategy.macro_strategy import MacroStrategy
from strategy.survival_strategy import SurvivalStrategy, predict_future_boundary
from strategy.task_assignment import TaskAssignmentManager, Task
from strategy.task_assignment import TASK_ESCAPE_SCROLL, TASK_GO_TO_MINING_NODE
from strategy.task_assignment import TASK_RETURN_TO_FACTORY, TASK_COLLECT_CRYSTAL
from strategy.task_assignment import TASK_EXPLORE, TASK_REMOVE_WALL, TASK_IDLE
from economy.crystal_logic import assign_crystal_targets
from economy.mining_logic import assign_mining_nodes
from economy.transfer_logic import find_transfer_opportunities
from combat.collision import resolve_friendly_collisions
from pathfinding.bfs import find_shortest_path
from exploration.frontier import find_frontier_cells
from units.factory_logic import get_factory_action
from units.scout_logic import get_scout_action
from units.miner_logic import get_miner_action
from units.worker_logic import get_worker_action
from utils.geometry import get_manhattan_distance
from debug.logger import StateLogger
from debug.visualizer import log_ascii_map

def get_clear_gate_action(
    pos: tuple,
    map_memory,
    width: int,
    south_bound: int,
    north_bound: int
) -> str:
    """Find a passable direction to move (prefer East, West, then North) to clear the factory spawn gate."""
    x, y = pos
    # Try East
    east_pos = (x + 1, y)
    if x + 1 < width and map_memory.is_passable(pos, east_pos):
        return "EAST"
    # Try West
    west_pos = (x - 1, y)
    if x - 1 >= 0 and map_memory.is_passable(pos, west_pos):
        return "WEST"
    # Try North
    north_pos = (x, y + 1)
    if y + 1 <= north_bound and map_memory.is_passable(pos, north_pos):
        return "NORTH"
    return "IDLE"

class CrawlAgent:
    """The master orchestrator class for our Crawl game agent."""
    
    def __init__(self):
        self.memory = GameMemory()
        self.macro = MacroStrategy()
        self.survival = SurvivalStrategy()
        self.task_manager = TaskAssignmentManager()
        self.current_step = 0

    def step(self, obs: Any, config: Any) -> Dict[str, str]:
        """Runs the complete turn pipeline and returns action decisions."""
        # 1. Parse observation and config
        config_state = parse_config(config)
        obs_state = parse_obs(obs)
        
        # Keep internal turn counter in sync
        self.current_step = getattr(obs, 'step', self.current_step)
        
        # 2. Update memory systems
        self.memory.update(obs_state, self.current_step)
        
        # 3. Clean up task list for active robots
        active_uids = set(obs_state.my_robots.keys())
        self.task_manager.clear_inactive_robots(active_uids)
        
        # Group units by type
        my_robots = obs_state.my_robots
        my_factory = obs_state.my_factory
        
        scouts = [r for r in my_robots.values() if r.rtype == 1]
        workers = [r for r in my_robots.values() if r.rtype == 2]
        miners = [r for r in my_robots.values() if r.rtype == 3]

        # 4. Check for scroll safety and assign ESCAPE_SCROLL task if threatened
        for robot in my_robots.values():
            if robot.rtype == 0:  # Factory has custom survival logic
                continue
                
            # If in danger of being consumed by scroll in 5 turns, assign escape task
            if self.survival.is_cell_in_danger(robot.pos, self.current_step, obs_state.south_bound, 5):
                future_sb = predict_future_boundary(self.current_step, obs_state.south_bound, 6)
                
                # Identify safe reachable coordinates (any discovered non-enclosed cell above future_sb)
                safe_goals = set()
                for col in range(config_state.width):
                    for row in range(future_sb + 1, obs_state.north_bound + 1):
                        pos = (col, row)
                        if pos in self.memory.map.discovered_cells:
                            w = self.memory.map.get_wall_value(pos)
                            if w != -1 and w != 15:
                                safe_goals.add(pos)
                                
                if safe_goals:
                    from pathfinding.astar import find_safe_path
                    path = find_safe_path(
                        start=robot.pos,
                        goals=safe_goals,
                        map_memory=self.memory.map,
                        enemy_memory=self.memory.enemy,
                        unit_type=robot.rtype,
                        current_step=self.current_step,
                        width=config_state.width,
                        south_bound=obs_state.south_bound,
                        north_bound=obs_state.north_bound
                    )
                    if path:
                        self.task_manager.assign(robot.uid, Task(TASK_ESCAPE_SCROLL, target_pos=path[-1]))
                        continue

        # 5. Assign mining nodes to miners
        mine_nodes = obs_state.mining_nodes
        miner_assignments = assign_mining_nodes(
            miners=miners,
            mining_nodes=mine_nodes,
            map_memory=self.memory.map,
            enemy_robots=obs_state.enemy_robots,
            my_factory=my_factory,
            south_bound=obs_state.south_bound,
            north_bound=obs_state.north_bound,
            current_step=self.current_step,
            width=config_state.width
        )
        for miner in miners:
            if self.task_manager.get_task(miner.uid).name == TASK_ESCAPE_SCROLL:
                continue
            if miner.uid in miner_assignments:
                self.task_manager.assign(miner.uid, Task(TASK_GO_TO_MINING_NODE, target_pos=miner_assignments[miner.uid]))
            else:
                self.task_manager.assign(miner.uid, Task(TASK_RETURN_TO_FACTORY, target_pos=my_factory.pos))

        # 6. Assign crystals to scouts
        crystals = obs_state.crystals
        scout_assignments = assign_crystal_targets(
            scouts=scouts,
            crystals=crystals,
            map_memory=self.memory.map,
            enemy_robots=obs_state.enemy_robots,
            my_factory=my_factory,
            current_step=self.current_step,
            width=config_state.width,
            south_bound=obs_state.south_bound,
            north_bound=obs_state.north_bound
        )
        
        known_passable = self.memory.map.get_known_passable_cells(obs_state.south_bound, obs_state.north_bound)
        frontier_cells = find_frontier_cells(
            known_passable_cells=known_passable,
            is_unknown_fn=self.memory.map.is_unknown,
            width=config_state.width,
            south_bound=obs_state.south_bound,
            north_bound=obs_state.north_bound
        )
        
        # Filter frontier cells to home side in early/mid game
        is_left_side = my_factory.col < (config_state.width // 2)
        home_cols = range(0, config_state.width // 2) if is_left_side else range(config_state.width // 2, config_state.width)
        
        if self.current_step < 300:
            frontier_cells = [f for f in frontier_cells if f[0] in home_cols]
        
        for scout in scouts:
            if self.task_manager.get_task(scout.uid).name == TASK_ESCAPE_SCROLL:
                continue
            if scout.uid in scout_assignments:
                self.task_manager.assign(scout.uid, Task(TASK_COLLECT_CRYSTAL, target_pos=scout_assignments[scout.uid]))
            elif frontier_cells:
                # Target the nearest frontier cell
                frontier_cells.sort(key=lambda f: get_manhattan_distance(scout.pos, f))
                best_frontier = frontier_cells[0]
                self.task_manager.assign(scout.uid, Task(TASK_EXPLORE, target_pos=best_frontier))
            else:
                self.task_manager.assign(scout.uid, Task(TASK_IDLE))

        # 7. Assign workers tasks
        # Verify if factory has escape paths
        survivable, escape_path = self.survival.verify_factory_survivability(
            my_factory, self.memory.map, self.current_step, obs_state.south_bound, obs_state.north_bound
        )
        
        blocking_wall_pos = None
        if not survivable:
            # Find the nearest wall in front of factory to remove
            for r in range(my_factory.row + 1, obs_state.north_bound + 1):
                pos = (my_factory.col, r)
                w = self.memory.map.get_wall_value(pos)
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
                        w_prev = self.memory.map.get_wall_value((c, r - 1))
                        w_curr = self.memory.map.get_wall_value((c, r))
                        
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
                w_res = self.memory.map.get_wall_value(res_pos)
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
            if self.task_manager.get_task(worker.uid).name == TASK_ESCAPE_SCROLL:
                continue
            if blocking_wall_pos is not None:
                self.task_manager.assign(worker.uid, Task(TASK_REMOVE_WALL, target_pos=blocking_wall_pos))
            else:
                self.task_manager.assign(worker.uid, Task(TASK_RETURN_TO_FACTORY, target_pos=my_factory.pos))

        # 8. Generate raw decisions
        proposed_actions = {}
        spawn_decision = self.macro.get_spawn_decision(obs_state, config_state, self.current_step)
        
        # Factory logic
        proposed_actions[my_factory.uid] = get_factory_action(
            factory=my_factory,
            spawn_decision=spawn_decision,
            escape_path=escape_path,
            map_memory=self.memory.map,
            width=config_state.width,
            south_bound=obs_state.south_bound,
            north_bound=obs_state.north_bound,
            config=config_state,
            current_step=self.current_step
        )
        
        # Spawning gate definition
        spawning_gate = (my_factory.col, my_factory.row + 1)

        # Scout logic
        for scout in scouts:
            if scout.pos == spawning_gate and scout.move_cd == 0:
                proposed_actions[scout.uid] = get_clear_gate_action(
                    scout.pos, self.memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
                )
            else:
                task = self.task_manager.get_task(scout.uid)
                proposed_actions[scout.uid] = get_scout_action(
                    scout=scout,
                    task=task,
                    map_memory=self.memory.map,
                    enemy_memory=self.memory.enemy,
                    current_step=self.current_step,
                    width=config_state.width,
                    south_bound=obs_state.south_bound,
                    north_bound=obs_state.north_bound
                )
            
        # Miner logic
        for miner in miners:
            if miner.pos == spawning_gate and miner.move_cd == 0:
                proposed_actions[miner.uid] = get_clear_gate_action(
                    miner.pos, self.memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
                )
            else:
                task = self.task_manager.get_task(miner.uid)
                proposed_actions[miner.uid] = get_miner_action(
                    miner=miner,
                    task=task,
                    mining_nodes=mine_nodes,
                    map_memory=self.memory.map,
                    enemy_memory=self.memory.enemy,
                    width=config_state.width,
                    south_bound=obs_state.south_bound,
                    north_bound=obs_state.north_bound,
                    config=config_state,
                    current_step=self.current_step
                )
            
        # Worker logic
        for worker in workers:
            if worker.pos == spawning_gate and worker.move_cd == 0:
                proposed_actions[worker.uid] = get_clear_gate_action(
                    worker.pos, self.memory.map, config_state.width, obs_state.south_bound, obs_state.north_bound
                )
            else:
                task = self.task_manager.get_task(worker.uid)
                proposed_actions[worker.uid] = get_worker_action(
                    worker=worker,
                    task=task,
                    map_memory=self.memory.map,
                    enemy_memory=self.memory.enemy,
                    current_step=self.current_step,
                    width=config_state.width,
                    south_bound=obs_state.south_bound,
                    north_bound=obs_state.north_bound,
                    config=config_state
                )

        # 9. Apply energy transfers (Priority over movement if transfer is active)
        transfer_actions = find_transfer_opportunities(
            obs=obs_state,
            map_memory=self.memory.map,
            config=config_state,
            current_step=self.current_step
        )
        for uid, trans_act in transfer_actions.items():
            proposed_actions[uid] = trans_act

        # 10. Run friendly collision resolution
        final_actions = resolve_friendly_collisions(
            proposed_actions=proposed_actions,
            obs=obs_state,
            width=config_state.width
        )
        

        # 11. Logging and ASCII visualizer diagnostics
        unit_counts = {1: len(scouts), 2: len(workers), 3: len(miners)}
        StateLogger.log_step(
            step=self.current_step,
            energy=my_factory.energy,
            unit_counts=unit_counts,
            mine_count=len(self.memory.map.mines),
            known_cells_count=len(self.memory.map.discovered_cells),
            tasks=self.task_manager.assignments
        )
        # Render ASCII map every 20 steps to avoid excessive stdout/stderr logs
        if self.current_step % 20 == 0:
            log_ascii_map(obs_state, self.memory.map, config_state.width)
            
        return final_actions

