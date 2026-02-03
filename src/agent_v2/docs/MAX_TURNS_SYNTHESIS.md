# Max Turns Synthesis Feature

## Overview

When an agent reaches `max_turns` without producing a final result, instead of returning "Reached maximum reasoning steps", the agent now makes **one final LLM call** to synthesize all findings into a coherent conclusion.

## Problem Solved

**Before:**
```
Turn 1: Query database
Turn 2: Navigate case
Turn 3: Query again
...
Turn 15: Max turns reached
Result: "Reached maximum reasoning steps."  ❌ Not helpful!
```

**After:**
```
Turn 1: Query database
Turn 2: Navigate case
Turn 3: Query again
...
Turn 15: Max turns reached
Turn 16 (Synthesis): Based on research, the findings suggest...  ✅ Useful!
```

## How It Works

### 1. Normal Execution

The agent runs normally, executing tools and reasoning through the problem.

### 2. Max Turns Detection

When `turn >= max_turns` and no final result has been produced:
- Old behavior: Return "Reached maximum reasoning steps"
- New behavior: Trigger synthesis

### 3. Synthesis Call

```python
# Add synthesis instruction
synthesis_prompt = (
    "You have reached the maximum number of reasoning steps. "
    "Based on all the research and analysis you've done so far, "
    "provide a final conclusion or answer. Synthesize your findings "
    "and provide the best response you can with the information gathered."
)

# One final LLM call (no tools, just synthesis)
response = client.chat.completions.create(
    model=model_id,
    messages=messages + [{"role": "user", "content": synthesis_prompt}],
    tools=None,  # No tools - force conclusion
    temperature=temperature
)
```

### 4. Result

The agent receives all previous conversation context and synthesizes a final answer based on what it learned.

## Benefits

### 1. No Wasted Work
Even if the agent runs out of turns, the research it did is not wasted - it gets synthesized into a useful conclusion.

### 2. Better Sub-Agent Reports
Sub-agents that hit max_turns now return structured reports instead of empty messages:

**Before:**
```json
{
  "task_id": 1,
  "report": "Reached maximum reasoning steps.",
  "status": "success"
}
```

**After:**
```json
{
  "task_id": 1,
  "report": "## Research Findings\n\nBased on my search of the medical database:\n- Found 5 relevant cases...\n- Pattern identified...\n- Conclusion: ...",
  "status": "success"
}
```

### 3. Graceful Degradation
When time/turns run out:
- Old: Hard failure with no output
- New: Partial success with best-effort synthesis

## Trajectory Logging

The synthesis turn is logged in the trajectory with special markers:

```json
{
  "run_id": "run_20260202_120000_abc123",
  "turns": [
    {"turn": 1, "content": "...", "tool_calls": [...]},
    {"turn": 2, "content": "...", "tool_calls": [...]},
    ...
    {"turn": 15, "content": "...", "tool_calls": [...]},
    {
      "turn": 16,
      "content": "Based on my research...",
      "tool_calls": [],
      "final": true,
      "synthesis": true  ← Marks this as synthesis turn
    }
  ],
  "termination_reason": "max_turns_synthesized",  ← New termination reason
  "total_turns": 16
}
```

## Termination Reasons

### New Reasons

- **`max_turns_synthesized`**: Max turns reached, synthesis successful
- **`max_turns_synthesis_failed`**: Max turns reached, synthesis failed (exception)

### Existing Reasons

- **`llm_complete`**: LLM returned response without tool calls (normal completion)
- **`final_result`**: Skill submitted FINAL_RESULT via bash protocol
- **`llm_error`**: Error calling LLM API

## Example Scenarios

### Scenario 1: Research Agent

```python
agent = Agent(
    skills=["med-deepresearch"],
    max_turns=7  # Limited turns
)

result = agent.run("Diagnose this case: 45yo male, chest pain, CT shows mediastinal mass")

# Agent workflow:
# Turn 1: Query "mediastinal mass chest pain"
# Turn 2: Navigate to case 1234
# Turn 3: Query "thymoma vs lymphoma"
# Turn 4: Navigate to case 5678
# Turn 5: Query more cases
# Turn 6: Navigate another case
# Turn 7: Max turns!
# Turn 8 (Synthesis): Based on cases reviewed, most likely diagnosis is thymoma because...
```

### Scenario 2: Sub-Agent Research

```python
# Main agent spawns sub-agents with low max_turns
subagents = spawn_subagents(
    "Research fever and rash cases",
    "Research neurological symptoms",
    "Research treatment outcomes"
)

# Each sub-agent has max_turns=7
# If they hit the limit, they synthesize findings:
# "Based on 3 cases examined, fever+rash commonly presents with..."
```

### Scenario 3: Exploration Task

```python
agent = Agent(max_turns=10)

result = agent.run("Explore the codebase and explain the architecture")

# Agent workflow:
# Turns 1-9: Uses bash to read files, grep for patterns, etc.
# Turn 10: Max turns reached
# Turn 11 (Synthesis): "Based on files examined, the architecture consists of..."
```

## Configuration

### Adjust Max Turns

```python
# High max_turns - more research time
agent = Agent(max_turns=20)

# Low max_turns - quick research + synthesis
agent = Agent(max_turns=5)

# Very low - mostly synthesis
agent = Agent(max_turns=2)
```

### Disable Synthesis (Not Recommended)

If you really want the old behavior, you would need to modify the code to skip synthesis. However, **this is not recommended** as synthesis provides much better user experience.

## Error Handling

If synthesis fails (e.g., API error), the agent falls back to a message:

```python
try:
    # Attempt synthesis
    final_response = synthesize(messages)
except Exception as e:
    # Fallback
    final_response = f"Reached maximum reasoning steps. Failed to synthesize: {str(e)}"
    trajectory["termination_reason"] = "max_turns_synthesis_failed"
```

## Testing

To test the synthesis behavior:

```python
from agent_v2 import Agent
from pathlib import Path

# Create agent with very low max_turns
agent = Agent(
    max_turns=2,  # Force synthesis
    session_dir=Path("src/agent_v2/sessions")
)

# Give it a multi-step task
result = agent.run("Research and explain quantum computing")

# Check result
print(result)
# Should contain synthesized explanation, not "Reached maximum reasoning steps"
```

## Implementation Details

### Code Location

File: `src/agent_v2/agent.py`

Method: `Agent.run()`

Lines: ~418-450

### Key Changes

1. **Detect max_turns without final result**
   ```python
   if turn >= self.max_turns and not final_response:
   ```

2. **Add synthesis instruction to messages**
   ```python
   messages.append({
       "role": "user",
       "content": synthesis_prompt
   })
   ```

3. **Make final LLM call without tools**
   ```python
   response = self.client.chat.completions.create(
       model=self.model_id,
       messages=messages,
       tools=None,  # Force conclusion, no more tool calls
       temperature=self.temperature
   )
   ```

4. **Record synthesis in trajectory**
   ```python
   trajectory["turns"].append({
       "turn": turn + 1,
       "synthesis": True,
       "final": True,
       ...
   })
   ```

## Best Practices

### 1. Set Appropriate Max Turns

- **Complex research**: `max_turns=15-20`
- **Quick tasks**: `max_turns=5-10`
- **Sub-agents**: `max_turns=7-10`

### 2. Design for Synthesis

When creating skills/prompts, remind agents that they might need to synthesize:

```markdown
If you run out of turns, you will be asked to synthesize your findings.
Keep track of what you've learned so you can provide a useful summary.
```

### 3. Monitor Termination Reasons

Track termination reasons in your logs to see how often synthesis occurs:

```python
from pathlib import Path
import json

logs = Path("src/agent_v2/logs").glob("*.json")
reasons = {}

for log_file in logs:
    data = json.load(open(log_file))
    reason = data.get("termination_reason", "unknown")
    reasons[reason] = reasons.get(reason, 0) + 1

print(reasons)
# {'llm_complete': 45, 'max_turns_synthesized': 12, 'final_result': 8}
```

## Comparison with FINAL_RESULT Protocol

### FINAL_RESULT Protocol
- Used by **skills** to explicitly submit final answers via bash
- Controlled by skill code
- Example: `research_tools.py submit --answer A`

### Max Turns Synthesis
- Used when **agent runs out of turns** without reaching final result
- Automatic safety net
- Example: Research incomplete, agent synthesizes what it found

Both mechanisms ensure the agent produces useful output rather than failing silently.

## Summary

The max turns synthesis feature ensures that:

1. **No wasted work**: Research/analysis is always synthesized
2. **Better UX**: Users get useful results even when time runs out
3. **Graceful degradation**: Partial results > no results
4. **Sub-agent reliability**: Sub-agents always return reports

This is especially important for parallel sub-agent research where some sub-agents might hit time limits while others complete successfully.
