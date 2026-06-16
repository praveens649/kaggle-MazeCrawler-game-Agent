Crawl
A maze crawling strategy game with fog of war. Two players navigate an infinite northward-scrolling maze, building robots to explore, collect energy, and outlast the opponent.

Overview
Each player starts with a single Factory robot near the bottom of a 20x20 maze. The maze scrolls northward over time — the southern boundary advances, destroying anything left behind. The last player with a surviving factory wins.

The maze has east/west symmetry: the left half mirrors the right half, with occasional doors connecting the two sides. Players start on opposite halves.

Robot Types
Type	Cost	Max Energy	Move Period	Vision	Special Abilities
Factory	—	unlimited	2 turns	4	BUILD, JUMP (20-turn CD), indestructible
Scout	50	100	1 turn	5	Fast explorer
Worker	200	300	2 turns	3	BUILD_DIR / REMOVE_DIR walls (100 energy)
Miner	300	500	2 turns	3	TRANSFORM into energy mine (requires mining node)
All robots consume 1 energy per turn. Robots with 0 energy are forced idle.

Actions
Each turn, you return a dictionary mapping robot UIDs to action strings.

Movement
NORTH, SOUTH, EAST, WEST — Move one cell in that direction (blocked by walls). A unit that successfully moves off the north or south edge of the board (no wall blocking) is destroyed. East/west are always blocked by perimeter walls.
Factory Actions
BUILD_SCOUT, BUILD_WORKER, BUILD_MINER — Spawn a new robot in the cell north of the factory. Requires no wall between factory and spawn cell. 10-turn cooldown between builds. The new robot is placed before the movement phase, so it counts as a stationary occupant during combat — if an enemy on that cell moves away the same turn, the new robot lands safely; otherwise crush combat resolves on the spawn cell.
JUMP_NORTH, JUMP_SOUTH, JUMP_EAST, JUMP_WEST — Leap 2 cells in a direction, ignoring all walls. The jump always happens and the cooldown is consumed. If the landing cell is off the board, the factory is destroyed. 20-turn cooldown.
Worker Actions
BUILD_NORTH, BUILD_SOUTH, BUILD_EAST, BUILD_WEST — Add a wall between the worker's cell and the adjacent cell in that direction. Costs 100 energy. The worker survives.
REMOVE_NORTH, REMOVE_SOUTH, REMOVE_EAST, REMOVE_WEST — Remove the wall between the worker's cell and the adjacent cell. Costs 100 energy. The worker survives.
Fixed walls (cannot be modified): the outer perimeter (E/W of the leftmost and rightmost columns) and the central mirror axis (E of column width/2 - 1 and W of column width/2). BUILD/REMOVE on a fixed wall, or where the wall is already in the requested state, still costs 100 energy but has no effect. Fixed walls are drawn as double lines in the visualizer.

Miner Actions
TRANSFORM — Destroy the miner and create an energy mine at its position. Requires the miner to be standing on a mining node. Costs 100 energy. The mine receives the miner's remaining energy (up to mine max).
Other
TRANSFER_NORTH, TRANSFER_SOUTH, TRANSFER_EAST, TRANSFER_WEST — Send all energy to an adjacent friendly robot. Blocked by walls. Target's energy is capped at its max (factory has no cap).
IDLE — Do nothing.
Combat
When two or more robots end the turn on the same cell, crush rules apply — ownership doesn't matter; friendly fire is real.

Crush hierarchy: Factory > Miner > Worker > Scout. The stronger type destroys the weaker.
Same type: Both (or all) robots of that type are destroyed. Two friendly scouts walking onto the same cell mutually annihilate.
Factory: Indestructible against any non-factory unit (friendly or enemy) and crushes them. Two enemy factories on the same cell mutually destroy each other (game ends, see Win Conditions).
Crystal on combat cell: The surviving robot (if any) collects the crystal energy. If no robot survives, the crystal is consumed.
Spawning a robot onto an occupied cell triggers combat normally — including friendly fire if the spawn cell is held by your own unit.

Map Features
Crystals
Scattered throughout the maze (6% density per cell). Any robot moving onto a crystal collects its energy (10-50). Crystals are visible only within vision range and are not remembered after leaving range.

Mining Nodes
Rare locations (3% density) marked on the map where miners can transform into mines. A mining node is consumed when a mine is created on it. Mining nodes never overlap with crystals.

Mines
Created by miners using TRANSFORM on a mining node. Mines generate 50 energy per turn up to a maximum of 1000 energy. Friendly robots standing on a mine collect energy from it. Mines are remembered once discovered (even outside vision range).

Fog of War
Each robot has a vision range (Manhattan distance). You can only see what's within the combined vision of all your robots.

Data	Visible in range	Remembered after leaving range
Walls/layout	Yes	Yes (permanent)
Crystals	Yes	No
Enemy robots	Yes	No
Own robots	Always	N/A
Mines (any owner)	Yes	Yes (permanent, last-known state)
Mining nodes	Yes	No
Maze Scrolling
The southern boundary advances over time, destroying all robots, mines, and crystals below it.

Start: Scrolls once every 4 turns
Ramp: Linearly increases speed over 400 steps
End: Scrolls every turn from step 400 onward (until game end at step 500)
If a factory falls below the southern boundary, that player is eliminated.

Turn Processing Order
Cooldown tick — Decrement move, jump, and build cooldowns
Action validation — Verify action legality
Energy consumption — Each robot loses 1 energy; 0-energy robots forced idle
Special actions — TRANSFORM (miner), BUILD_DIR/REMOVE_DIR (worker walls), BUILD_SCOUT/WORKER/MINER (factory), TRANSFER (in that order)
Movement + combat — Simultaneous movement, then resolve collisions
Crystal collection — Robots on crystal cells collect energy
Mine energy fill — Robots on friendly mines collect energy
Mine generation — Each mine gains 50 energy (up to max 1000)
Scroll advancement — Advance boundaries, generate new row, place crystals/nodes
Boundary destruction — Destroy robots/mines below southern boundary
Win condition check
Update observations — Compute fog of war, build per-player views
Win Conditions
Survival: If one factory is destroyed (by scrolling below the boundary), the other player wins.
Simultaneous elimination: If both factories are destroyed on the same turn (e.g. mutual factory collision, or both scrolled off), apply the tiebreaker cascade.
Time limit (step 500): If both factories are still alive, apply the tiebreaker cascade.
Tiebreaker cascade
Total energy across all robots — higher wins
Unit count across all robots — higher wins
True draw — both players receive reward 0.5
Reward
Alive (mid-game): Total energy across all your robots
Win by tiebreaker cascade: 1
Loss by tiebreaker cascade: 0
Draw: 0.5
Eliminated (opponent survives): step_eliminated - episodeSteps - 1 (negative value); winner gets total energy
Observation Format
def agent(obs, config):
    obs.player        # Your player index (0 or 1)
    obs.walls         # Flat array: index = (row - southBound) * width + col
                      # Values: wall bitfield, -1 = undiscovered
    obs.crystals      # {"col,row": energy} — only currently visible
    obs.robots        # {"uid": [type, col, row, energy, owner, move_cd, jump_cd, build_cd]}
    obs.mines         # {"col,row": [energy, maxEnergy, owner]} — remembered once seen
    obs.miningNodes   # {"col,row": 1} — only currently visible
    obs.southBound    # Current southern boundary row
    obs.northBound    # Current northern boundary row
Wall Bitfield
N = 1, E = 2, S = 4, W = 8
Check for a wall: if wall_value & 1: means there's a north wall. Fixed walls (perimeter and middle axis) have the same bitfield representation but cannot be modified by workers; the visualizer renders them as double lines.

Quick Start
from kaggle_environments import make

def my_agent(obs, config):
    actions = {}
    for uid, data in obs.robots.items():
        rtype, col, row, energy, owner = data[0], data[1], data[2], data[3], data[4]
        if owner != obs.player:
            continue
        if rtype == 0:  # Factory
            if energy >= config.workerCost:
                actions[uid] = "BUILD_WORKER"
            else:
                actions[uid] = "NORTH"
        else:
            actions[uid] = "NORTH"
    return actions

env = make("crawl", configuration={"randomSeed": 42})
env.run([my_agent, "random"])
env.render(mode="ipython", width=800, height=800)
Configuration Defaults
Parameter	Default	Description
episodeSteps	501	Max turns
width	20	Maze width
height	20	Visible window height
factoryEnergy	1000	Starting factory energy
scoutCost	50	Energy to build scout (also the energy a freshly-built scout spawns with)
workerCost	200	Energy to build worker (also the energy a freshly-built worker spawns with)
minerCost	300	Energy to build miner (also the energy a freshly-built miner spawns with)
scoutMaxEnergy	100	Max energy a scout can carry
workerMaxEnergy	300	Max energy a worker can carry
minerMaxEnergy	500	Max energy a miner can carry
wallBuildCost	100	Energy per worker BUILD_DIR (charged even on no-op)
wallRemoveCost	100	Energy per worker REMOVE_DIR (charged even on no-op)
transformCost	100	Energy for miner transform
mineMaxEnergy	1000	Max energy a mine stores
mineRate	50	Mine energy generation per turn
energyPerTurn	1	Energy consumed per robot per turn
factoryBuildCooldown	10	Turns between builds
factoryJumpCooldown	20	Turns between jumps
factoryMovePeriod	2	Factory moves every N turns
workerMovePeriod	2	Worker moves every N turns
minerMovePeriod	2	Miner moves every N turns
visionFactory	4	Factory vision range
visionScout	5	Scout vision range
visionWorker	3	Worker vision range
visionMiner	3	Miner vision range
scrollStartInterval	4	Initial turns between scrolls
scrollEndInterval	1	Final turns between scrolls
scrollRampSteps	400	Step when max scroll speed reached
crystalDensity	0.06	Crystal spawn probability per cell
miningNodeDensity	0.03	Mining node spawn probability per cell
doorProbability	0.08	Door probability between maze halves

---

## Game Feature & Implementation Efficiency

Our agent ([CrawlAgent](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent.py#L50) / [agent_v2](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent_v2.py#L421)) is designed to outperform baseline bots (e.g., standard random or greedy agents) by optimizing computation, prediction, and strategic execution. Below are the key engineering design features that ensure high efficiency:

### 1. Symmetry-Based Fog of War Mapping
The game board has East-West (horizontal) symmetry. Our [MapMemory](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/memory/map_memory.py#L27) model automatically mirrors any discovered cell's walls to its counterpart on the other half of the board using [mirror_wall_bitfield](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/memory/map_memory.py#L8). This:
- **Doubles exploration rate** without requiring physical robot movement.
- Allows the pathfinding module to pre-compute paths through unrevealed regions in the Fog of War.

### 2. Predictive Friendly Collision Simulator
Friendly fire (crush rules and same-type unit collisions) is a major hazard in Crawl. The bot incorporates a local **predictive collision resolution loop** in [resolve_friendly_collisions](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/combat/collision.py#L8) before submitting actions:
- Anticipates the landing coordinates of all friendly units and factory spawns.
- Resolves conflicts greedily: prioritizes factory survival and high-tier units, forcing others to `IDLE` or canceling build orders if the spawn gate is blocked.
- Avoids mutual annihilation of friendly scouts and workers, preserving material advantage.

### 3. Danger-Aware A* Pathfinder
Instead of running basic BFS/DFS, the bot uses a customized A* search algorithm in [find_safe_path](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/pathfinding/astar.py#L114) featuring a **dynamic safety cost function**:
- **Scroll Evasion:** Applies heavy exponential penalties to cells near the advancing southern boundary to prevent scroll deaths (see [get_safe_cell_cost](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/pathfinding/astar.py#L60)).
- **Threat Mitigation:** Dynamically reads enemy unit positions and adds steep cost weightings to adjacent cells, preventing units from walking into lethal encounters.
- **Scroll Prediction:** Validates coordinates to ensure a path remains above the predicted scroll boundary on arrival.

### 4. Proactive Path Excavation & Gate Clearance
Factory mobility is critical for late-game survival. 
- Workers proactively scan a 3-column corridor ahead of the factory and navigate to demolish any blocking walls.
- Robots spawned by the factory check if they are blocking the spawn gate and move immediately to clear it using [get_clear_gate_action](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent.py#L27), preventing factory construction blocks.

### 5. Multi-Tiered Target Scoring
Target selection in [choose_goal](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent_v2.py#L156) uses a specialized priority scoring matrix:
- **Scouts:** Target crystals and frontier cells, with high-energy scouts returning to transfer energy to the factory.
- **Miners:** Automatically navigate to and transform on mining nodes.
- **Workers:** Focus on clearing factory path blocks, or return to act as factory escorts.
- **Oscillation Mitigation:** Distance and visit-frequency penalties are combined with territorial home-side constraints to prevent infinite path oscillations (see [score_targets](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent_v2.py#L79)).

---

## Contributing

We welcome contributions to improve the agent's performance, heuristics, and architecture! 

### Project Structure Overview
- [agent/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent): Contains state representation, action parsing, and core agent entry points.
- [combat/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/combat): Friendly collision simulation and path deconfliction.
- [economy/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/economy): Logic for crystal collection, node mining, and energy transfer.
- [exploration/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/exploration): Frontier cell detection for mapping unrevealed areas.
- [pathfinding/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/pathfinding): Weighted A* pathfinding and BFS distance grids.
- [strategy/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/strategy): Macro scheduling, spawn logic, and factory survival metrics.
- [units/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/units): Custom behavior trees/decision logic for each robot class.
- [utils/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/utils): Coordinate geometry and wall checking helpers.
- [memory/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/memory): Shared memory representations for discovered walls and enemy movements.
- [debug/](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/debug): ASCII map visualizer and step logs.

### Contribution Guidelines
1. **Branching & PRs:** Create a descriptive feature branch from `main` (e.g., `feature/improved-worker-tunneling`). Submit pull requests detailing the changes and performance impact.
2. **Code Standards:** 
   - Write clean, modular, and self-documenting code.
   - Follow standard Python (PEP 8) style guidelines.
   - Do not store persistent game state in global variables that could persist across runs (reset state in [agent_v2](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/agent/agent_v2.py#L421) on step 0).
3. **Local Testing:**
   - Always run local games to verify that your changes do not break or regress the bot.
   - Test against baseline agents or previous versions:
     ```python
     from kaggle_environments import make
     env = make("crawl", debug=True)
     env.run(["main.py", "greedy_opponent.py"])
     ```
   - Run the custom debug scripts (e.g., [debug_step_83.py](file:///c:/Users/Praveen/kaggle-MazeCrawler-game/debug_step_83.py)) to reproduce specific edge cases and test hotfixes.
4. **Submitting to Kaggle:**
   - Ensure the submission can be bundled cleanly:
     ```bash
     tar -czf submission.tar.gz main.py agent/ combat/ economy/ exploration/ pathfinding/ strategy/ units/ utils/ memory/
     ```
   - Submit via the Kaggle CLI:
     ```bash
     kaggle competitions submit maze-crawler -f submission.tar.gz -m "Brief description of changes"
     ```