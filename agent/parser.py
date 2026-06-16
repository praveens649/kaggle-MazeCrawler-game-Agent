"""Parser module to decode raw Kaggle observations and configs."""

from typing import Tuple
from agent.state import Robot, Mine, GameConfig, ObsState

def parse_pos(pos_str: str) -> Tuple[int, int]:
    """Helper to parse a 'col,row' string to a tuple."""
    col_str, row_str = pos_str.split(",")
    return int(col_str), int(row_str)

def parse_config(config) -> GameConfig:
    """Parse configuration dynamically mapping camelCase parameters."""
    def get(name, default):
        if hasattr(config, name):
            return getattr(config, name)
        if isinstance(config, dict) and name in config:
            return config[name]
        return default

    return GameConfig(
        width=get("width", 20),
        height=get("height", 20),
        episode_steps=get("episodeSteps", 501),
        factory_energy=get("factoryEnergy", 1000),
        scout_cost=get("scoutCost", 50),
        worker_cost=get("workerCost", 200),
        miner_cost=get("minerCost", 300),
        scout_max_energy=get("scoutMaxEnergy", 100),
        worker_max_energy=get("workerMaxEnergy", 300),
        miner_max_energy=get("minerMaxEnergy", 500),
        wall_build_cost=get("wallBuildCost", 100),
        wall_remove_cost=get("wallRemoveCost", 100),
        transform_cost=get("transformCost", 100),
        mine_max_energy=get("mineMaxEnergy", 1000),
        mine_rate=get("mineRate", 50),
        energy_per_turn=get("energyPerTurn", 1),
        factory_build_cooldown=get("factoryBuildCooldown", 10),
        factory_jump_cooldown=get("factoryJumpCooldown", 20),
        factory_move_period=get("factoryMovePeriod", 2),
        worker_move_period=get("workerMovePeriod", 2),
        miner_move_period=get("minerMovePeriod", 2),
        vision_factory=get("visionFactory", 4),
        vision_scout=get("visionScout", 5),
        vision_worker=get("visionWorker", 3),
        vision_miner=get("visionMiner", 3),
        scroll_start_interval=get("scrollStartInterval", 4),
        scroll_end_interval=get("scrollEndInterval", 1),
        scroll_ramp_steps=get("scrollRampSteps", 400)
    )

def parse_obs(obs) -> ObsState:
    """Parse standard environment observations into the typed ObsState object."""
    def get_attr(name):
        if hasattr(obs, name):
            return getattr(obs, name)
        if isinstance(obs, dict) and name in obs:
            return obs[name]
        raise KeyError(f"Attribute {name} not found in observation")

    player_id = get_attr("player")
    south_bound = get_attr("southBound")
    north_bound = get_attr("northBound")
    raw_walls = get_attr("walls")

    # Parse Robots
    raw_robots = get_attr("robots")
    robots = {}
    for uid, data in raw_robots.items():
        rtype = data[0]
        col = data[1]
        row = data[2]
        energy = data[3]
        owner = data[4]
        move_cd = data[5]
        jump_cd = data[6] if len(data) > 6 else 0
        build_cd = data[7] if len(data) > 7 else 0
        
        robots[uid] = Robot(
            uid=uid,
            rtype=rtype,
            pos=(col, row),
            energy=energy,
            owner=owner,
            move_cd=move_cd,
            jump_cd=jump_cd,
            build_cd=build_cd
        )

    # Parse Crystals
    raw_crystals = get_attr("crystals")
    crystals = {}
    for pos_str, energy in raw_crystals.items():
        pos = parse_pos(pos_str)
        crystals[pos] = energy

    # Parse Mines
    raw_mines = get_attr("mines")
    mines = {}
    for pos_str, data in raw_mines.items():
        pos = parse_pos(pos_str)
        energy = data[0]
        max_energy = data[1]
        owner = data[2]
        mines[pos] = Mine(
            pos=pos,
            energy=energy,
            max_energy=max_energy,
            owner=owner
        )

    # Parse Mining Nodes
    raw_mining_nodes = get_attr("miningNodes")
    mining_nodes = set()
    for pos_str in raw_mining_nodes.keys():
        mining_nodes.add(parse_pos(pos_str))

    return ObsState(
        player_id=player_id,
        south_bound=south_bound,
        north_bound=north_bound,
        robots=robots,
        crystals=crystals,
        mines=mines,
        mining_nodes=mining_nodes,
        raw_walls=list(raw_walls)
    )
