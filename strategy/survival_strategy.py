"""Survival strategy logic, scroll prediction, and escape route validation."""

from typing import Tuple, List, Set, Optional
from agent.state import Robot, ObsState
from memory.map_memory import MapMemory

def predict_future_boundary(current_step: int, current_south_bound: int, steps_forward: int) -> int:
    """Predict the southern boundary coordinate at a future step.
    
    The scroll speed ramps linearly from 0.25 rows/turn at step 0 to 1.0 rows/turn at step 400.
    """
    sb = float(current_south_bound)
    for step in range(current_step, current_step + steps_forward):
        # Linearly interpolate speed from 0.25 to 1.0
        speed = 0.25 + 0.75 * min(step, 400) / 400.0
        sb += speed
    return int(sb)

class SurvivalStrategy:
    def __init__(self, danger_buffer_turns: int = 8):
        self.danger_buffer_turns = danger_buffer_turns

    def is_cell_in_danger(
        self,
        pos: Tuple[int, int],
        current_step: int,
        current_south_bound: int,
        turns_ahead: int
    ) -> bool:
        """Check if a cell will fall below the southern boundary within turns_ahead steps."""
        future_sb = predict_future_boundary(current_step, current_south_bound, turns_ahead)
        return pos[1] <= future_sb

    def get_safe_cells(
        self,
        cells: Set[Tuple[int, int]],
        current_step: int,
        current_south_bound: int,
        turns_ahead: int
    ) -> Set[Tuple[int, int]]:
        """Filter a set of cells, returning only those that are safe from the scroll."""
        future_sb = predict_future_boundary(current_step, current_south_bound, turns_ahead)
        return {pos for pos in cells if pos[1] > future_sb}

    def verify_factory_survivability(
        self,
        factory: Robot,
        map_memory: MapMemory,
        current_step: int,
        south_bound: int,
        north_bound: int
    ) -> Tuple[bool, List[Tuple[int, int]]]:
        """Check if the factory has a clear path to move north and survive the scroll.
        
        Returns:
            (is_survivable: bool, escape_path: List[Tuple[int, int]])
        """
        # Since factory moves once every 2 turns, search up to 10 turns ahead
        turns_to_check = 10
        future_sb = predict_future_boundary(current_step, south_bound, turns_to_check)
        
        # We perform a BFS search starting from the factory position
        # target must be at a row > future_sb and row <= north_bound
        start = factory.pos
        width = map_memory.width
        
        # If factory is already below or at danger, it's not safe
        if start[1] <= south_bound:
            return False, []

        from collections import deque
        queue = deque([start])
        parent = {}
        visited = {start}
        found_target: Optional[Tuple[int, int]] = None
        
        while queue:
            curr = queue.popleft()
            col, row = curr
            
            # If we reached a row safe from the predicted boundary 10 turns ahead
            if row > future_sb:
                found_target = curr
                break
                
            for dc, dr in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
                neighbor = (col + dc, row + dr)
                # Only move within grid bounds
                if not (0 <= neighbor[0] < width and south_bound <= neighbor[1] <= north_bound):
                    continue
                # Also must be passable in map memory
                if neighbor not in visited and map_memory.is_passable(curr, neighbor):
                    visited.add(neighbor)
                    parent[neighbor] = curr
                    queue.append(neighbor)
                    
        if found_target is None:
            return False, []
            
        # Reconstruct path
        path = []
        curr_node = found_target
        while curr_node != start:
            path.append(curr_node)
            curr_node = parent[curr_node]
        path.append(start)
        path.reverse()
        return True, path
