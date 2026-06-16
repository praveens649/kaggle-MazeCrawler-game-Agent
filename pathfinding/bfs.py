"""Breadth-First Search (BFS) pathfinder for the Crawl AI Agent."""

from collections import deque
from typing import Dict, List, Tuple, Set, Optional

def find_shortest_path(
    start: Tuple[int, int],
    goals: Set[Tuple[int, int]],
    is_passable_fn,  # Callable[[Tuple[int, int], Tuple[int, int]], bool]
    width: int,
    south_bound: int,
    north_bound: int
) -> Optional[List[Tuple[int, int]]]:
    """Find the shortest path from start to any goal in goals.
    
    Returns:
        List of (col, row) coordinates including start and goal, or None if unreachable.
    """
    if not goals:
        return None
        
    if start in goals:
        return [start]
        
    queue = deque([start])
    parent: Dict[Tuple[int, int], Tuple[int, int]] = {}
    visited = {start}
    
    found_goal: Optional[Tuple[int, int]] = None
    
    while queue:
        curr = queue.popleft()
        
        if curr in goals:
            found_goal = curr
            break
            
        x, y = curr
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            
            # Boundary checks
            if not (0 <= nx < width and south_bound <= ny <= north_bound):
                continue
                
            if neighbor not in visited and is_passable_fn(curr, neighbor):
                visited.add(neighbor)
                parent[neighbor] = curr
                queue.append(neighbor)
                
    if found_goal is None:
        return None
        
    # Reconstruct path
    path = []
    curr_node = found_goal
    while curr_node != start:
        path.append(curr_node)
        curr_node = parent[curr_node]
    path.append(start)
    path.reverse()
    return path


def compute_bfs_distances(
    start: Tuple[int, int],
    is_passable_fn,  # Callable[[Tuple[int, int], Tuple[int, int]], bool]
    width: int,
    south_bound: int,
    north_bound: int
) -> Dict[Tuple[int, int], int]:
    """Run a single BFS from start to find distances to all reachable cells."""
    queue = deque([(start, 0)])
    distances = {start: 0}
    visited = {start}

    while queue:
        curr, dist = queue.popleft()
        cx, cy = curr
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor = (cx + dx, cy + dy)
            nx, ny = neighbor
            if 0 <= nx < width and south_bound <= ny <= north_bound:
                if neighbor not in visited and is_passable_fn(curr, neighbor):
                    visited.add(neighbor)
                    distances[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))
    return distances

