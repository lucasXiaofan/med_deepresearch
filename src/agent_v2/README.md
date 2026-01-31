# agent_v2 - Skill-Based Agent Framework

A flexible agent framework with session management and skill-based capabilities.

## Quick Start

```bash
# Set up environment variables
export OPENROUTER_API_KEY="your-key"
export BRAVE_API_KEY="your-key"  # For web search

# Single query
python -m agent_v2 "What is the capital of France?"

# Interactive mode (recommended)
python -m agent_v2 --interactive
python -m agent_v2 -I --session patient_001 --model openai/gpt-4o

# With skills
python -m agent_v2 --skills explain-code -I
```

## Concepts

### Sessions

A session persists across multiple agent runs - like a patient visit where multiple interactions happen.

```bash
# Start interactive session
python -m agent_v2 -I --session patient_001

# Agent remembers context across runs
> Patient reports headache for 3 days
> What symptoms were reported earlier?  # Agent knows!
```

**Session Store**: The agent can save notes using `session_store` tool:
- Simple append-only: agent stores JSON dicts that persist
- Data visible in subsequent runs
- File-locked for parallel safety

### Skills

Skills are specialized instruction modules loaded into the agent.

**No skills**: Agent only has basic tools (web_search, bash, session_store)
**Single skill**: Full SKILL.md content in system prompt
**Multiple skills**: Routing prompt; agent loads skills on demand

**Skill Structure:**
```
skills/
├── explain-code/
│   ├── SKILL.md           # Required: instructions
│   └── reference/
│       └── patterns.md    # Optional: extra context
```

**SKILL.md Format:**
```markdown
---
name: explain-code
description: Explains code with analogies. Use when user asks "how does this work?"
---

# Instructions here...
```

### Tools

Every agent has:
- **web_search** - Search the internet
- **bash** - Execute shell commands
- **session_store** - Store data in session (append-only JSON dicts)
- **think** - Record reasoning steps

With multiple skills, also:
- **get_skill** - Load a skill's instructions
- **get_skill_reference** - Load reference material

## CLI Reference

```bash
# Single query
python -m agent_v2 "Your question"

# Interactive mode
python -m agent_v2 --interactive
python -m agent_v2 -I

# Options
--session, -s     Session ID (auto-generated if not set)
--skills          Skill to load (repeatable: --skills a --skills b)
--skills-dir      Skills directory (default: ./skills)
--image, -i       Image file path
--model, -m       Model (default: openai/gpt-4o-mini)
--max-turns       Max reasoning turns (default: 15)
--temperature,-t  Temperature (default: 0.3)
--log-dir         Logs directory (default: ./logs)
--session-dir     Sessions directory (default: ./sessions)
--verbose, -v     Show extra info

# List commands
--list-sessions   List all sessions
--list-skills     List available skills
```

### Interactive Mode Commands

When running with `-I`:
- Type your query and press Enter
- `session` - Show session info and stored data
- `image:/path/to/file.png Your question` - Include an image
- `quit` or `exit` - Exit

## Python API

```python
from agent_v2 import Agent

# Basic
agent = Agent()
result = agent.run("Search for Python 3.12 features")

# Full config
agent = Agent(
    session_id="task_123",
    skills=["explain-code"],
    model="openai/gpt-4o",
    temperature=0.5,
    max_turns=20
)

# With image
result = agent.run("What's in this?", image="./screenshot.png")

# Access session
print(agent.session_id)
print(agent.session.store)  # List of stored dicts
```

## Creating Skills

1. Create folder:
```bash
mkdir -p skills/my-skill/reference
```

2. Create `skills/my-skill/SKILL.md`:
```markdown
---
name: my-skill
description: Does X. Use when user asks about Y.
---

# Instructions

Your detailed instructions here.
```

3. Use it:
```bash
python -m agent_v2 --skills my-skill -I
```

## Logs

Every run saves a trajectory in `./logs/`:
```json
{
  "run_id": "run_20240115_143022_abc123",
  "session_id": "session_...",
  "model": "openai/gpt-4o-mini",
  "input": "User question",
  "turns": [
    {"turn": 1, "content": "...", "tool_calls": [...]}
  ],
  "output": "Final response"
}
```

## Environment Variables

```bash
OPENROUTER_API_KEY=your-key      # Required (default provider)
BRAVE_API_KEY=your-key           # Required for web_search
DEEPSEEK_API_KEY=your-key        # Optional: use deepseek models
AGENT_MODEL=openai/gpt-4o        # Optional: override default model
```

## Project Structure

```
agent_v2/
├── __init__.py       # Exports
├── __main__.py       # CLI with interactive mode
├── agent.py          # Agent class
├── session.py        # Session (file-locked, parallel-safe)
├── skill_loader.py   # Skill loading/routing
├── prompts.py        # Prompt templates
├── tools/
│   ├── registry.py   # Tool registration
│   └── implementations.py  # web_search, bash, session_store
└── skills/           # Your skills go here
```
