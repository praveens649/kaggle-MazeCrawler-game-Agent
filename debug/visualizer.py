"""ASCII map visualizer for debugging map memory, robots, and scroll bounds."""

import sys
from typing import Tuple
from agent.state import ObsState
from memory.map_memory import MapMemory

def render_ascii_map(
    obs: ObsState,
    map_memory: MapMemory,
    width: int = 20
) -> str:
    """Generate an ASCII visual representation of the active board.
    
    Renders from southBound to northBound, including walls, units, crystals, and unknown cells.
    """
    south = obs.south_bound
    north = obs.north_bound
    
    # Map symbols
    # Unknown: ' ? '
    # Empty: ' . '
    # Crystal: ' * '
    # Mine: ' X '
    # Robots:
    # Own: F (Factory), S (Scout), W (Worker), M (Miner)
    # Enemy: f (Factory), s (Scout), w (Worker), m (Miner)
    
    lines = []
    lines.append(f"--- BOARD RENDER (Row {south} to {north}) ---")
    
    for row in range(north, south - 1, -1):
        row_str = f"{row:03d} |"
        for col in range(width):
            pos = (col, row)
            
            # Check unit occupant
            occupant = None
            for r in obs.robots.values():
                if r.pos == pos:
                    sym = "F" if r.rtype == 0 else "S" if r.rtype == 1 else "W" if r.rtype == 2 else "M"
                    if r.owner != obs.player_id:
                        sym = sym.lower()
                    occupant = sym
                    break
            
            if occupant:
                cell_char = occupant
            elif pos in obs.crystals:
                cell_char = "*"
            elif pos in map_memory.mines:
                cell_char = "X"
            elif pos in obs.mining_nodes:
                cell_char = "O"
            elif map_memory.is_unknown(pos):
                cell_char = "?"
            else:
                cell_char = "."
                
            # Render wall indicators around cell (e.g. check East/South walls for grid lines)
            w = map_memory.get_wall_value(pos)
            
            # Form cell string
            left_wall = "|" if (w != -1 and w & 8) or col == 0 else " "
            right_wall = "|" if (w != -1 and w & 2) or col == width - 1 else " "
            
            row_str += f"{left_wall}{cell_char}{right_wall}"
            
        lines.append(row_str)
        
    lines.append("-" * (width * 3 + 6))
    return "\n".join(lines)

def log_ascii_map(obs: ObsState, map_memory: MapMemory, width: int = 20):
    """Log ASCII map to stderr for easy visibility in Kaggle logs."""
    try:
        rendered = render_ascii_map(obs, map_memory, width)
        sys.stderr.write(rendered + "\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"Failed to render ASCII map: {e}\n")
        sys.stderr.flush()
