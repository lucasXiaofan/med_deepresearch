#!/usr/bin/env python3
"""Test that agent synthesizes findings when max_turns is reached."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_v2.agent import Agent

# Create an agent with very low max_turns to trigger synthesis
agent = Agent(
    skills=[],
    max_turns=2,  # Very low to force max_turns scenario
    session_dir=Path("src/agent_v2/sessions"),
    log_dir=Path("src/agent_v2/logs")
)

# Give it a task that requires multiple steps
result = agent.run(
    "List 10 prime numbers and explain why they are prime. "
    "Use the bash tool to calculate if needed."
)

print("=" * 60)
print("AGENT RESULT:")
print("=" * 60)
print(result)
print("=" * 60)

# Check that we got a synthesis, not just "Reached maximum reasoning steps"
if "Reached maximum reasoning steps" in result and "synthesize" not in result.lower():
    print("❌ FAILED: Agent did not synthesize findings")
    sys.exit(1)
else:
    print("✓ PASSED: Agent provided synthesis or completed task")
    sys.exit(0)
