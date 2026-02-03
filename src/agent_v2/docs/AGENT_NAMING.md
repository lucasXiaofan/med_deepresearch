# Agent Naming System

This document explains how sessions and logs are identified by agent name/type to distinguish between different types of agents.

## Overview

Every agent now has an `agent_name` that identifies its type or purpose. This name is stored in:
- Session files (JSON)
- Trajectory log files (JSON)
- Session listings

This allows you to easily distinguish between:
- Main agents with skills (e.g., "med-deepresearch")
- Sub-agents spawned for parallel research (e.g., "subagent-research-1")
- Generic agents (e.g., "main-agent")

## Agent Name Assignment

### Automatic Naming (Priority Order)

1. **Explicit agent_name parameter** (highest priority)
   ```python
   Agent(agent_name="custom-name")
   # → agent_name: "custom-name"
   ```

2. **Auto-detected from skills**
   ```python
   Agent(skills=["med-deepresearch"])
   # → agent_name: "med-deepresearch"

   Agent(skills=["skill1", "skill2"])
   # → agent_name: "skill1+skill2"
   ```

3. **Default fallback**
   ```python
   Agent()
   # → agent_name: "main-agent"
   ```

## Usage Examples

### Main Agent with Skill

```python
from agent_v2 import Agent

agent = Agent(
    skills=["med-deepresearch"],
    session_id="case_001"
)

print(agent.session.agent_name)
# Output: "med-deepresearch"
```

**Session file** (`session_case_001.json`):
```json
{
  "session_id": "case_001",
  "agent_name": "med-deepresearch",
  "store": [...],
  "history": [...]
}
```

**Log file** (`run_20260202_120000_abc123.json`):
```json
{
  "run_id": "run_20260202_120000_abc123",
  "session_id": "case_001",
  "agent_name": "med-deepresearch",
  "model": "deepseek-chat",
  "turns": [...]
}
```

### Sub-Agent (Spawned by Main Agent)

```python
from agent_v2 import Agent

subagent = Agent(
    session_id="case_001_sub1",
    agent_name="subagent-research-1",
    custom_system_prompt="You are a research sub-agent..."
)

print(subagent.session.agent_name)
# Output: "subagent-research-1"
```

**Session file** (`session_case_001_sub1.json`):
```json
{
  "session_id": "case_001_sub1",
  "agent_name": "subagent-research-1",
  "store": [...],
  "history": [...]
}
```

### Listing Sessions with Agent Names

```bash
# Command line
python -m agent_v2 --list-sessions
```

**Output:**
```
Sessions:
  session_case_001
    Agent: med-deepresearch
    Runs: 3, Store items: 15
    Updated: 2026-02-02T12:30:00

  session_case_001_sub1
    Agent: subagent-research-1
    Runs: 1, Store items: 8
    Updated: 2026-02-02T12:25:00

  session_case_001_sub2
    Agent: subagent-research-2
    Runs: 1, Store items: 6
    Updated: 2026-02-02T12:25:00
```

## File Structure

### Sessions Directory
```
src/agent_v2/sessions/
├── session_20260202_120000_abc123.json       # agent_name: "med-deepresearch"
├── session_20260202_120000_abc123_sub1.json  # agent_name: "subagent-research-1"
├── session_20260202_120000_abc123_sub2.json  # agent_name: "subagent-research-2"
└── session_20260202_130000_def456.json       # agent_name: "main-agent"
```

### Logs Directory
```
src/agent_v2/logs/
├── run_20260202_120100_aaa111.json  # agent_name: "med-deepresearch"
├── run_20260202_120130_bbb222.json  # agent_name: "subagent-research-1"
├── run_20260202_120135_ccc333.json  # agent_name: "subagent-research-2"
└── run_20260202_130100_ddd444.json  # agent_name: "main-agent"
```

## Benefits

### 1. Easy Identification
```python
# Find all sessions from main agent with med-deepresearch skill
sessions = list_sessions()
main_sessions = [s for s in sessions if s['agent_name'] == 'med-deepresearch']
```

### 2. Filtering Logs
```bash
# Find all sub-agent logs
grep -l '"agent_name": "subagent-research' src/agent_v2/logs/*.json

# Find main agent logs
grep -l '"agent_name": "med-deepresearch"' src/agent_v2/logs/*.json
```

### 3. Debugging Parallel Research
When debugging parallel sub-agent execution, you can easily identify which session/log belongs to which sub-agent:

```python
# Main agent spawns 3 sub-agents
sessions = list_sessions()

# Identify main agent session
main = [s for s in sessions if 'subagent' not in s['agent_name']]

# Identify sub-agent sessions
subs = [s for s in sessions if 'subagent-research' in s['agent_name']]
```

### 4. Session Organization
```python
from agent_v2.session import list_sessions
from pathlib import Path

sessions = list_sessions(Path('src/agent_v2/sessions'))

# Group by agent type
by_agent = {}
for s in sessions:
    agent_name = s['agent_name']
    if agent_name not in by_agent:
        by_agent[agent_name] = []
    by_agent[agent_name].append(s)

# Show summary
for agent_name, agent_sessions in by_agent.items():
    print(f"{agent_name}: {len(agent_sessions)} sessions")
```

**Output:**
```
med-deepresearch: 15 sessions
subagent-research-1: 8 sessions
subagent-research-2: 7 sessions
subagent-research-3: 6 sessions
main-agent: 3 sessions
```

## Implementation Details

### Session Class Changes

**Added Fields:**
- `agent_name: str` - Agent identifier

**Updated Methods:**
- `__init__(agent_name="agent")` - Added parameter
- `_load()` - Loads agent_name from JSON
- `save()` - Saves agent_name to JSON

### Agent Class Changes

**Added Parameter:**
- `agent_name: Optional[str] = None` - Explicit agent name

**Auto-Detection Logic:**
```python
if agent_name:                    # 1. Explicit (highest priority)
    final_agent_name = agent_name
elif self.skill_names:            # 2. Auto-detect from skills
    final_agent_name = "+".join(self.skill_names)
else:                             # 3. Default fallback
    final_agent_name = "main-agent"
```

**Trajectory Logging:**
- Added `"agent_name"` field to trajectory JSON

### spawn_subagents.py Changes

**Sub-agent Creation:**
```python
Agent(
    session_id=subagent_session_id,
    agent_name=f"subagent-research-{task_id}",  # Explicit naming
    custom_system_prompt=subagent_prompt
)
```

This ensures all sub-agents are clearly identifiable by their task number.

## Backward Compatibility

Old sessions without `agent_name` field:
- Will show `agent_name: "unknown"` in listings
- Will load without errors
- Will get `agent_name: "agent"` if re-saved

## Testing

Run the test suite:
```bash
# Test session agent_name
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from agent_v2.session import Session

s = Session(agent_name='test', session_dir=Path('src/agent_v2/sessions'))
s.save()
s2 = Session(session_id=s.session_id, session_dir=Path('src/agent_v2/sessions'))
assert s2.agent_name == 'test', 'Agent name not preserved!'
print('✓ Session agent_name works')
"

# Test agent auto-detection
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from agent_v2.agent import Agent

a1 = Agent(skills=['med-deepresearch'], session_dir=Path('src/agent_v2/sessions'))
assert a1.session.agent_name == 'med-deepresearch'

a2 = Agent(session_dir=Path('src/agent_v2/sessions'))
assert a2.session.agent_name == 'main-agent'

a3 = Agent(agent_name='custom', session_dir=Path('src/agent_v2/sessions'))
assert a3.session.agent_name == 'custom'

print('✓ Agent auto-detection works')
"
```

## Summary

The agent naming system provides:
- **Identification**: Easy to distinguish agent types
- **Organization**: Filter and group sessions/logs by agent
- **Debugging**: Track which agent produced which output
- **Transparency**: Clear understanding of multi-agent workflows

All sessions and logs now include `agent_name` for better traceability and organization.
