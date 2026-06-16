"""Macro-strategic phase management and robot production logic."""

from typing import Dict, Optional
from agent.state import ObsState, GameConfig
from agent.constants import TYPE_SCOUT, TYPE_WORKER, TYPE_MINER

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
        
        # Factory safety reserve: keep at least 200 energy for movement and survival
        factory_reserve = 200
        available_energy = energy - factory_reserve
        
        # Count our current alive units
        unit_counts = {TYPE_SCOUT: 0, TYPE_WORKER: 0, TYPE_MINER: 0}
        for robot in obs.my_robots.values():
            if robot.rtype in unit_counts:
                unit_counts[robot.rtype] += 1

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
            # Late game checklist: focus entirely on workers for path clearance, no miners
            if unit_counts[TYPE_WORKER] < 2 and available_energy >= config.worker_cost:
                return TYPE_WORKER
            if unit_counts[TYPE_SCOUT] < 1 and available_energy >= config.scout_cost:
                return TYPE_SCOUT
            if unit_counts[TYPE_WORKER] < 4 and available_energy >= config.worker_cost:
                return TYPE_WORKER
            if unit_counts[TYPE_SCOUT] < 2 and available_energy >= config.scout_cost:
                return TYPE_SCOUT

        return None
