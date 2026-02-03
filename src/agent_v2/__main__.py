"""CLI entry point for agent_v2.

Usage:
    # Single query
    python -m agent_v2 "Your question here"

    # Interactive mode (listen for input)
    python -m agent_v2 --interactive --session my_session --model openai/gpt-4o

    # With skills
    python -m agent_v2 --skills explain-code "Explain this code"
"""
import argparse
import sys
from pathlib import Path

from .agent import Agent


def run_interactive(agent: Agent, verbose: bool = False):
    """Run agent in interactive mode, listening for input."""
    print(f"Agent ready. Session: {agent.session_id}")
    print(f"Model: {agent.model}")
    if agent.loaded_skills:
        print(f"Skills: {', '.join(s.name for s in agent.loaded_skills)}")
    print("-" * 40)
    print("Type your input (or 'quit'/'exit' to stop, 'session' to show session info)")
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.lower() == "session":
            print(f"Session ID: {agent.session_id}")
            print(f"Store items: {len(agent.session.store)}")
            print(f"Runs: {len(agent.session.history)}")
            if agent.session.store:
                print("Recent stored data:")
                for item in agent.session.store[-3:]:
                    print(f"  [{item['timestamp']}] {item['data']}")
            continue

        # Check for image attachment: "image:path/to/file.png your question"
        image = None
        if user_input.startswith("image:"):
            parts = user_input.split(" ", 1)
            if len(parts) >= 2:
                image = parts[0].replace("image:", "")
                user_input = parts[1]
            else:
                print("Usage: image:/path/to/file.png Your question here")
                continue

        print()  # Blank line before response
        result = agent.run(user_input, image=image)
        print(result)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="agent_v2 - Skill-based agent with session support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single query
  python -m agent_v2 "What is the capital of France?"

  # Interactive mode
  python -m agent_v2 --interactive
  python -m agent_v2 -I --session patient_001 --model openai/gpt-4o

  # With skills
  python -m agent_v2 --skills explain-code "Explain this"

  # Multiple skills
  python -m agent_v2 --skills explain-code --skills review-code -I

  # With image (single query)
  python -m agent_v2 --image ./screenshot.png "What's in this?"

  # List sessions/skills
  python -m agent_v2 --list-sessions
  python -m agent_v2 --list-skills
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="User input (not needed in interactive mode)"
    )

    parser.add_argument(
        "--interactive", "-I",
        action="store_true",
        help="Run in interactive mode, listening for input"
    )

    parser.add_argument(
        "--session", "-s",
        type=str,
        default=None,
        help="Session ID for persistence"
    )

    parser.add_argument(
        "--skills",
        type=str,
        action="append",
        default=[],
        help="Skill(s) to load (can repeat)"
    )

    parser.add_argument(
        "--skills-dir",
        type=str,
        default="./skills",
        help="Skills directory (default: ./skills)"
    )

    parser.add_argument(
        "--image", "-i",
        type=str,
        default=None,
        help="Path to image file"
    )

    parser.add_argument(
        "--model", "-m",
        type=str,
        default="deepseek-chat",
        help="Model to use (default: openai/gpt-4o-mini)"
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        default=15,
        help="Max reasoning turns (default: 15)"
    )

    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.3,
        help="LLM temperature (default: 0.3)"
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default="./logs",
        help="Logs directory (default: ./logs)"
    )

    parser.add_argument(
        "--session-dir",
        type=str,
        default="./sessions",
        help="Sessions directory (default: ./sessions)"
    )

    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List sessions and exit"
    )

    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List skills and exit"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show extra info"
    )

    args = parser.parse_args()

    # Handle list commands
    if args.list_sessions:
        from .session import list_sessions
        sessions = list_sessions(Path(args.session_dir))
        if not sessions:
            print("No sessions found.")
        else:
            print("Sessions:")
            for s in sessions:
                print(f"  {s['session_id']}")
                print(f"    Agent: {s.get('agent_name', 'unknown')}")
                print(f"    Runs: {s['runs']}, Store items: {s['store_items']}")
                print(f"    Updated: {s['updated_at']}")
        return

    if args.list_skills:
        from .skill_loader import SkillLoader
        loader = SkillLoader(Path(args.skills_dir))
        skills = loader.discover_skills()
        if not skills:
            print(f"No skills found in {args.skills_dir}")
        else:
            print("Skills:")
            for name in skills:
                skill = loader.load_skill(name)
                if skill:
                    print(f"  /{skill.name}: {skill.description}")
        return

    # Need input or interactive mode
    if not args.input and not args.interactive:
        parser.print_help()
        sys.exit(1)

    # Create agent
    agent = Agent(
        session_id=args.session,
        skills=args.skills if args.skills else None,
        skills_dir=Path(args.skills_dir),
        model=args.model,
        temperature=args.temperature,
        max_turns=args.max_turns,
        log_dir=Path(args.log_dir),
        session_dir=Path(args.session_dir)
    )

    # Interactive mode
    if args.interactive:
        run_interactive(agent, verbose=args.verbose)
        return

    # Single query mode
    if args.verbose:
        print(f"Session: {agent.session_id}")
        print(f"Model: {agent.model}")
        print("-" * 40)

    result = agent.run(args.input, image=args.image)
    print(result)

    if args.verbose:
        print("-" * 40)
        print(f"Session: {agent.session_id}")


if __name__ == "__main__":
    main()
