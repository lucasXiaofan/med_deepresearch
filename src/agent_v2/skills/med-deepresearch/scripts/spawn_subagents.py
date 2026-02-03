#!/usr/bin/env python3
"""Spawn multiple sub-agents in parallel to handle research tasks.

Usage:
    python scripts/spawn_subagents.py "task1" "task2" ["task3"] ["task4"] ["task5"]

This script:
1. Takes up to 5 research tasks as arguments (each task as a quoted string)
2. Creates sub-agents with predefined research prompt
3. Runs them in parallel using threads
4. Gathers all reports
5. Stores task assignments and reports in main agent's session

Example:
    python scripts/spawn_subagents.py \
        "Search for cases with fever and rash in children" \
        "Find cases with neurological symptoms" \
        "Research treatment outcomes for similar diagnoses"
"""

import sys
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent_v2.agent import Agent
from agent_v2.session import Session


def get_main_session():
    """Get the main agent's session from environment variables."""
    session_id = os.getenv("AGENT_SESSION_ID")
    session_dir = os.getenv("AGENT_SESSION_DIR")

    if not session_id or not session_dir:
        return None, "Error: AGENT_SESSION_ID and AGENT_SESSION_DIR environment variables not set"

    try:
        return Session(session_id=session_id, session_dir=Path(session_dir)), None
    except Exception as e:
        return None, f"Error loading session: {str(e)}"


def load_subagent_prompt():
    """Load the sub-agent system prompt from subagent_prompt.md."""
    prompt_file = Path(__file__).parent.parent / "subagent_prompt.md"

    if not prompt_file.exists():
        return None, f"Error: {prompt_file} not found"

    try:
        return prompt_file.read_text(encoding="utf-8"), None
    except Exception as e:
        return None, f"Error reading subagent prompt: {str(e)}"


def run_subagent(task_id: int, task_description: str, subagent_prompt: str, main_session_id: str):
    """Run a single sub-agent on a task.

    Args:
        task_id: Unique identifier for this task (1-5)
        task_description: The research task to perform
        subagent_prompt: System prompt for the sub-agent
        main_session_id: Main agent's session ID (for naming sub-agent sessions)

    Returns:
        Dict with task_id, task, status, and report/error
    """
    try:
        # Create sub-agent with custom system prompt
        # Each sub-agent gets its own session tied to the main session
        subagent_session_id = f"{main_session_id}_sub{task_id}"

        agent = Agent(
            session_id=subagent_session_id,
            skills=[],  # No skills - uses research_tools via bash directly
            custom_system_prompt=subagent_prompt,
            max_turns=7,  # Enough turns for thorough research
            temperature=0.3,
            agent_name=f"subagent-research-{task_id}"
        )

        # Run the sub-agent on the task
        result = agent.run(task_description)

        return {
            "task_id": task_id,
            "task": task_description,
            "status": "success",
            "report": result,
            "session_id": subagent_session_id
        }

    except Exception as e:
        return {
            "task_id": task_id,
            "task": task_description,
            "status": "error",
            "error": str(e),
            "report": None
        }


def main():
    """Main function to spawn sub-agents in parallel."""

    # Check arguments
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: spawn_subagents.py <task1> <task2> [task3] [task4] [task5]"
        }))
        sys.exit(1)

    # Get tasks (maximum 5)
    tasks = sys.argv[1:6]

    if len(tasks) > 5:
        print(json.dumps({
            "status": "error",
            "error": "Maximum 5 tasks allowed"
        }))
        sys.exit(1)

    # Load sub-agent prompt
    subagent_prompt, error = load_subagent_prompt()
    if error:
        print(json.dumps({"status": "error", "error": error}))
        sys.exit(1)

    # Get main session
    main_session, error = get_main_session()
    if error:
        print(json.dumps({"status": "error", "error": error}))
        sys.exit(1)

    main_session_id = main_session.session_id

    # Record task assignment in main session
    task_assignment = {
        "type": "subagent_spawn",
        "timestamp": datetime.now().isoformat(),
        "num_agents": len(tasks),
        "tasks": [
            {"task_id": i + 1, "task": task}
            for i, task in enumerate(tasks)
        ]
    }
    main_session.append_store(task_assignment)

    # Run sub-agents in parallel using ThreadPoolExecutor
    results = []

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(run_subagent, i + 1, task, subagent_prompt, main_session_id): i
            for i, task in enumerate(tasks)
        }

        # Gather results as they complete
        for future in as_completed(future_to_task):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                task_idx = future_to_task[future]
                results.append({
                    "task_id": task_idx + 1,
                    "task": tasks[task_idx],
                    "status": "error",
                    "error": f"Unexpected error: {str(e)}",
                    "report": None
                })

    # Sort results by task_id for consistent ordering
    results.sort(key=lambda x: x["task_id"])

    # Store all results in main session
    results_record = {
        "type": "subagent_results",
        "timestamp": datetime.now().isoformat(),
        "num_agents": len(tasks),
        "results": results
    }
    main_session.append_store(results_record)

    # Output summary (JSON format for easy parsing)
    summary = {
        "status": "completed",
        "num_agents": len(tasks),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }

    print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
