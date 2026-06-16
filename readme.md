

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