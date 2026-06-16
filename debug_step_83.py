import sys
import os
import json

workspace_dir = r"c:\Users\Praveen\kaggle-MazeCrawler-game"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from agent.parser import parse_config, parse_obs
from memory.memory import GameMemory
from strategy.survival_strategy import SurvivalStrategy
from units.factory_logic import get_factory_action
from combat.collision import resolve_friendly_collisions

def main():
    os.chdir(workspace_dir)
    
    match_data = json.load(open("logs/local_match.json"))
    steps = match_data["steps"]
    
    # Initialize memory
    memory = GameMemory()
    
    for step_num in range(85):
        step_data = steps[step_num][0]
        obs_raw = step_data["observation"]
        config_raw = match_data["configuration"]
        
        config_state = parse_config(config_raw)
        obs_state = parse_obs(obs_raw)
        
        # Update memory up to current step
        memory.update(obs_state, step_num)
        
        if step_num >= 80:
            my_factory = obs_state.my_factory
            survival = SurvivalStrategy()
            
            survivable, escape_path = survival.verify_factory_survivability(
                my_factory, memory.map, step_num, obs_state.south_bound, obs_state.north_bound
            )
            
            # Print Factory CD and other details
            print(f"\n--- Step {step_num} ---")
            print(f"Factory pos: {my_factory.pos}, move_cd: {my_factory.move_cd}, build_cd: {my_factory.build_cd}, energy: {my_factory.energy}")
            
            # Get proposed action
            proposed_act = get_factory_action(
                factory=my_factory,
                spawn_decision=None,
                escape_path=escape_path,
                map_memory=memory.map,
                width=config_state.width,
                south_bound=obs_state.south_bound,
                north_bound=obs_state.north_bound,
                config=config_state,
                current_step=step_num
            )
            
            # Find Miner 13-5
            miner_act = 'IDLE'
            proposed_actions = {
                '0-0': proposed_act,
            }
            if '13-5' in obs_state.my_robots:
                proposed_actions['13-5'] = 'IDLE'
                
            print(f"Proposed actions: {proposed_actions}")
            
            final_actions = resolve_friendly_collisions(
                proposed_actions=proposed_actions,
                obs=obs_state,
                width=config_state.width
            )
            print(f"Final actions after collision: {final_actions}")

if __name__ == "__main__":
    main()
