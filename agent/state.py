"""Game state models and configuration representation for the Crawl AI Agent."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set

@dataclass
class Robot:
    uid: str
    rtype: int         # 0=Factory, 1=Scout, 2=Worker, 3=Miner
    pos: Tuple[int, int]  # (col, row)
    energy: int
    owner: int         # 0 or 1
    move_cd: int
    jump_cd: int = 0
    build_cd: int = 0

    @property
    def col(self) -> int:
        return self.pos[0]

    @property
    def row(self) -> int:
        return self.pos[1]

@dataclass
class Mine:
    pos: Tuple[int, int]  # (col, row)
    energy: int
    max_energy: int
    owner: int

@dataclass
class GameConfig:
    width: int = 20
    height: int = 20
    episode_steps: int = 501
    factory_energy: int = 1000
    scout_cost: int = 50
    worker_cost: int = 200
    miner_cost: int = 300
    scout_max_energy: int = 100
    worker_max_energy: int = 300
    miner_max_energy: int = 500
    wall_build_cost: int = 100
    wall_remove_cost: int = 100
    transform_cost: int = 100
    mine_max_energy: int = 1000
    mine_rate: int = 50
    energy_per_turn: int = 1
    factory_build_cooldown: int = 10
    factory_jump_cooldown: int = 20
    factory_move_period: int = 2
    worker_move_period: int = 2
    miner_move_period: int = 2
    vision_factory: int = 4
    vision_scout: int = 5
    vision_worker: int = 3
    vision_miner: int = 3
    scroll_start_interval: int = 4
    scroll_end_interval: int = 1
    scroll_ramp_steps: int = 400

@dataclass
class ObsState:
    player_id: int
    south_bound: int
    north_bound: int
    robots: Dict[str, Robot] = field(default_factory=dict)
    crystals: Dict[Tuple[int, int], int] = field(default_factory=dict)
    mines: Dict[Tuple[int, int], Mine] = field(default_factory=dict)
    mining_nodes: Set[Tuple[int, int]] = field(default_factory=set)
    raw_walls: List[int] = field(default_factory=list)
    
    @property
    def my_robots(self) -> Dict[str, Robot]:
        return {uid: r for uid, r in self.robots.items() if r.owner == self.player_id}
        
    @property
    def enemy_robots(self) -> Dict[str, Robot]:
        return {uid: r for uid, r in self.robots.items() if r.owner != self.player_id}
        
    @property
    def my_factory(self) -> Robot:
        for r in self.my_robots.values():
            if r.rtype == 0:
                return r
        raise ValueError("My factory was not found in active robots!")
        
    @property
    def enemy_factory(self) -> Robot:
        for r in self.enemy_robots.values():
            if r.rtype == 0:
                return r
        raise ValueError("Enemy factory was not found in active robots!")

    def has_enemy_factory(self) -> bool:
        return any(r.rtype == 0 for r in self.enemy_robots.values())
