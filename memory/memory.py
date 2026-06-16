"""Unified memory orchestrator for the Crawl AI Agent."""

from agent.state import ObsState
from memory.map_memory import MapMemory
from memory.enemy_memory import EnemyMemory

class GameMemory:
    """Combines spatial memory and enemy tactical memory into a single class."""
    
    def __init__(self, width: int = 20):
        self.map = MapMemory(width)
        self.enemy = EnemyMemory()

    def update(self, obs: ObsState, current_step: int):
        """Update both map and enemy memories with the latest observation."""
        self.map.update(obs)
        self.enemy.update(obs, current_step)
