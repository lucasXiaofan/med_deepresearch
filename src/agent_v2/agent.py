"""Main Agent class for agent_v2.

The Agent:
1. Manages conversation with an LLM
2. Executes tools when requested
3. Handles session context
4. Loads and applies skills
5. Records trajectories for debugging
6. Detects FINAL_RESULT markers from bash to terminate runs
7. Passes session info to bash via environment variables
"""
import os
import re
import json
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from openai import OpenAI
from dotenv import load_dotenv

from .session import Session
from .skill_loader import SkillLoader, Skill, generate_skill_routing_prompt, generate_single_skill_prompt
from .prompts import build_system_prompt, SKILL_ROUTING_TOOLS
from .tools import get_tool_schemas, execute_tool, bash_with_session

load_dotenv()


# Final Result Protocol markers
FINAL_RESULT_START = "<<<FINAL_RESULT>>>"
FINAL_RESULT_END = "<<<END_FINAL_RESULT>>>"


def parse_final_result(output: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if output contains a FINAL_RESULT marker.

    The Final Result Protocol allows skills to signal run termination
    with structured output. Format:

        <<<FINAL_RESULT>>>
        {"key": "value", ...}
        <<<END_FINAL_RESULT>>>

    Args:
        output: String output from a tool (typically bash)

    Returns:
        Tuple of (is_final, parsed_result_dict or None)
    """
    pattern = r'<<<FINAL_RESULT>>>\s*(.*?)\s*<<<END_FINAL_RESULT>>>'
    match = re.search(pattern, output, re.DOTALL)

    if match:
        try:
            result = json.loads(match.group(1))
            return True, result
        except json.JSONDecodeError:
            return True, {"raw": match.group(1).strip()}

    return False, None


class Agent:
    """Skill-based agent with session support and final result detection.

    The agent has access to:
    - web_search: Search the internet
    - bash: Execute shell commands (with session env vars for skill scripts)
    - think: Record reasoning steps

    Session management is handled automatically via environment variables
    passed to bash commands. Skills can access session via AGENT_SESSION_ID.
    """

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        session_id: Optional[str] = None,
        skills: Optional[List[str]] = None,
        skills_dir: Optional[Path] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_turns: int = 15,
        log_dir: Optional[Path] = None,
        custom_instructions: str = "",
        session_dir: Optional[Path] = None
    ):
        """Initialize the agent.

        Args:
            session_id: Session ID (auto-generated if None)
            skills: List of skill names to load
            skills_dir: Directory containing skill folders
            model: Model identifier (e.g., "openai/gpt-4o-mini")
            temperature: LLM temperature (0-1)
            max_turns: Maximum tool-calling turns
            log_dir: Directory for trajectory logs
            custom_instructions: Additional system prompt instructions
            session_dir: Directory for session storage
        """
        # Session setup
        self.session_dir = session_dir or Path("./sessions")
        self.session = Session(
            session_id=session_id,
            session_dir=self.session_dir
        )
        self.session_id = self.session.session_id

        # Skill setup
        self.skill_loader = SkillLoader(skills_dir or Path("./skills"))
        self.skill_names = skills or []
        self.loaded_skills: List[Skill] = []
        self._load_skills()

        # Model setup
        self.model = model or os.getenv("AGENT_MODEL", self.DEFAULT_MODEL)
        self.temperature = temperature
        self.max_turns = max_turns
        self.custom_instructions = custom_instructions

        # Client setup
        self._setup_client()

        # Logging setup
        self.log_dir = log_dir or Path("./logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Build prompts and tools
        self._build_system_prompt()
        self._build_tools()

    def _setup_client(self):
        """Setup the OpenAI client based on model."""
        if self.model.startswith("deepseek"):
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            self.model_id = self.model.replace("deepseek/", "")
        else:
            self.client = OpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url=self.DEFAULT_BASE_URL
            )
            self.model_id = self.model

    def _load_skills(self):
        """Load configured skills."""
        for skill_name in self.skill_names:
            skill = self.skill_loader.load_skill(skill_name)
            if skill:
                self.loaded_skills.append(skill)

    def _build_system_prompt(self):
        """Build the system prompt based on skills and session."""
        skill_prompt = ""
        self.has_skill_routing = False

        if len(self.loaded_skills) == 1:
            skill_prompt = generate_single_skill_prompt(self.loaded_skills[0])
        elif len(self.loaded_skills) > 1:
            skill_prompt = generate_skill_routing_prompt(self.loaded_skills)
            self.has_skill_routing = True

        session_prompt = self.session.get_context_prompt()

        self.system_prompt = build_system_prompt(
            skill_prompt=skill_prompt,
            session_prompt=session_prompt,
            has_skill_routing=self.has_skill_routing,
            custom_instructions=self.custom_instructions
        )

    def _build_tools(self):
        """Build tool schemas for this agent.

        Note: session_store is NOT exposed to the LLM.
        Skills manage session via their own scripts using AGENT_SESSION_ID env var.
        """
        # Core tools visible to LLM: web_search, bash, think
        # self.tools = get_tool_schemas(["web_search", "bash", "think"])
        self.tools = get_tool_schemas(["bash"])

        # Skill routing tools (only if multiple skills)
        if self.has_skill_routing:
            self.tools.extend(SKILL_ROUTING_TOOLS)

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode a local image to base64 data URL."""
        path = Path(image_path)
        if not path.exists():
            return None

        suffix = path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        mime_type = mime_types.get(suffix, "image/png")

        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime_type};base64,{encoded}"

    def _execute_tool(self, name: str, args: dict) -> Tuple[str, bool, Optional[Dict]]:
        """Execute a tool call.

        For bash commands, passes session info via environment variables
        so skill scripts can access and update the session.

        Returns:
            Tuple of (result_string, is_final, final_result_dict)
        """
        if name == "get_skill":
            return self.skill_loader.get_skill_content(args.get("skill_name", "")), False, None

        if name == "get_skill_reference":
            result = self.skill_loader.get_reference(
                args.get("skill_name", ""),
                args.get("ref_name", "")
            )
            return result, False, None

        # For bash, use bash_with_session to pass session env vars
        if name == "bash":
            command = args.get("command", "")
            timeout = args.get("timeout", 60)

            result = bash_with_session(
                command=command,
                session_id=self.session_id,
                session_dir=str(self.session_dir),
                timeout=timeout
            )

            # Check for FINAL_RESULT marker
            is_final, final_data = parse_final_result(result)
            if is_final:
                # Reload session to get any updates from the script
                self.session._load()
                return result, True, final_data

            # Reload session in case script updated it
            self.session._load()
            return result, False, None

        # Other tools (web_search, think)
        result = execute_tool(name, args)
        return result, False, None

    def run(
        self,
        user_input: str,
        image: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> str:
        """Run the agent on a user input.

        The run loop terminates when:
        1. LLM returns a response without tool calls
        2. A bash tool returns a FINAL_RESULT marker
        3. Max turns is reached

        Args:
            user_input: The user's text input
            image: Optional path to an image file
            run_id: Optional run identifier (auto-generated if None)

        Returns:
            The agent's final response string (or FINAL_RESULT JSON)
        """
        run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Rebuild prompt to include latest session context
        self._build_system_prompt()

        messages = [{"role": "system", "content": self.system_prompt}]

        # Build user message
        user_content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]

        if image:
            image_url = self._encode_image(image)
            if image_url:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })

        messages.append({"role": "user", "content": user_content})

        # Trajectory tracking
        trajectory = {
            "run_id": run_id,
            "session_id": self.session_id,
            "model": self.model,
            "input": user_input,
            "image": image,
            "turns": [],
            "tokens": {"input": 0, "output": 0},
            "started_at": datetime.now().isoformat(),
            "termination_reason": None
        }

        turn = 0
        final_response = ""
        final_result_data = None

        while turn < self.max_turns:
            turn += 1

            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    tools=self.tools if self.tools else None,
                    temperature=self.temperature
                )
            except Exception as e:
                final_response = f"Error calling LLM: {str(e)}"
                trajectory["termination_reason"] = "llm_error"
                break

            if response.usage:
                trajectory["tokens"]["input"] += response.usage.prompt_tokens
                trajectory["tokens"]["output"] += response.usage.completion_tokens

            choice = response.choices[0]
            message = choice.message

            turn_record = {
                "turn": turn,
                "content": message.content,
                "tool_calls": []
            }

            if message.tool_calls:
                messages.append(message)

                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    result, is_final, final_data = self._execute_tool(name, args)

                    turn_record["tool_calls"].append({
                        "name": name,
                        "args": args,
                        "result": result[:2000] if len(result) > 2000 else result,
                        "is_final": is_final
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })

                    # Check for FINAL_RESULT termination
                    if is_final:
                        final_result_data = final_data
                        final_response = json.dumps(final_data) if final_data else result
                        trajectory["termination_reason"] = "final_result"
                        turn_record["final"] = True
                        trajectory["turns"].append(turn_record)
                        break

                trajectory["turns"].append(turn_record)

                # Exit outer loop if we got a final result
                if final_result_data is not None:
                    break
            else:
                # No tool calls - LLM finished naturally
                final_response = message.content or ""
                turn_record["final"] = True
                trajectory["termination_reason"] = "llm_complete"
                trajectory["turns"].append(turn_record)
                break

        if turn >= self.max_turns and not final_response:
            final_response = "Reached maximum reasoning steps."
            trajectory["termination_reason"] = "max_turns"
            if messages and hasattr(messages[-1], 'content'):
                final_response = messages[-1].content or final_response

        trajectory["finished_at"] = datetime.now().isoformat()
        trajectory["output"] = final_response
        trajectory["final_result_data"] = final_result_data
        trajectory["total_turns"] = turn

        self._save_trajectory(trajectory)

        # Reload session to capture any updates from scripts
        self.session._load()

        self.session.add_run({
            "run_id": run_id,
            "input": user_input,
            "output_summary": final_response[:500],
            "output": final_response,
            "final_result_data": final_result_data,
            "turns": turn,
            "tokens": trajectory["tokens"]
        })

        return final_response

    def _save_trajectory(self, trajectory: dict):
        """Save trajectory to log file."""
        log_file = self.log_dir / f"{trajectory['run_id']}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False)


def create_agent(
    session_id: Optional[str] = None,
    skills: Optional[List[str]] = None,
    model: Optional[str] = None,
    **kwargs
) -> Agent:
    """Factory function to create an agent."""
    return Agent(
        session_id=session_id,
        skills=skills,
        model=model,
        **kwargs
    )
