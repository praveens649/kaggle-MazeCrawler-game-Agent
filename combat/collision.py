"""Predictive collision simulator to avoid friendly fire."""

from typing import Dict, Tuple, List, Set
from agent.state import ObsState, Robot
from agent.constants import DIR_TO_DELTA, TYPE_FACTORY
from utils.geometry import get_offset_position

def resolve_friendly_collisions(
    proposed_actions: Dict[str, str],
    obs: ObsState,
    width: int
) -> Dict[str, str]:
    """Inspect proposed actions and adjust them to prevent friendly unit collisions.
    
    Friendly fire rules:
    - Same-type units ending on the same cell destroy both.
    - Spawning onto an occupied cell triggers combat.
    
    Strategy:
    1. Calculate landing cells for all robots based on proposed actions.
    2. Identify collisions of same-type units.
    3. Greedily resolve by forcing one of the colliding units to IDLE.
    4. Repeat until stable.
    """
    adjusted_actions = dict(proposed_actions)
    my_robots = obs.my_robots
    
    # Run resolution loop
    for iteration in range(10):  # Cap iterations to prevent infinite loops
        collision_detected = False
        
        # Maps target_pos -> list of (uid, type)
        occupied_targets: Dict[Tuple[int, int], List[Tuple[str, int]]] = {}
        
        # 1. Map target positions for existing units
        for uid, robot in my_robots.items():
            action = adjusted_actions.get(uid, "IDLE")
            
            # Default landing position is current position
            target_pos = robot.pos
            
            if action in ["NORTH", "SOUTH", "EAST", "WEST"]:
                target_pos = get_offset_position(robot.pos, action)
            elif action.startswith("JUMP_"):
                # Jump moves 2 cells
                jump_dir = action.split("_")[1]
                delta = DIR_TO_DELTA.get(jump_dir, (0, 0))
                target_pos = (robot.pos[0] + delta[0] * 2, robot.pos[1] + delta[1] * 2)
                
            occupied_targets.setdefault(target_pos, []).append((uid, robot.rtype))
            
        # 2. Add virtual unit if Factory builds
        for uid, robot in my_robots.items():
            if robot.rtype == 0:  # Factory
                action = adjusted_actions.get(uid, "IDLE")
                if action in ["BUILD_SCOUT", "BUILD_WORKER", "BUILD_MINER"]:
                    spawn_pos = (robot.col, robot.row + 1)
                    spawn_type = 1 if action == "BUILD_SCOUT" else 2 if action == "BUILD_WORKER" else 3
                    occupied_targets.setdefault(spawn_pos, []).append(("SPAWNED_VIRTUAL", spawn_type))

        # 3. Detect and resolve collisions (any multi-occupancy of a cell)
        for target_pos, occupants in list(occupied_targets.items()):
            if len(occupants) > 1:
                # Collision detected!
                collision_detected = True
                
                # Separate occupants into stationary and moving
                moving_uids = []
                stationary_uids = []
                for uid, rtype in occupants:
                    if uid == "SPAWNED_VIRTUAL":
                        stationary_uids.append((uid, rtype))
                    else:
                        act = adjusted_actions.get(uid, "IDLE")
                        if act in ["NORTH", "SOUTH", "EAST", "WEST", "JUMP_NORTH", "JUMP_SOUTH", "JUMP_EAST", "JUMP_WEST"]:
                            moving_uids.append((uid, rtype))
                        else:
                            stationary_uids.append((uid, rtype))
                
                # We must force all but one unit to IDLE to resolve collision.
                # Exception: If our Factory is moving and is in scroll danger, it MUST move.
                # We check if Factory is one of the moving occupants.
                factory_must_move = False
                factory_uid = None
                for uid, rtype in moving_uids:
                    if rtype == 0:  # Factory
                        # Check if factory is in scroll danger
                        factory_robot = my_robots.get(uid)
                        if factory_robot and factory_robot.row <= obs.south_bound + 3:
                            factory_must_move = True
                            factory_uid = uid
                            break
                
                uids_to_force_idle = []
                
                if factory_must_move and factory_uid:
                    # Factory has absolute priority. Keep factory, force everyone else to IDLE.
                    for u, r in occupants:
                        if u != factory_uid and u != "SPAWNED_VIRTUAL":
                            uids_to_force_idle.append(u)
                else:
                    # Normal resolution:
                    if stationary_uids:
                        # Keep the first stationary unit
                        for u, r in stationary_uids[1:]:
                            if u != "SPAWNED_VIRTUAL":
                                uids_to_force_idle.append(u)
                        # Force all moving units to IDLE
                        for u, r in moving_uids:
                            uids_to_force_idle.append(u)
                    else:
                        # All are moving. Keep the strongest unit.
                        # Strength score: Factory(0)->4, Miner(3)->3, Worker(2)->2, Scout(1)->1.
                        def get_strength(rtype):
                            if rtype == 0: return 4
                            if rtype == 3: return 3
                            if rtype == 2: return 2
                            return 1
                        
                        moving_uids.sort(key=lambda x: get_strength(x[1]), reverse=True)
                        # Keep the strongest, force others to IDLE
                        for u, r in moving_uids[1:]:
                            uids_to_force_idle.append(u)
                            
                for u in uids_to_force_idle:
                    adjusted_actions[u] = "IDLE"

            # B: Factory Spawn collision (if factory spawns and the target cell has a friendly unit remaining on it)
            # Check if "SPAWNED_VIRTUAL" is in occupants and there are other occupants
            # Note: if we cancelled the other unit's movement, it is now stationary on the spawn cell.
            # We must cancel the factory's spawn to avoid crushing it.
            has_spawn = any(uid == "SPAWNED_VIRTUAL" for uid, _ in occupants)
            if has_spawn and len(occupants) > 1:
                # Cancel the Factory's build action to avoid crushing our own unit
                for factory_uid, factory_robot in my_robots.items():
                    if factory_robot.rtype == 0:
                        fact_action = adjusted_actions.get(factory_uid, "IDLE")
                        if fact_action in ["BUILD_SCOUT", "BUILD_WORKER", "BUILD_MINER"]:
                            adjusted_actions[factory_uid] = "IDLE"
                            collision_detected = True

        if not collision_detected:
            break
            
    return adjusted_actions
