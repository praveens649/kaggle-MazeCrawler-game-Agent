"""Finite State Machine (FSM) behavior controller for autonomous unit state transitions."""

from typing import Dict, Tuple, Set, Any, Optional
from agent.state import Robot, ObsState, GameConfig
from strategy.task_assignment import (
    Task,
    TASK_EXPLORE,
    TASK_COLLECT_CRYSTAL,
    TASK_GO_TO_MINING_NODE,
    TASK_RETURN_TO_FACTORY,
    TASK_REMOVE_WALL,
    TASK_ESCAPE_SCROLL,
    TASK_IDLE
)
from utils.geometry import get_manhattan_distance

# Formal FSM State Definitions
STATE_EXPLORE = TASK_EXPLORE
STATE_COLLECT_CRYSTAL = TASK_COLLECT_CRYSTAL
STATE_GO_TO_MINING_NODE = TASK_GO_TO_MINING_NODE
STATE_RETURN_TO_FACTORY = TASK_RETURN_TO_FACTORY
STATE_REMOVE_WALL = TASK_REMOVE_WALL
STATE_ESCAPE_SCROLL = TASK_ESCAPE_SCROLL
STATE_IDLE = TASK_IDLE

class RobotFSM:
    def __init__(self):
        # Persistent state for each robot: uid -> state_string
        self.states: Dict[str, str] = {}

    def get_state(self, uid: str) -> str:
        """Get the current state of a robot."""
        return self.states.get(uid, STATE_IDLE)

    def transition(
        self,
        robot: Robot,
        obs: ObsState,
        config: GameConfig,
        current_step: int,
        is_safe_escape_available: bool,
        scout_assignment_pos: Optional[Tuple[int, int]],
        miner_assignment_pos: Optional[Tuple[int, int]],
        blocking_wall_pos: Optional[Tuple[int, int]],
        frontier_cells: list
    ) -> str:
        """Evaluate guards and compute the next FSM state for a robot."""
        current_state = self.states.get(robot.uid, STATE_IDLE)
        next_state = current_state
        
        # --- GLOBAL GUARD: Scroll Danger Evasion ---
        # If in danger of being consumed by scroll in 5 turns, escape
        is_in_danger = robot.row <= obs.south_bound + 4
        if is_in_danger and is_safe_escape_available:
            next_state = STATE_ESCAPE_SCROLL
        elif current_state == STATE_ESCAPE_SCROLL and not is_in_danger:
            # Re-initialize to a default search state
            next_state = STATE_EXPLORE

        # --- SPECIFIC UNIT STATE MACHINE GUARDS ---
        if next_state != STATE_ESCAPE_SCROLL:
            if robot.rtype == 1:  # Scout FSM
                next_state = self._transition_scout(
                    robot, current_state, obs, scout_assignment_pos, frontier_cells
                )
            elif robot.rtype == 2:  # Worker FSM
                next_state = self._transition_worker(
                    robot, current_state, obs, blocking_wall_pos
                )
            elif robot.rtype == 3:  # Miner FSM
                next_state = self._transition_miner(
                    robot, current_state, obs, miner_assignment_pos
                )
                
        # Save and return next state
        self.states[robot.uid] = next_state
        return next_state

    def _transition_scout(
        self,
        scout: Robot,
        current_state: str,
        obs: ObsState,
        scout_assignment_pos: Optional[Tuple[int, int]],
        frontier_cells: list
    ) -> str:
        """FSM transition rules for Scouts."""
        # Rule 1: High Energy Return
        if scout.energy >= 80:
            return STATE_RETURN_TO_FACTORY

        # Rule 2: Low Energy Resume Exploration/Collection
        if current_state == STATE_RETURN_TO_FACTORY:
            if scout.energy < 30:  # Successfully dumped energy
                return STATE_EXPLORE
            return STATE_RETURN_TO_FACTORY

        # Rule 3: Collect visible crystal assignments
        if scout_assignment_pos is not None:
            return STATE_COLLECT_CRYSTAL

        # Rule 4: Explore frontier if nothing to collect
        if frontier_cells:
            return STATE_EXPLORE

        # Rule 5: Idle fallback
        return STATE_IDLE

    def _transition_worker(
        self,
        worker: Robot,
        current_state: str,
        obs: ObsState,
        blocking_wall_pos: Optional[Tuple[int, int]]
    ) -> str:
        """FSM transition rules for Workers."""
        # Rule 1: Prioritize clearing assigned blocking walls
        if blocking_wall_pos is not None:
            return STATE_REMOVE_WALL

        # Rule 2: Otherwise return to factory to act as escort/dump energy
        return STATE_RETURN_TO_FACTORY

    def _transition_miner(
        self,
        miner: Robot,
        current_state: str,
        obs: ObsState,
        miner_assignment_pos: Optional[Tuple[int, int]]
    ) -> str:
        """FSM transition rules for Miners."""
        # Rule 1: Go to assigned mining nodes
        if miner_assignment_pos is not None:
            return STATE_GO_TO_MINING_NODE

        # Rule 2: No mining nodes available -> return to factory
        return STATE_RETURN_TO_FACTORY
