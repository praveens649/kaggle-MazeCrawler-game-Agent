"""Bayesian prediction and resource estimation under Fog of War."""

from typing import Dict, Tuple, Set, Any
from agent.state import ObsState, GameConfig
from memory.map_memory import MapMemory

class BayesianResourcePredictor:
    def __init__(self):
        # Track historical resource locations we've confirmed
        self.confirmed_crystals: Set[Tuple[int, int]] = set()
        self.confirmed_nodes: Set[Tuple[int, int]] = set()
        
        # Track cells we've confirmed to be empty of resources
        self.confirmed_empty: Set[Tuple[int, int]] = set()
        
        # Track estimated enemy footprints (where the enemy has likely visited)
        self.enemy_visited_cells: Set[Tuple[int, int]] = set()

    def update(self, obs: ObsState, map_memory: MapMemory, config: GameConfig, current_step: int):
        """Update Bayesian prior beliefs using current observations and symmetry."""
        width = config.width
        
        # 1. Update confirmed resource locations from current visible data
        for pos, energy in obs.crystals.items():
            self.confirmed_crystals.add(pos)
            
        for pos in obs.mining_nodes:
            self.confirmed_nodes.add(pos)

        # 2. Update empty cells in our visible range
        # Any discovered cell that does not currently contain crystals or nodes is empty
        for pos in map_memory.discovered_cells:
            # Check if this cell is currently visible
            # (scouts have vision 5, workers 3, factory 4)
            # To be simple: if it's in discovered cells, and not in obs.crystals/mining_nodes,
            # and it's within the current active bounds, we mark it empty.
            if pos[1] >= obs.south_bound:
                if pos not in obs.crystals and pos not in obs.mining_nodes:
                    self.confirmed_empty.add(pos)

        # 3. Track enemy movements to estimate their harvested areas
        for enemy in obs.enemy_robots.values():
            self.enemy_visited_cells.add(enemy.pos)
            # Assume enemy has vision radius around their current position where they harvest crystals
            ex, ey = enemy.pos
            vision_range = 3 if enemy.rtype != 1 else 5
            for dx in range(-vision_range, vision_range + 1):
                for dy in range(-vision_range, vision_range + 1):
                    if abs(dx) + abs(dy) <= vision_range:
                        nx, ny = ex + dx, ey + dy
                        if 0 <= nx < width:
                            self.enemy_visited_cells.add((nx, ny))

    def predict_resource_probability(
        self,
        pos: Tuple[int, int],
        config: GameConfig,
        obs: ObsState
    ) -> float:
        """Estimate the probability that a cell contains a resource (crystal or node).
        
        Uses symmetry-based Bayesian update:
        P(C_x,y = 1 | counterpart_observed)
        """
        x, y = pos
        width = config.width
        counterpart = (width - 1 - x, y)
        
        # If we have confirmed it is empty, probability is 0
        if pos in self.confirmed_empty:
            return 0.0

        # If we have confirmed it has a crystal or node, probability is 1
        if pos in self.confirmed_crystals or pos in self.confirmed_nodes:
            return 1.0

        # Prior probabilities from config density
        p_crystal_prior = getattr(config, 'crystal_density', 0.06)
        p_node_prior = getattr(config, 'mining_node_density', 0.03)
        p_prior = p_crystal_prior + p_node_prior

        # Likelihood update based on counterpart cell observation
        # Symmetrical map generation means resources are generated symmetrically at step 0.
        if counterpart in self.confirmed_crystals or counterpart in self.confirmed_nodes:
            # The counterpart cell was generated with a resource.
            # Therefore, this cell was also generated with a resource.
            # Has it been harvested?
            if pos in self.enemy_visited_cells:
                # Enemy has visited this cell, likely harvested it if it was a crystal.
                # Mining nodes are permanent, so if counterpart is a node, this is still a node.
                if counterpart in self.confirmed_nodes:
                    return 0.95
                return p_crystal_prior * 0.1  # highly likely gone
            else:
                # Cell has not been visited by enemy, very high likelihood resource is still there
                return 0.90
        elif counterpart in self.confirmed_empty:
            # Counterpart is empty. By symmetry, this cell was generated empty.
            return 0.0

        # Counterpart is also unknown: return prior probability
        return p_prior
