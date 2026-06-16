"""Production-grade Kaggle Maze Crawler Agent entry point."""

from agent.agent_v2 import agent_v2

def agent(obs, config):
    """The agent function called by Kaggle Environments on each step."""
    return agent_v2(obs, config)