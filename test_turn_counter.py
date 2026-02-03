#!/usr/bin/env python3
"""Test that turn counter is shown to LLM."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_v2.agent import Agent

print("Creating agent with max_turns=5 to test turn counter...")

# Create agent with low max_turns to see counter in action
agent = Agent(
    skills=[],
    max_turns=5,
    session_dir=Path("src/agent_v2/sessions"),
    log_dir=Path("src/agent_v2/logs")
)

print(f"Agent session: {agent.session_id}")
print("Running agent...")

# Give it a task that will use multiple turns
result = agent.run("Use bash to list files in the current directory, then count them.")

print("\n" + "=" * 60)
print("RESULT:")
print("=" * 60)
print(result)
print("=" * 60)

# Check the trajectory to see turn counters
log_files = list(Path("src/agent_v2/logs").glob(f"run_*.json"))
if log_files:
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)

    with open(latest_log) as f:
        trajectory = json.load(f)

    print("\nTURN ANALYSIS:")
    print("-" * 60)
    for turn_record in trajectory.get("turns", []):
        turn_num = turn_record.get("turn")
        tool_calls = turn_record.get("tool_calls", [])

        print(f"\nTurn {turn_num}:")
        if tool_calls:
            for tc in tool_calls:
                result_preview = tc.get("result", "")[:200]
                has_counter = "[Turn" in result_preview
                print(f"  Tool: {tc.get('name')}")
                print(f"  Has counter: {'✓' if has_counter else '✗'}")
                if has_counter:
                    # Extract the counter part
                    import re
                    match = re.search(r'\[Turn \d+/\d+[^\]]*\]', result_preview)
                    if match:
                        print(f"  Counter: {match.group()}")

    print("\n" + "=" * 60)
    print(f"Termination reason: {trajectory.get('termination_reason')}")
    print(f"Total turns: {trajectory.get('total_turns')}")
    print("=" * 60)

print("\n✓ Test complete - check turn counters above")
