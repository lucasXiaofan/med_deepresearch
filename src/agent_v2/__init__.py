"""agent_v2 - Skill-based agent framework with session support.

Quick Start:
    from agent_v2 import Agent, create_agent

    # Basic agent
    agent = Agent()
    result = agent.run("Search for the latest Python release")

    # Agent with skills
    agent = Agent(skills=["med-deepresearch"])
    result = agent.run("Diagnose this case...")

    # Agent with session
    agent = Agent(session_id="task_123")
    result = agent.run("Continue from where we left off")
"""
from .agent import Agent, create_agent
from .session import Session, list_sessions
from .skill_loader import SkillLoader, Skill

__all__ = [
    "Agent",
    "create_agent",
    "Session",
    "list_sessions",
    "SkillLoader",
    "Skill",
]

__version__ = "0.1.0"
