"""Spatial map memory with East-West symmetry inference for the Crawl AI Agent."""

from typing import Dict, Set, Tuple, Optional
from agent.state import ObsState, Mine
from agent.constants import WALL_N, WALL_E, WALL_S, WALL_W
from utils.geometry import get_mirrored_pos, is_in_bounds

def mirror_wall_bitfield(w: int) -> int:
    """Mirror wall bitfield for East-West symmetry.
    
    North and South walls stay North and South.
    East and West walls swap places.
    """
    if w == -1:
        return -1
    w_mirror = 0
    if w & 1:
        w_mirror |= WALL_N
    if w & 4:
        w_mirror |= WALL_S
    if w & 2:
        w_mirror |= WALL_W
    if w & 8:
        w_mirror |= WALL_E
    return w_mirror

class MapMemory:
    def __init__(self, width: int = 20):
        self.width = width
        # (col, row) -> wall_bitfield (0-15)
        self.walls: Dict[Tuple[int, int], int] = {}
        # (col, row) -> Mine
        self.mines: Dict[Tuple[int, int], Mine] = {}
        # Set of discovered passable cells (cells that have been seen and aren't completely walled off)
        self.discovered_cells: Set[Tuple[int, int]] = set()
        # (col, row) -> visit_count
        self.visit_counts: Dict[Tuple[int, int], int] = {}

    def update(self, obs: ObsState):
        """Update memory using current observation and apply symmetry reflections."""
        south = obs.south_bound
        north = obs.north_bound
        
        # 1. Update walls
        for row in range(south, north + 1):
            for col in range(self.width):
                pos = (col, row)
                idx = (row - south) * self.width + col
                if 0 <= idx < len(obs.raw_walls):
                    w = obs.raw_walls[idx]
                    if w != -1:
                        self.set_wall_value(pos, w)

        # 2. Update mines
        # Clean up mines that fell below south bound
        self.mines = {pos: m for pos, m in self.mines.items() if pos[1] >= south}
        
        # Merge currently visible mines
        for pos, mine in obs.mines.items():
            self.mines[pos] = mine

    def set_wall_value(self, pos: Tuple[int, int], w: int):
        """Set wall value for a cell and its mirrored counterpart."""
        if w == -1:
            return
            
        self.walls[pos] = w
        self.discovered_cells.add(pos)
        
        # Mirror cell based on E-W symmetry
        mirrored = get_mirrored_pos(pos, self.width)
        w_mirror = mirror_wall_bitfield(w)
        
        # Only mirror if not already explicitly seen (we prioritize actual observations)
        if mirrored not in self.walls:
            self.walls[mirrored] = w_mirror
            self.discovered_cells.add(mirrored)

    def get_wall_value(self, pos: Tuple[int, int]) -> int:
        """Get the wall bitfield for a cell. Returns -1 if unknown."""
        return self.walls.get(pos, -1)

    def is_unknown(self, pos: Tuple[int, int]) -> bool:
        """Check if a cell is undiscovered."""
        return pos not in self.walls

    def is_passable(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """Check if movement from from_pos to to_pos is possible based on known walls.
        
        If either cell is undiscovered, we assume passable to allow exploration, 
        unless it's out of bounds.
        """
        # Outer boundaries check
        col_from, row_from = from_pos
        col_to, row_to = to_pos
        
        # Simple adjacency verification
        dx = col_to - col_from
        dy = row_to - row_from
        if abs(dx) + abs(dy) != 1:
            return False
            
        # Determine direction of travel
        if dy == 1:
            direction = "NORTH"
            rev_direction = "SOUTH"
        elif dy == -1:
            direction = "SOUTH"
            rev_direction = "NORTH"
        elif dx == 1:
            direction = "EAST"
            rev_direction = "WEST"
        else:
            direction = "WEST"
            rev_direction = "EAST"

        # Check wall on current cell
        w_from = self.get_wall_value(from_pos)
        if w_from != -1:
            bit = WALL_N if direction == "NORTH" else WALL_E if direction == "EAST" else WALL_S if direction == "SOUTH" else WALL_W
            if w_from & bit:
                return False
                
        # Check wall on target cell
        w_to = self.get_wall_value(to_pos)
        if w_to != -1:
            rev_bit = WALL_S if direction == "NORTH" else WALL_W if direction == "EAST" else WALL_N if direction == "SOUTH" else WALL_E
            if w_to & rev_bit:
                return False
                
        return True

    def get_known_passable_cells(self, south_bound: int, north_bound: int) -> Set[Tuple[int, int]]:
        """Get all discovered cells within the active height window."""
        return {pos for pos in self.discovered_cells if south_bound <= pos[1] <= north_bound}
