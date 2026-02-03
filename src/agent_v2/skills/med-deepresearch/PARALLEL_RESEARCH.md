# Parallel Sub-Agent Research System

This document explains the parallel sub-agent research capability in the med-deepresearch skill.

## Overview

The med-deepresearch skill now supports spawning up to 5 sub-agents in parallel to handle complex research tasks. This allows the main agent to delegate different research questions to specialized sub-agents that work simultaneously.

## Architecture

```
Main Agent (receives original problem)
    ├── Can use research_tools.py directly (plan, query, navigate)
    ├── Can spawn sub-agents via spawn_subagents.py
    └── Submits final result via research_tools.py submit

Sub-Agents (spawned by main agent)
    ├── Receive predefined system prompt (subagent_prompt.md)
    ├── Can use research_tools.py (query, navigate only)
    ├── Cannot spawn more sub-agents
    ├── Cannot use FINAL_RESULT protocol
    └── Return research reports to main agent
```

## Files

### 1. `SKILL.md` (Main Agent Skill)
- System prompt for the main agent
- Describes all available tools including sub-agent spawning
- Updated with parallel research workflow

### 2. `subagent_prompt.md` (Sub-Agent System Prompt)
- System prompt automatically loaded for sub-agents
- Instructs sub-agents on their role and constraints
- Provides research report template

### 3. `scripts/spawn_subagents.py` (Sub-Agent Spawner)
- Creates up to 5 sub-agents in parallel
- Each sub-agent runs in its own thread
- Gathers all reports and stores in main session

### 4. `scripts/research_tools.py` (Research Tools)
- Provides query, navigate, plan, and submit commands
- Used by both main agent and sub-agents
- Automatically tracks research in session

## Usage

### Main Agent Workflow

```bash
# 1. Main agent receives a complex medical case
# 2. Main agent decides to use parallel research

# 3. Spawn sub-agents with different tasks
uv run python src/agent_v2/skills/med-deepresearch/scripts/spawn_subagents.py \
    "Search for cases with fever and rash in children" \
    "Find cases with neurological symptoms" \
    "Research treatment outcomes for suspected measles"

# 4. Sub-agents run in parallel, each:
#    - Uses query to search medical database
#    - Uses navigate to examine specific cases
#    - Returns structured research report

# 5. Main agent receives all reports (stored in session)
# 6. Main agent synthesizes findings
# 7. Main agent submits final answer
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py submit \
    --answer C \
    --reasoning "Based on sub-agent reports..."
```

### Example spawn_subagents.py Output

```json
{
  "status": "completed",
  "num_agents": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "task_id": 1,
      "task": "Search for cases with fever and rash in children",
      "status": "success",
      "report": "## Research Question\n...\n## Findings\n...",
      "session_id": "main_session_sub1"
    },
    {
      "task_id": 2,
      "task": "Find cases with neurological symptoms",
      "status": "success",
      "report": "## Research Question\n...\n## Findings\n...",
      "session_id": "main_session_sub2"
    },
    {
      "task_id": 3,
      "task": "Research treatment outcomes",
      "status": "success",
      "report": "## Research Question\n...\n## Findings\n...",
      "session_id": "main_session_sub3"
    }
  ]
}
```

## Session Storage

All sub-agent activity is tracked in the main agent's session:

1. **Task Assignment Record**:
```json
{
  "type": "subagent_spawn",
  "timestamp": "2024-02-01T14:30:00",
  "num_agents": 3,
  "tasks": [...]
}
```

2. **Results Record**:
```json
{
  "type": "subagent_results",
  "timestamp": "2024-02-01T14:35:00",
  "num_agents": 3,
  "results": [...]
}
```

## Constraints

### Sub-Agent Limitations
- ❌ Cannot spawn more sub-agents (no recursion)
- ❌ Cannot use FINAL_RESULT protocol
- ❌ Cannot access main agent's full session
- ✅ Can use query and navigate tools
- ✅ Each gets own sub-session (isolated)
- ✅ Returns structured research report

### System Limits
- Maximum 5 sub-agents per spawn
- Each sub-agent limited to 12 reasoning turns
- All sub-agents share main agent's API key/model

## Benefits

1. **Speed**: Parallel execution instead of sequential research
2. **Specialization**: Each sub-agent focuses on one research question
3. **Scalability**: Handle complex cases with multiple angles
4. **Traceability**: All research tracked in session store
5. **Isolation**: Sub-agent failures don't crash main agent

## When to Use Parallel Research

✅ **Good Use Cases:**
- Complex differential diagnosis with 3+ hypotheses
- Need to search multiple symptom combinations
- Comparing different demographic groups
- Time-critical research with many variables

❌ **Bad Use Cases:**
- Simple, straightforward cases
- Single clear hypothesis
- Sequential research (where each step depends on previous)
- Very similar research tasks (better as single query)

## Example Scenario

**Case**: 45-year-old with chest pain, mediastinal mass on CT

**Single Agent Approach** (sequential):
1. Query "mediastinal mass chest pain"
2. Navigate to promising cases
3. Query "thymoma vs lymphoma"
4. Navigate more cases
5. Submit answer
*Total time: ~5 minutes*

**Parallel Agent Approach**:
1. Spawn 3 sub-agents:
   - "Research anterior mediastinal masses in adults"
   - "Compare thymoma vs lymphoma imaging features"
   - "Search for cases with similar demographics and presentation"
2. All 3 work simultaneously
3. Synthesize reports
4. Submit answer
*Total time: ~2 minutes*

## Technical Details

### Thread Safety
- Uses Python's `ThreadPoolExecutor` for parallel execution
- Each sub-agent gets own Agent instance
- Session file locking prevents conflicts (fcntl)
- Results gathered safely with `as_completed()`

### Error Handling
- Individual sub-agent failures don't crash the system
- Failed tasks return error status in results
- Main agent receives all results (success + errors)
- Partial success is acceptable

### Resource Management
- Sub-agents share same model/API as main agent
- Each sub-agent limited to 12 turns (prevents runaway)
- Thread pool auto-manages concurrency
- Sessions cleaned up after completion
