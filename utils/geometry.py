"""Geometric and grid math utilities for the Crawl AI Agent."""

from typing import Tuple
from agent.constants import DIR_TO_DELTA, DELTA_TO_DIR, DIR_IDLE

def get_manhattan_distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
    """Calculate Manhattan distance between two points."""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def get_offset_position(pos: Tuple[int, int], direction: str) -> Tuple[int, int]:
    """Get the position after moving in the given direction."""
    delta = DIR_TO_DELTA.get(direction, (0, 0))
    return pos[0] + delta[0], pos[1] + delta[1]

def get_direction_from_offset(start: Tuple[int, int], end: Tuple[int, int]) -> str:
    """Get direction from start to end (must be adjacent)."""
    delta = (end[0] - start[0], end[1] - start[1])
    return DELTA_TO_DIR.get(delta, DIR_IDLE)

def get_mirrored_col(col: int, width: int) -> int:
    """Calculate mirrored X coordinate (East-West symmetry)."""
    return width - 1 - col

def get_mirrored_pos(pos: Tuple[int, int], width: int) -> Tuple[int, int]:
    """Calculate mirrored position based on East-West symmetry."""
    return get_mirrored_col(pos[0], width), pos[1]

def is_in_bounds(col: int, row: int, width: int, south_bound: int, north_bound: int) -> bool:
    """Check if a coordinate is within the board column range and row range."""
    return 0 <= col < width and south_bound <= row <= north_bound
