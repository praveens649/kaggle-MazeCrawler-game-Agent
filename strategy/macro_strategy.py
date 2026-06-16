"""Macro-strategic phase management and robot production logic."""

from typing import Dict, Optional
from agent.state import ObsState, GameConfig
from agent.constants import TYPE_SCOUT, TYPE_WORKER, TYPE_MINER
from strategy.survival_strategy import predict_future_boundary

class MacroStrategy:
    def __init__(self):
        self.phase = "EARLY"  # "EARLY", "MID", "LATE"

    def get_phase(self, step: int) -> str:
        """Evaluate and return the strategic phase based on the game turn."""
        if step < 100:
            self.phase = "EARLY"
        elif step < 300:
            self.phase = "MID"
        else:
            self.phase = "LATE"
        return self.phase

    def get_spawn_decision(
        self,
        obs: ObsState,
        config: GameConfig,
        step: int
    ) -> Optional[int]:
        """Decide which unit type to spawn from the factory.
        
        Returns:
            TYPE_SCOUT, TYPE_WORKER, TYPE_MINER, or None.
        """
        factory = obs.my_factory
        if factory.build_cd > 0:
            return None

        phase = self.get_phase(step)
        energy = factory.energy
        
        # Count our current alive units
        unit_counts = {TYPE_SCOUT: 0, TYPE_WORKER: 0, TYPE_MINER: 0}
        for robot in obs.my_robots.values():
            if robot.rtype in unit_counts:
                unit_counts[robot.rtype] += 1

        # Dynamic Factory safety reserve: keep enough energy for movement and survival
        is_near_scroll = factory.row <= obs.south_bound + 5
        has_worker = unit_counts[TYPE_WORKER] > 0

        if phase == "EARLY":
            # Aggressive expansion, very low reserve
            factory_reserve = 50
        elif phase == "MID":
            if is_near_scroll:
                # Keep a high reserve to spawn emergency worker or move
                factory_reserve = 200 if not has_worker else 100
            else:
                factory_reserve = 100 if not has_worker else 50
        else: # LATE
            # Conserve energy for Turn-500 tiebreakers
            if is_near_scroll and not has_worker:
                factory_reserve = 200
            else:
                factory_reserve = 350

        available_energy = energy - factory_reserve

        if phase == "EARLY":
            # Priority checklist for early game: get a balanced foundation first
            if unit_counts[TYPE_MINER] < 1 and available_energy >= config.miner_cost and (step >= 10 or unit_counts[TYPE_SCOUT] >= 1):
                return TYPE_MINER
            if unit_counts[TYPE_SCOUT] < 1 and available_energy >= config.scout_cost:
                return TYPE_SCOUT
            if unit_counts[TYPE_WORKER] < 1 and available_energy >= config.worker_cost and (step >= 20 or unit_counts[TYPE_MINER] >= 1):
                return TYPE_WORKER
            if unit_counts[TYPE_SCOUT] < 2 and available_energy >= config.scout_cost:
                return TYPE_SCOUT
            if unit_counts[TYPE_MINER] < 2 and available_energy >= config.miner_cost:
                return TYPE_MINER
            if unit_counts[TYPE_WORKER] < 2 and available_energy >= config.worker_cost:
                return TYPE_WORKER

        elif phase == "MID":
            # Mid game priority: maintain minimum counts, scale economy and clearers
            if unit_counts[TYPE_MINER] < 2 and available_energy >= config.miner_cost:
                return TYPE_MINER
            if unit_counts[TYPE_SCOUT] < 2 and available_energy >= config.scout_cost:
                return TYPE_SCOUT
            if unit_counts[TYPE_WORKER] < 2 and available_energy >= config.worker_cost:
                return TYPE_WORKER
            if unit_counts[TYPE_MINER] < 4 and available_energy >= config.miner_cost:
                return TYPE_MINER
            if unit_counts[TYPE_WORKER] < 3 and available_energy >= config.worker_cost:
                return TYPE_WORKER
            if unit_counts[TYPE_SCOUT] < 4 and available_energy >= config.scout_cost:
                return TYPE_SCOUT

        elif phase == "LATE":
            # Scan for blocking walls in the corridor ahead of the factory (5 rows ahead, 3 columns wide)
            has_blocking_wall = False
            width = config.width
            for r in range(factory.row + 1, min(factory.row + 6, obs.north_bound + 1)):
                for c in [factory.col, factory.col - 1, factory.col + 1]:
                    if 0 <= c < width:
                        idx = (r - obs.south_bound) * width + c
                        if 0 <= idx < len(obs.raw_walls):
                            w = obs.raw_walls[idx]
                            if w != -1 and w != 0:
                                has_blocking_wall = True
                                break
                if has_blocking_wall:
                    break

            # Late game checklist: focus entirely on workers for path clearance, no miners
            # Spawn first worker unconditionally
            if unit_counts[TYPE_WORKER] < 1 and available_energy >= config.worker_cost:
                return TYPE_WORKER

            # Only spawn extra workers if a blockade is actually detected ahead of the factory
            if has_blocking_wall:
                if unit_counts[TYPE_WORKER] < 3 and available_energy >= config.worker_cost:
                    return TYPE_WORKER

            # Maintain first scout for vision unconditionally
            if unit_counts[TYPE_SCOUT] < 1 and available_energy >= config.scout_cost:
                return TYPE_SCOUT
            # Second scout only if we have high energy surplus
            if unit_counts[TYPE_SCOUT] < 2 and available_energy >= config.scout_cost and energy > 500:
                return TYPE_SCOUT

        return None


