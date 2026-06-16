"""Greedy rule-based opponent for local testing."""

from random import choice

def agent(obs, config):
    actions = {}
    width = config.width
    my_robots = {
        uid: data for uid, data in obs.robots.items()
        if data[4] == obs.player
    }

    # Group robots
    factories = [uid for uid, data in my_robots.items() if data[0] == 0]
    scouts = [uid for uid, data in my_robots.items() if data[0] == 1]
    workers = [uid for uid, data in my_robots.items() if data[0] == 2]
    miners = [uid for uid, data in my_robots.items() if data[0] == 3]

    for uid, data in my_robots.items():
        rtype, col, row, energy = data[0], data[1], data[2], data[3]
        build_cd = data[7] if len(data) > 7 else 0

        idx = (row - obs.southBound) * width + col
        w = obs.walls[idx] if 0 <= idx < len(obs.walls) and obs.walls[idx] != -1 else 0

        if rtype == 0:  # Factory
            # Spawn worker if we have none, else spawn miner, else spawn scouts
            has_worker = any(obs.robots[ruid][0] == 2 for ruid, rdata in obs.robots.items() if rdata[4] == obs.player)
            has_miner = any(obs.robots[ruid][0] == 3 for ruid, rdata in obs.robots.items() if rdata[4] == obs.player)
            
            if not has_worker and energy >= config.workerCost and build_cd == 0:
                actions[uid] = "BUILD_WORKER"
            elif not has_miner and energy >= config.minerCost and build_cd == 0:
                actions[uid] = "BUILD_MINER"
            elif energy >= config.scoutCost and build_cd == 0:
                actions[uid] = "BUILD_SCOUT"
            else:
                # Move north if clear, else jump
                if not (w & 1):
                    actions[uid] = "NORTH"
                else:
                    actions[uid] = "JUMP_NORTH"
                    
        elif rtype == 1:  # Scout
            # Head to nearest crystal
            nearest_crystal = None
            min_dist = float('inf')
            for pos_str, cry_energy in obs.crystals.items():
                cx, cy = map(int, pos_str.split(","))
                dist = abs(col - cx) + abs(row - cy)
                if dist < min_dist:
                    min_dist = dist
                    nearest_crystal = (cx, cy)
            
            if nearest_crystal:
                cx, cy = nearest_crystal
                dx, dy = cx - col, cy - row
                # Try to move towards crystal
                if dy > 0 and not (w & 1): actions[uid] = "NORTH"
                elif dx > 0 and not (w & 2): actions[uid] = "EAST"
                elif dy < 0 and not (w & 4): actions[uid] = "SOUTH"
                elif dx < 0 and not (w & 8): actions[uid] = "WEST"
                else: actions[uid] = "IDLE"
            else:
                # Move north if possible, else random
                if not (w & 1):
                    actions[uid] = "NORTH"
                else:
                    passable = []
                    if not (w & 2): passable.append("EAST")
                    if not (w & 8): passable.append("WEST")
                    actions[uid] = choice(passable) if passable else "IDLE"

        elif rtype == 2:  # Worker
            # Remove any wall blocking path north, else move north
            if (w & 1) and energy >= config.wallRemoveCost:
                actions[uid] = "REMOVE_NORTH"
            elif not (w & 1):
                actions[uid] = "NORTH"
            else:
                # Try to go east/west
                passable = []
                if not (w & 2): passable.append("EAST")
                if not (w & 8): passable.append("WEST")
                actions[uid] = choice(passable) if passable else "IDLE"

        elif rtype == 3:  # Miner
            # Transform if on node
            is_on_node = f"{col},{row}" in obs.miningNodes
            if is_on_node and energy >= config.transformCost:
                actions[uid] = "TRANSFORM"
            else:
                # Head towards nearest mining node
                nearest_node = None
                min_dist = float('inf')
                for pos_str in obs.miningNodes.keys():
                    nx, ny = map(int, pos_str.split(","))
                    dist = abs(col - nx) + abs(row - ny)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_node = (nx, ny)
                        
                if nearest_node:
                    nx, ny = nearest_node
                    dx, dy = nx - col, ny - row
                    if dy > 0 and not (w & 1): actions[uid] = "NORTH"
                    elif dx > 0 and not (w & 2): actions[uid] = "EAST"
                    elif dy < 0 and not (w & 4): actions[uid] = "SOUTH"
                    elif dx < 0 and not (w & 8): actions[uid] = "WEST"
                    else: actions[uid] = "IDLE"
                else:
                    if not (w & 1): actions[uid] = "NORTH"
                    else: actions[uid] = "IDLE"

    return actions
