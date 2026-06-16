"""Survival strategy logic, scroll prediction, and escape route validation."""

import heapq
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

    def find_factory_escape_with_wall_removals(
        self,
        factory: Robot,
        map_memory: MapMemory,
        current_step: int,
        south_bound: int,
        north_bound: int
    ) -> Tuple[bool, List[Tuple[int, int]], List[Tuple[int, int]]]:
        """Find the shortest path to safety for the factory, allowing wall removals at a cost.

        Uses Dijkstra's algorithm where:
        - Moving through passable cells has cost 1
        - Moving through removable walls has cost 15 (representing clearing delay)
        - Fixed walls are impassable

        Returns:
            (success: bool, escape_path: List[Tuple[int, int]], walls_to_remove: List[Tuple[int, int]])
        """
        # Predict where the scroll boundary will be when we need to be safe
        # Factory moves every 2 turns, so we need to look ahead further
        turns_to_check = 20  # Increased look-ahead for factory escape
        future_sb = predict_future_boundary(current_step, south_bound, turns_to_check)

        # If factory is already below or at danger, it's not safe
        if factory.pos[1] <= south_bound:
            return False, [], []

        # Dijkstra's algorithm
        # Priority queue storing: (cost, position, path_so_far, walls_removed_so_far)
        open_set = []
        heapq.heappush(open_set, (0, factory.pos, [factory.pos], []))

        # Store visited positions with their minimum cost
        visited_costs: Dict[Tuple[int, int], float] = {factory.pos: 0.0}

        width = map_memory.width

        # For reconstructing the path
        came_from: Dict[Tuple[int, int], Tuple[Optional[Tuple[int, int]], bool]] = {}
        # The boolean indicates whether the move to this position involved removing a wall

        while open_set:
            current_cost, current_pos, path_so_far, walls_removed_so_far = heapq.heappop(open_set)

            # Check if we've reached safety (above the future scroll boundary)
            if current_pos[1] > future_sb:
                # Reconstruct the path and walls to remove
                path = []
                walls_to_remove = []
                current = current_pos

                while current in came_from:
                    prev_pos, removed_wall = came_from[current]
                    if prev_pos is not None:  # Not the starting position
                        path.append(current)
                        if removed_wall:
                            walls_to_remove.append(current)
                    current = prev_pos

                path.append(factory.pos)
                path.reverse()
                walls_to_remove.reverse()

                return True, path, walls_to_remove

            # Explore neighbors
            x, y = current_pos
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:  # North, South, East, West
                neighbor = (x + dx, y + dy)
                nx, ny = neighbor

                # Boundary check
                if not (0 <= nx < width and south_bound <= ny <= north_bound):
                    continue

                # Check if we can move to this position
                current_wall_value = map_memory.get_wall_value(current_pos)
                neighbor_wall_value = map_memory.get_wall_value(neighbor)

                # Determine if there's a wall between current position and neighbor
                # We need to check the appropriate wall bit based on direction
                wall_blocking = False
                wall_to_remove = None

                if dx == 0 and dy == -1:  # Moving North
                    # Check north wall of current position or south wall of neighbor
                    if (current_wall_value != -1 and (current_wall_value & 1)) or \
                       (neighbor_wall_value != -1 and (neighbor_wall_value & 4)):
                        wall_blocking = True
                        wall_to_remove = neighbor  # We'll remove the wall at the neighbor position
                elif dx == 0 and dy == 1:  # Moving South
                    # Check south wall of current position or north wall of neighbor
                    if (current_wall_value != -1 and (current_wall_value & 4)) or \
                       (neighbor_wall_value != -1 and (neighbor_wall_value & 1)):
                        wall_blocking = True
                        wall_to_remove = neighbor
                elif dx == 1 and dy == 0:  # Moving East
                    # Check east wall of current position or west wall of neighbor
                    if (current_wall_value != -1 and (current_wall_value & 2)) or \
                       (neighbor_wall_value != -1 and (neighbor_wall_value & 8)):
                        wall_blocking = True
                        wall_to_remove = neighbor
                elif dx == -1 and dy == 0:  # Moving West
                    # Check west wall of current position or east wall of neighbor
                    if (current_wall_value != -1 and (current_wall_value & 8)) or \
                       (neighbor_wall_value != -1 and (neighbor_wall_value & 2)):
                        wall_blocking = True
                        wall_to_remove = neighbor

                # If there's a wall blocking, check if we can remove it
                if wall_blocking:
                    # Check if it's a fixed wall (cannot be removed)
                    if wall_to_remove is not None:
                        wx, wy = wall_to_remove
                        from utils.walls import is_fixed_wall
                        # Determine direction from current to neighbor for wall check
                        if dx == 0 and dy == -1:  # North
                            direction = "NORTH"
                        elif dx == 0 and dy == 1:  # South
                            direction = "SOUTH"
                        elif dx == 1 and dy == 0:  # East
                            direction = "EAST"
                        elif dx == -1 and dy == 0:  # West
                            direction = "WEST"

                        if is_fixed_wall(wx, direction, width):
                            # Fixed wall, cannot pass
                            continue

                    # We can remove this wall, but it costs extra
                    move_cost = 15  # Cost for removing a wall
                    new_walls_removed = walls_removed_so_far + [wall_to_remove] if wall_to_remove else walls_removed_so_far
                else:
                    # No wall, normal movement cost
                    move_cost = 1
                    new_walls_removed = walls_removed_so_far

                # Calculate new cost
                new_cost = current_cost + move_cost

                # If we found a better path to this neighbor, update it
                if neighbor not in visited_costs or new_cost < visited_costs[neighbor]:
                    visited_costs[neighbor] = new_cost
                    came_from[neighbor] = (current_pos, wall_to_remove is not None)
                    new_path = path_so_far + [neighbor]
                    heapq.heappush(open_set, (new_cost, neighbor, new_path, new_walls_removed))

        # If we exhausted all possibilities and didn't find a path to safety
        return False, [], []
