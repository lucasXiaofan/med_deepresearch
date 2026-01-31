"""Prompt templates for agent_v2.

Prompts are built in layers:
1. Base prompt: Always present, describes core capabilities
2. Skill prompt: Added based on skill configuration
3. Session prompt: Added when agent has session context
"""

BASE_SYSTEM_PROMPT = """You are an AI assistant with access to tools that help you accomplish tasks.

## Core Capabilities

You have access to these fundamental tools:

1. **web_search**: Search the internet for current information
   - Use for: facts, documentation, tutorials, news, research
   - Returns: search results with titles, URLs, and descriptions

2. **bash**: Execute shell commands
   - Use for: file operations, running scripts, system commands
   - Returns: command output or error messages
   - Be careful with destructive operations

3. **think**: Record your reasoning process
   - Use for: planning, breaking down problems, documenting your thought process
   - Helps maintain clear reasoning chains

## Guidelines

- **Be thorough**: Research before concluding, verify information when possible
- **Be efficient**: Don't repeat actions unnecessarily
- **Be clear**: Explain your reasoning and cite sources when relevant
- **Be safe**: Avoid destructive operations, ask for confirmation when uncertain

## Response Format

Always provide a clear, helpful response. When completing a task:
1. Summarize what you found or accomplished
2. Provide relevant details
3. Note any limitations or uncertainties
"""


SKILL_ROUTING_TOOLS_DESC = """
## Skill Management Tools

You also have access to:

4. **get_skill**: Load detailed instructions for a skill
   - Use when you need to apply a specific skill
   - Returns the full skill content with instructions

5. **get_skill_reference**: Load reference material from a skill
   - Use for additional context or examples
   - Specify skill name and reference file name
"""


def build_system_prompt(
    skill_prompt: str = "",
    session_prompt: str = "",
    has_skill_routing: bool = False,
    custom_instructions: str = ""
) -> str:
    """Build the complete system prompt.

    Args:
        skill_prompt: Skill-specific content (single skill or routing info)
        session_prompt: Session context information
        has_skill_routing: Whether skill routing tools are available
        custom_instructions: Additional custom instructions

    Returns:
        Complete system prompt string
    """
    parts = [BASE_SYSTEM_PROMPT]

    if has_skill_routing:
        parts.append(SKILL_ROUTING_TOOLS_DESC)

    if skill_prompt:
        parts.append(skill_prompt)

    if custom_instructions:
        parts.append(f"## Additional Instructions\n\n{custom_instructions}")

    if session_prompt:
        parts.append(session_prompt)

    return "\n\n".join(parts)


# Tool schema for skill routing (added dynamically when multiple skills)
SKILL_ROUTING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_skill",
            "description": "Load full instructions for a skill. Use this when you need to apply a specific skill to the task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to load (e.g., 'explain-code')"
                    }
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill_reference",
            "description": "Load additional reference material from a skill's reference folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill"
                    },
                    "ref_name": {
                        "type": "string",
                        "description": "Name of the reference file (e.g., 'reference.md')"
                    }
                },
                "required": ["skill_name", "ref_name"]
            }
        }
    }
]
