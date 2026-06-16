"""Frontier exploration mapping for the Crawl AI Agent."""

from typing import List, Tuple, Set

def find_frontier_cells(
    known_passable_cells: Set[Tuple[int, int]],
    is_unknown_fn,  # Callable[[Tuple[int, int]], bool]
    width: int,
    south_bound: int,
    north_bound: int
) -> List[Tuple[int, int]]:
    """Identify known passable cells that are adjacent to undiscovered/unknown cells.
    
    A cell is a frontier cell if:
    1. It is known and passable.
    2. It is within active bounds.
    3. At least one of its cardinal neighbors is unknown.
    """
    frontiers = []
    
    for cell in known_passable_cells:
        col, row = cell
        if not (0 <= col < width and south_bound <= row <= north_bound):
            continue
            
        # Check if any cardinal neighbor is unknown
        has_unknown_neighbor = False
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (col + dc, row + dr)
            # Only consider unknown neighbors that are within the scroll window
            # (or slightly north of it to anticipate scroll)
            if 0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound + 5:
                if is_unknown_fn(neighbor):
                    has_unknown_neighbor = True
                    break
                    
        if has_unknown_neighbor:
            frontiers.append(cell)
            
    return frontiers
