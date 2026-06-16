"""Distance and grid proximity mapping for the Crawl AI Agent."""

from collections import deque
from typing import Dict, List, Tuple, Set, Optional

def compute_distance_grid(
    starts: List[Tuple[int, int]],
    is_passable_fn,  # Callable[[Tuple[int, int]], bool]
    width: int,
    south_bound: int,
    north_bound: int
) -> Dict[Tuple[int, int], Tuple[int, Tuple[int, int]]]:
    """Compute a multi-source distance grid on the map.
    
    Returns a dictionary mapping:
        (col, row) -> (distance_from_nearest_start, nearest_start_pos)
    """
    dist_map: Dict[Tuple[int, int], Tuple[int, Tuple[int, int]]] = {}
    queue = deque()
    
    for start in starts:
        if 0 <= start[0] < width and south_bound <= start[1] <= north_bound:
            dist_map[start] = (0, start)
            queue.append(start)
            
    while queue:
        curr = queue.popleft()
        curr_dist, start_pos = dist_map[curr]
        
        # Check adjacent neighbors
        x, y = curr
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            
            # Boundary checks
            if not (0 <= nx < width and south_bound <= ny <= north_bound):
                continue
                
            # Check if passable and not visited
            if neighbor not in dist_map and is_passable_fn(curr, neighbor):
                dist_map[neighbor] = (curr_dist + 1, start_pos)
                queue.append(neighbor)
                
    return dist_map
