"""Dynamic Programming based finite-horizon path optimizer for the Factory."""

from typing import Dict, Tuple, List, Optional
from agent.state import Robot, ObsState, GameConfig
from strategy.survival_strategy import predict_future_boundary
from memory.map_memory import MapMemory
from utils.geometry import is_in_bounds

class DPPathOptimizer:
    def __init__(self, horizon: int = 5):
        self.horizon = horizon
        # Memoization cache for DP: (t, col, row, jump_cd) -> (max_value, best_action)
        self.memo: Dict[Tuple[int, int, int, int], Tuple[float, str]] = {}

    def get_optimal_action(
        self,
        factory: Robot,
        map_memory: MapMemory,
        config: GameConfig,
        current_step: int,
        south_bound: int,
        north_bound: int
    ) -> str:
        """Run DP backward induction to find the best immediate action for the factory."""
        self.memo.clear()
        
        # Start state at step 0
        fx, fy = factory.pos
        jump_cd = factory.jump_cd
        
        # Run recursive memoized DP search
        val, action = self._dp_search(
            t=0,
            col=fx,
            row=fy,
            jump_cd=jump_cd,
            map_memory=map_memory,
            config=config,
            current_step=current_step,
            south_bound=south_bound,
            north_bound=north_bound
        )
        
        return action if action else "IDLE"

    def _dp_search(
        self,
        t: int,
        col: int,
        row: int,
        jump_cd: int,
        map_memory: MapMemory,
        config: GameConfig,
        current_step: int,
        south_bound: int,
        north_bound: int
    ) -> Tuple[float, str]:
        """Recursive helper function computing value of state at step t."""
        state = (t, col, row, jump_cd)
        if state in self.memo:
            return self.memo[state]

        # Base case: end of horizon
        if t == self.horizon:
            val = self._evaluate_state(col, row, t, current_step, south_bound, north_bound, map_memory, config)
            return val, "IDLE"

        # Evaluate transitions
        actions = []
        
        # 1. Standard movements (cooldown 2 turns, but we evaluate step-by-step)
        # We assume move_cd is simulated or simplified step-by-step
        for dx, dy, act_name in [(0, 1, "NORTH"), (1, 0, "EAST"), (-1, 0, "WEST"), (0, -1, "SOUTH"), (0, 0, "IDLE")]:
            nx, ny = col + dx, row + dy
            if act_name == "IDLE":
                actions.append((act_name, col, row, max(0, jump_cd - 1)))
            elif is_in_bounds(nx, ny, config.width, south_bound + 1, north_bound):
                if map_memory.is_passable((col, row), (nx, ny)):
                    actions.append((act_name, nx, ny, max(0, jump_cd - 1)))

        # 2. Jump movements (leaps 2 cells, ignoring walls, requires jump_cd == 0)
        if jump_cd == 0:
            for dx, dy, act_name in [(0, 1, "JUMP_NORTH"), (1, 0, "JUMP_EAST"), (-1, 0, "JUMP_WEST"), (0, -1, "JUMP_SOUTH")]:
                nx, ny = col + dx * 2, row + dy * 2
                if is_in_bounds(nx, ny, config.width, south_bound + 1, north_bound):
                    # Check if landing cell is not solid wall
                    w_landing = map_memory.get_wall_value((nx, ny))
                    if w_landing != -1 and w_landing != 15:
                        actions.append((act_name, nx, ny, 20))  # Set jump cooldown to 20

        # Run DP transitions
        best_val = -float('inf')
        best_action = "IDLE"
        
        # Current cell instant reward/penalty
        current_state_val = self._evaluate_state(col, row, t, current_step, south_bound, north_bound, map_memory, config)

        for act_name, nx, ny, n_jump_cd in actions:
            # Recursive call for next step
            val, _ = self._dp_search(
                t=t + 1,
                col=nx,
                row=ny,
                jump_cd=n_jump_cd,
                map_memory=map_memory,
                config=config,
                current_step=current_step,
                south_bound=south_bound,
                north_bound=north_bound
            )
            
            # Transition utility combines current step value + next steps discount
            total_val = current_state_val + 0.9 * val
            if total_val > best_val:
                best_val = total_val
                best_action = act_name

        self.memo[state] = (best_val, best_action)
        return best_val, best_action

    def _evaluate_state(
        self,
        col: int,
        row: int,
        t: int,
        current_step: int,
        south_bound: int,
        north_bound: int,
        map_memory: MapMemory,
        config: GameConfig
    ) -> float:
        """Utility function to evaluate safety and efficiency of a state."""
        score = 0.0
        
        # 1. Vertical progress reward
        score += float(row) * 10.0
        
        # 2. Scroll Boundary Evasion (heavy penalty if below predicted boundary)
        pred_sb = predict_future_boundary(current_step, south_bound, t + 1)
        dist_to_sb = row - pred_sb
        if dist_to_sb <= 0:
            score -= 1000.0  # Instant death
        elif dist_to_sb < 2:
            score -= 500.0
        elif dist_to_sb < 4:
            score -= (4 - dist_to_sb) * 100.0
            
        # 3. Trapped checking (number of passable neighbors)
        passable_neighbors = 0
        for dx, dy in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
            nx, ny = col + dx, row + dy
            if is_in_bounds(nx, ny, config.width, south_bound + 1, north_bound):
                if map_memory.is_passable((col, row), (nx, ny)):
                    passable_neighbors += 1
        
        if passable_neighbors == 0:
            score -= 300.0  # Strongly penalize getting cornered/trapped
            
        return score
