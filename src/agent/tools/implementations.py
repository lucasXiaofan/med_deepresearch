"""Tool implementations for the agent."""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from .registry import tool

# Load environment variables from .env file
load_dotenv()

# Memory directory for conversation logs
MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)


@tool(name="bash_command", description="Execute bash commands in a shell")
def bash_command(command: str) -> str:
    """Execute a bash command and return output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            executable='/bin/bash'
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode == 0:
            return output if output else "Command executed successfully (no output)"
        else:
            return f"Error (exit code {result.returncode}): {error or output}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(name="think", description="Think step by step about the plan to break down the task")
def think(thought: str) -> str:
    """Record a thought during reasoning. Use this to plan your approach."""
    return f"Thought recorded: {thought}"


@tool(name="brave_search", description="Search the web using Brave Search API")
def brave_search(query: str, count: int = 10) -> str:
    """Search the web for information using Brave Search API.

    Args:
        query: The search query string
        count: Number of results to return (max 20)

    Returns:
        Formatted search results or error message
    """
    try:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY not found in environment variables"

        # Brave Search API endpoint
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        params = {
            "q": query,
            "count": min(count, 20)  # Max 20 results
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = []

            # Extract web results
            if "web" in data and "results" in data["web"]:
                for idx, result in enumerate(data["web"]["results"][:count], 1):
                    results.append({
                        "position": idx,
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "description": result.get("description", "")
                    })

            if results:
                formatted_results = "\n\n".join([
                    f"{r['position']}. {r['title']}\n   URL: {r['url']}\n   {r['description']}"
                    for r in results
                ])
                return f"Search Results for '{query}':\n\n{formatted_results}"
            else:
                return f"No results found for query: {query}"
        else:
            return f"Error: Brave API returned status code {response.status_code}\n{response.text}"

    except requests.Timeout:
        return "Error: Search request timed out"
    except requests.RequestException as e:
        return f"Error: Network request failed - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool(name="final_answer", description="Submit your final answer choice for a multiple choice question. Use this when you are ready to provide your diagnosis.")
def final_answer(answer: str, reasoning: str) -> str:
    """Submit the final answer for a multiple choice diagnostic question.

    Args:
        answer: The answer choice letter (A, B, C, D, or E)
        reasoning: Brief explanation for why this answer was chosen

    Returns:
        Formatted answer response
    """
    # Normalize answer to uppercase single letter
    answer = answer.strip().upper()
    if len(answer) > 1:
        answer = answer[0]

    if answer not in ['A', 'B', 'C', 'D', 'E']:
        return f"Error: Invalid answer '{answer}'. Must be A, B, C, D, or E."

    return json.dumps({
        "answer": answer,
        "reasoning": reasoning
    })


@tool(name="final_result", description="Format and present the final report to the user. Use this when you have gathered enough information to provide a complete answer.")
def final_result(summary: str, details: str, sources: str = "") -> str:
    """Format the agent's final report to the user.

    Args:
        summary: A brief summary of the findings (1-2 sentences)
        details: Detailed explanation or answer
        sources: Optional sources or references used

    Returns:
        Formatted final report
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""
# FINAL REPORT
Generated: {timestamp}

## SUMMARY
{summary}

## DETAILS
{details}
"""

    if sources:
        report += f"""
## SOURCES
{sources}
"""

    return report


def save_conversation(user_query: str, final_response: str, image_path: str = None) -> None:
    """Save a conversation to the memory log.

    Args:
        user_query: The user's original query
        final_response: The agent's final response
        image_path: Optional path to image used in conversation
    """
    log_file = MEMORY_DIR / "conversation_log.json"

    # Load existing conversations
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            conversations = json.load(f)
    else:
        conversations = []

    # Add new conversation
    conversation = {
        "id": len(conversations) + 1,
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "image_path": image_path,
        "final_response": final_response
    }
    conversations.append(conversation)

    # Save back to file
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)


def load_recent_conversations(limit: int = 5) -> list[dict]:
    """Load the most recent conversations from memory.

    Args:
        limit: Maximum number of recent conversations to load

    Returns:
        List of recent conversation dictionaries
    """
    log_file = MEMORY_DIR / "conversation_log.json"

    if not log_file.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    # Return most recent conversations
    return conversations[-limit:] if conversations else []
