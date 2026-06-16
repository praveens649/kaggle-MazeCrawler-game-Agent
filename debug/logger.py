"""Telemetry logging for agent performance metrics."""

import sys
from typing import Dict, Any
from agent.state import ObsState

class StateLogger:
    @staticmethod
    def log_step(
        step: int,
        energy: int,
        unit_counts: Dict[int, int],
        mine_count: int,
        known_cells_count: int,
        tasks: Dict[str, Any]
    ):
        """Print game state telemetry on each step."""
        scout_cnt = unit_counts.get(1, 0)
        worker_cnt = unit_counts.get(2, 0)
        miner_cnt = unit_counts.get(3, 0)
        
        # Build task summaries
        task_summary = {}
        for uid, task in tasks.items():
            if hasattr(task, 'name'):
                name = task.name
                target_pos = task.target_pos
            elif isinstance(task, dict):
                name = task.get('mode', 'IDLE')
                target_pos = task.get('target')
            else:
                name = str(task)
                target_pos = None
            task_summary[uid] = f"{name}({target_pos})" if target_pos else name
            
        sys.stderr.write(
            f"[Turn {step:03d}] "
            f"Factory Energy: {energy} | "
            f"Scouts: {scout_cnt} | Workers: {worker_cnt} | Miners: {miner_cnt} | "
            f"Mines: {mine_count} | "
            f"Known Space: {known_cells_count} cells | "
            f"Active Tasks: {task_summary}\n"
        )
        sys.stderr.flush()
