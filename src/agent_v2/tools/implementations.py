"""Core tool implementations for agent_v2.

Provides fundamental tools:
- web_search: Search the internet
- bash: Execute shell commands (with session env vars)
- think: Record reasoning
"""
import os
import json
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

from .registry import tool

load_dotenv()

# Detect project root (4 levels up from this file: tools/ -> agent_v2/ -> src/ -> project/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@tool(name="web_search", description="Search the web for information. Use this to find current information, documentation, or answers to questions.")
def web_search(query: str, count: int = 10) -> str:
    """Search the web using Brave Search API.

    Args:
        query: The search query string
        count: Number of results to return (max 20, default 10)
    """
    try:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY not found in environment variables"

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        params = {"q": query, "count": min(count, 20)}

        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            results = []

            if "web" in data and "results" in data["web"]:
                for idx, result in enumerate(data["web"]["results"][:count], 1):
                    results.append(
                        f"{idx}. {result.get('title', 'No title')}\n"
                        f"   URL: {result.get('url', '')}\n"
                        f"   {result.get('description', 'No description')}"
                    )

            if results:
                return f"Search results for '{query}':\n\n" + "\n\n".join(results)
            return f"No results found for: {query}"
        else:
            return f"Error: Search API returned status {response.status_code}"

    except requests.Timeout:
        return "Error: Search request timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def bash_with_session(command: str, session_id: str = None, session_dir: str = None, timeout: int = 60) -> str:
    """Execute a bash command with session environment variables.

    Args:
        command: The bash command to execute
        session_id: Agent's session ID (passed as AGENT_SESSION_ID env var)
        session_dir: Session directory (passed as AGENT_SESSION_DIR env var)
        timeout: Maximum execution time in seconds (default 60)

    Returns:
        Command output or error message
    """
    try:
        # Build environment with session info
        env = os.environ.copy()
        if session_id:
            env["AGENT_SESSION_ID"] = session_id
        if session_dir:
            env["AGENT_SESSION_DIR"] = str(session_dir)

        # Always run commands from project root for consistency
        # This ensures skill scripts with paths like "src/..." work correctly
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, 300),
            executable='/bin/bash',
            cwd=str(PROJECT_ROOT),
            env=env
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode == 0:
            return output if output else "Command executed successfully (no output)"
        else:
            return f"Error (exit {result.returncode}): {error or output}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(name="bash", description="Execute a bash command. Use for file operations, running scripts, or system commands.")
def bash(command: str, timeout: int = 60) -> str:
    """Execute a bash command and return output.

    Args:
        command: The bash command to execute
        timeout: Maximum execution time in seconds (default 60)
    """
    # This is the basic bash without session - agent.py will use bash_with_session
    return bash_with_session(command, timeout=timeout)


@tool(name="think", description="Think through the problem step by step. Use this to plan your approach before taking actions.")
def think(thought: str) -> str:
    """Record a reasoning step.

    Args:
        thought: Your thought or reasoning step
    """
    return f"Thought recorded: {thought}"


# Session store - used internally, not exposed to LLM
def create_session_store_tool(session):
    """Create a session_store tool bound to a Session object.

    Note: This is kept for internal use but not exposed to the LLM.
    Skills use their own scripts that access the session via env vars.
    """
    def session_store(data: str) -> str:
        """Store data in the session."""
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                return "Error: data must be a JSON object"
            session.append_store(parsed)
            return f"Stored in session: {data}"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON - {str(e)}"

    return session_store
