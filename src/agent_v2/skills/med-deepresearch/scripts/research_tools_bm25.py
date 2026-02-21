#!/usr/bin/env python3
"""
Research tools for med-deepresearch skill.

This script provides tools that automatically update the agent's session.
The session_id is passed via AGENT_SESSION_ID environment variable.

Commands:
    plan     - Record research plan (queries to run, steps to take)
    query    - Execute a search query and record results
    navigate - Select a case to investigate further
    submit   - Submit final diagnosis answer

Usage:
    python research_tools.py plan --steps "1. Search for X" "2. Compare with Y"
    python research_tools.py query --name "chest pain CT findings"
    python research_tools.py navigate --case-id 1000
    python research_tools.py submit --answer A --reasoning "..."
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from agent_v2.session import Session

# Session directory (relative to project root)
DEFAULT_SESSION_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "sessions"


def get_session() -> Session:
    """Get the current agent's session from environment variable."""
    session_id = os.environ.get("AGENT_SESSION_ID")
    if not session_id:
        print("Error: AGENT_SESSION_ID not set. This script must be called by the agent.", file=sys.stderr)
        sys.exit(1)

    session_dir = os.environ.get("AGENT_SESSION_DIR", str(DEFAULT_SESSION_DIR))
    return Session(session_id=session_id, session_dir=Path(session_dir))


def cmd_plan(args):
    """Record a research plan."""
    session = get_session()

    plan_data = {
        "type": "plan",
        "steps": args.steps,
        "goal": args.goal or "Diagnose the clinical case"
    }

    session.append_store(plan_data)

    print(f"Research plan recorded with {len(args.steps)} steps:")
    for i, step in enumerate(args.steps, 1):
        print(f"  {i}. {step}")

    return 0


def cmd_query(args):
    """Execute a search query and record results."""
    session = get_session()

    # Run med_search.py
    search_script = Path(__file__).parent.parent.parent.parent.parent / "med_search.py"

    cmd = ["uv", "run", "python", str(search_script), args.name]
    if args.top_k:
        cmd.extend(["--top_k", str(args.top_k)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent.parent.parent.parent)
        )
        output = result.stdout
        error = result.stderr

        # Record the query in session
        query_data = {
            "type": "query",
            "query": args.name,
            "top_k": args.top_k or 5,
            "success": result.returncode == 0
        }
        session.append_store(query_data)

        if result.returncode == 0:
            print(output)
        else:
            print(f"Search error: {error or output}", file=sys.stderr)
            return 1

    except subprocess.TimeoutExpired:
        print("Error: Search timed out", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running search: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_navigate(args):
    """Select a case to investigate further."""
    session = get_session()

    # Run med_search.py with case ID
    search_script = Path(__file__).parent.parent.parent.parent.parent / "med_search.py"

    cmd = ["uv", "run", "python", str(search_script), str(args.case_id)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent.parent.parent.parent)
        )
        output = result.stdout

        # Record the navigation in session
        nav_data = {
            "type": "navigate",
            "case_id": args.case_id,
            "reason": args.reason or "Selected for investigation"
        }
        session.append_store(nav_data)

        if result.returncode == 0:
            print(output)
        else:
            print(f"Case {args.case_id} not found", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_submit(args):
    """Submit final diagnosis answer."""
    session = get_session()

    # Normalize answer
    answer = args.answer.upper()
    if answer not in ['A', 'B', 'C', 'D', 'E']:
        print(f"Error: Invalid answer '{answer}'. Must be A, B, C, D, or E.", file=sys.stderr)
        return 1

    # Record submission in session
    submit_data = {
        "type": "submit",
        "answer": answer,
        "reasoning": args.reasoning
    }
    session.append_store(submit_data)

    # Output FINAL_RESULT for agent termination
    result = {
        "answer": answer,
        "reasoning": args.reasoning,
        "timestamp": datetime.now().isoformat()
    }

    print("<<<FINAL_RESULT>>>")
    print(json.dumps(result, indent=2))
    print("<<<END_FINAL_RESULT>>>")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Research tools for medical diagnosis",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # plan command
    plan_parser = subparsers.add_parser("plan", help="Record research plan")
    plan_parser.add_argument(
        "--steps", "-s",
        nargs="+",
        required=True,
        help="List of research steps"
    )
    plan_parser.add_argument(
        "--goal", "-g",
        type=str,
        default=None,
        help="Goal of the research"
    )

    # query command
    query_parser = subparsers.add_parser("query", help="Search medical database")
    query_parser.add_argument(
        "--name", "-n",
        type=str,
        required=True,
        help="Search query"
    )
    query_parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=5,
        help="Number of results (default: 5)"
    )

    # navigate command
    nav_parser = subparsers.add_parser("navigate", help="Select a case to investigate")
    nav_parser.add_argument(
        "--case-id", "-c",
        type=int,
        required=True,
        help="Case number to investigate"
    )
    nav_parser.add_argument(
        "--reason", "-r",
        type=str,
        default=None,
        help="Reason for selecting this case"
    )

    # submit command
    submit_parser = subparsers.add_parser("submit", help="Submit final answer")
    submit_parser.add_argument(
        "--answer", "-a",
        type=str,
        required=True,
        choices=["A", "B", "C", "D", "E", "a", "b", "c", "d", "e"],
        help="Answer choice (A-E)"
    )
    submit_parser.add_argument(
        "--reasoning", "-r",
        type=str,
        required=True,
        help="Reasoning for the answer"
    )

    args = parser.parse_args()

    if args.command == "plan":
        return cmd_plan(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "navigate":
        return cmd_navigate(args)
    elif args.command == "submit":
        return cmd_submit(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
