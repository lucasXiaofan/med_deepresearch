"""Main Agent class for agent_v2.

The Agent:
1. Manages conversation with an LLM
2. Executes tools when requested
3. Handles session context
4. Loads and applies skills
5. Records trajectories for debugging
6. Detects FINAL_RESULT markers from bash to terminate runs
7. Passes session info to bash via environment variables
8. Supports vision models with automatic image injection
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
from .config import load_config, get_model_config, resolve_image_csv_path, build_client_kwargs
from .image_loader import ImageLoader

load_dotenv()

# Module directory for default log/session storage
MODULE_DIR = Path(__file__).parent

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
        skills_dir: Optional[Path] = None, #need complete path not relative path
        model: Optional[str] = None,
        model_type: Optional[str] = None,
        config_path: Optional[Path] = None,
        temperature: float = 0.3,
        max_turns: int = 15,
        log_dir: Optional[Path] = None,
        custom_instructions: str = "",
        custom_system_prompt: Optional[str] = None,
        session_dir: Optional[Path] = None,
        agent_name: Optional[str] = None
    ):
        """Initialize the agent.

        Args:
            session_id: Session ID (auto-generated if None)
            skills: List of skill names to load
            skills_dir: Directory containing skill folders
            model: Model identifier (e.g., "openai/gpt-4o-mini"). Overrides config.
            model_type: "vision" or "text" (selects from agent_config.yaml)
            config_path: Path to agent_config.yaml (defaults to agent_v2/agent_config.yaml)
            temperature: LLM temperature (0-1)
            max_turns: Maximum tool-calling turns
            log_dir: Directory for trajectory logs (defaults to agent_v2/logs)
            custom_instructions: Additional instructions to augment system prompt
            custom_system_prompt: Custom system prompt to append after built prompt (augments, not replaces)
            session_dir: Directory for session storage (defaults to agent_v2/sessions)
            agent_name: Agent identifier (auto-detected from skills if None)
        """
        # Load config
        self.config = load_config(config_path)
        self.config_path = config_path

        # Skill setup first (to determine agent_name)
        self.skill_loader = SkillLoader(skills_dir or Path("./skills"))
        self.skill_names = skills or []
        self.loaded_skills: List[Skill] = []
        self._load_skills()

        # Determine agent name (explicit > skills > default)
        if agent_name:
            final_agent_name = agent_name
        elif self.skill_names:
            final_agent_name = "+".join(self.skill_names)  # e.g., "med-deepresearch" or "skill1+skill2"
        else:
            final_agent_name = "main-agent"

        # Session setup - defaults to agent_v2/sessions
        self.session_dir = session_dir or (MODULE_DIR / "sessions")
        self.session = Session(
            session_id=session_id,
            session_dir=self.session_dir,
            agent_name=final_agent_name
        )
        self.session_id = self.session.session_id

        # Model setup: explicit model > model_type from config > env > default
        if model:
            self.model = model
            self.supports_vision = False  # explicit model, unknown vision support
            self._setup_client()
        elif model_type:
            model_cfg = get_model_config(self.config, model_type)
            self.model = model_cfg["model_id"]
            self.supports_vision = model_cfg.get("supports_vision", False)
            self._setup_client_from_config(model_cfg)
        else:
            self.model = os.getenv("AGENT_MODEL", self.DEFAULT_MODEL)
            self.supports_vision = False
            self._setup_client()

        self.temperature = temperature
        self.max_turns = max_turns
        self.custom_instructions = custom_instructions
        self.custom_system_prompt = custom_system_prompt

        # Image loader (only for vision models)
        self.image_loader: Optional[ImageLoader] = None
        if self.supports_vision:
            self._setup_image_loader()

        # Logging setup - defaults to agent_v2/logs
        self.log_dir = log_dir or (MODULE_DIR / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Build prompts and tools
        self._build_system_prompt()
        self._build_tools()

    def _setup_client(self):
        """Setup the OpenAI client based on model name (legacy path)."""
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

    def _setup_client_from_config(self, model_cfg: Dict[str, Any]):
        """Setup the OpenAI client from config model entry."""
        kwargs = build_client_kwargs(model_cfg)
        self.client = OpenAI(**kwargs)
        self.model_id = model_cfg["model_id"]

    def _setup_image_loader(self):
        """Initialize the image loader from config."""
        try:
            csv_path = resolve_image_csv_path(self.config, self.config_path)
            self.image_loader = ImageLoader(csv_path)
            print(f"[Vision] Loaded {self.image_loader.total_images} images "
                  f"across {len(self.image_loader.case_ids)} cases")
        except FileNotFoundError as e:
            print(f"[Vision] Warning: {e}. Image injection disabled.")
            self.image_loader = None

    def _load_skills(self):
        """Load configured skills."""
        for skill_name in self.skill_names:
            skill = self.skill_loader.load_skill(skill_name)
            if skill:
                self.loaded_skills.append(skill)

    def _build_system_prompt(self):
        """Build the system prompt based on skills and session.

        If custom_system_prompt is provided, it augments (appends to) the built prompt.
        """
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

        # Augment with custom system prompt if provided
        if self.custom_system_prompt:
            self.system_prompt = f"{self.system_prompt}\n\n{self.custom_system_prompt}"

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

    def _extract_navigate_case_id(self, command: str) -> Optional[str]:
        """Extract case ID from a navigate bash command.

        Detects patterns like:
            research_tools.py navigate --case-id 1234
        """
        match = re.search(r'navigate\s+--case-id\s+(\d+)', command)
        return match.group(1) if match else None

    def _inject_case_images(self, case_id: str, messages: List[Dict]) -> bool:
        """Inject case images as a user message after tool results.

        For vision models, appends image content blocks.
        For text models, appends text descriptions.

        Returns True if images were injected.
        """
        if not self.image_loader or not self.image_loader.has_images(case_id):
            return False

        if self.supports_vision:
            img_blocks = self.image_loader.format_as_api_content(case_id)
            if img_blocks:
                header = {"type": "text", "text": f"--- Medical images for case {case_id} ---"}
                messages.append({
                    "role": "user",
                    "content": [header] + img_blocks
                })
                return True
        else:
            text_desc = self.image_loader.format_as_text(case_id)
            if text_desc:
                messages.append({
                    "role": "user",
                    "content": text_desc
                })
                return True

        return False

    def run(
        self,
        user_input: str,
        image: Optional[str] = None,
        case_id: Optional[str | int] = None,
        run_id: Optional[str] = None
    ) -> str:
        """Run the agent on a user input.

        The run loop terminates when:
        1. LLM returns a response without tool calls
        2. A bash tool returns a FINAL_RESULT marker
        3. Max turns is reached

        Args:
            user_input: The user's text input
            image: Optional path to a local image file
            case_id: Optional eurorad case ID to auto-load images (vision models)
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

        # Attach local image file if provided
        if image:
            image_url = self._encode_image(image)
            if image_url:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })

        # Auto-load case images for vision models
        if case_id and self.image_loader and self.supports_vision:
            img_blocks = self.image_loader.format_as_api_content(str(case_id))
            if img_blocks:
                user_content.append({"type": "text", "text": f"\n--- Medical images for case {case_id} ---"})
                user_content.extend(img_blocks)
        elif case_id and self.image_loader:
            # Text model: append image descriptions
            text_desc = self.image_loader.format_as_text(str(case_id))
            if text_desc:
                user_content.append({"type": "text", "text": f"\n{text_desc}"})

        messages.append({"role": "user", "content": user_content})

        # Trajectory tracking
        trajectory = {
            "run_id": run_id,
            "session_id": self.session_id,
            "agent_name": self.session.agent_name,
            "model": self.model,
            "supports_vision": self.supports_vision,
            "input": user_input,
            "image": image,
            "case_id": str(case_id) if case_id else None,
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
                        "result": result, # need full results
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

                # Inject images when agent navigates to a case (vision models)
                if self.image_loader:
                    for tc in (message.tool_calls or []):
                        if tc.function.name == "bash":
                            try:
                                tc_args = json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                continue
                            nav_case_id = self._extract_navigate_case_id(tc_args.get("command", ""))
                            if nav_case_id:
                                injected = self._inject_case_images(nav_case_id, messages)
                                if injected:
                                    turn_record.setdefault("images_injected", []).append(nav_case_id)

                # Add turn counter reminder to keep LLM aware of remaining turns
                turns_remaining = self.max_turns - turn
                if turns_remaining <= 3:
                    # Urgent warning when very low
                    turn_warning = f"\n[Turn {turn}/{self.max_turns} - Only {turns_remaining} turns left! Prioritize completing your task.]"
                elif turns_remaining <= 5:
                    # Moderate warning
                    turn_warning = f"\n[Turn {turn}/{self.max_turns} - {turns_remaining} turns remaining, work efficiently.]"
                else:
                    # Just a counter
                    turn_warning = f"\n[Turn {turn}/{self.max_turns}]"

                # Append turn info to last tool/user message
                if messages and messages[-1]["role"] == "tool":
                    messages[-1]["content"] += turn_warning
                elif messages and messages[-1]["role"] == "user":
                    # Images were injected as user message; append counter there
                    content = messages[-1]["content"]
                    if isinstance(content, str):
                        messages[-1]["content"] += turn_warning
                    elif isinstance(content, list):
                        content.append({"type": "text", "text": turn_warning})
            else:
                # No tool calls - LLM finished naturally
                final_response = message.content or ""
                turn_record["final"] = True
                trajectory["termination_reason"] = "llm_complete"
                trajectory["turns"].append(turn_record)
                break

        if turn >= self.max_turns and not final_response:
            # Max turns reached - make one final call to synthesize findings
            trajectory["termination_reason"] = "max_turns_synthesized"

            try:
                # Add instruction for final synthesis
                synthesis_prompt = (
                    "You have reached the maximum number of reasoning steps. "
                    "Based on all the research and analysis you've done so far, "
                    "provide a final conclusion or answer. Synthesize your findings "
                    "and provide the best response you can with the information gathered."
                )

                messages.append({
                    "role": "user",
                    "content": synthesis_prompt
                })

                # Final LLM call without tools - just get the synthesis
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    tools=self.tools if self.tools else None,
                    temperature=self.temperature
                )

                if response.usage:
                    trajectory["tokens"]["input"] += response.usage.prompt_tokens
                    trajectory["tokens"]["output"] += response.usage.completion_tokens

                final_response = response.choices[0].message.content or "Unable to synthesize findings."

                # Record the synthesis turn
                trajectory["turns"].append({
                    "turn": turn + 1,
                    "content": final_response,
                    "tool_calls": [],
                    "final": True,
                    "synthesis": True
                })

            except Exception as e:
                final_response = f"Reached maximum reasoning steps. Failed to synthesize: {str(e)}"
                trajectory["termination_reason"] = "max_turns_synthesis_failed"

        trajectory["finished_at"] = datetime.now().isoformat()
        trajectory["output"] = final_response
        trajectory["final_result_data"] = final_result_data
        trajectory["total_turns"] = turn

        # Store trajectory as instance variable for external access
        self.trajectory = trajectory

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
        agent_name = trajectory.get('agent_name', 'unknown')
        run_id = trajectory['run_id']
        log_file = self.log_dir / f"{agent_name}_{run_id}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False)


def create_agent(
    session_id: Optional[str] = None,
    skills: Optional[List[str]] = None,
    model: Optional[str] = None,
    model_type: Optional[str] = None,
    config_path: Optional[Path] = None,
    **kwargs
) -> Agent:
    """Factory function to create an agent.

    Args:
        session_id: Session ID.
        skills: Skill names to load.
        model: Explicit model ID (overrides config).
        model_type: "vision" or "text" (selects from config).
        config_path: Path to agent_config.yaml.
        **kwargs: Additional Agent constructor args.
    """
    return Agent(
        session_id=session_id,
        skills=skills,
        model=model,
        model_type=model_type,
        config_path=config_path,
        **kwargs
    )
