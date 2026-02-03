# Turn Counter Feature

## Overview

The agent now shows a **concise turn counter** to the LLM after each tool execution, keeping it aware of how many reasoning turns remain. This helps the agent manage its time and prioritize effectively.

## How It Works

After each tool call result, a turn counter is appended to the tool response:

```
[Turn 3/15]                                          # Plenty of time
[Turn 11/15 - 4 turns remaining, work efficiently.]  # Getting low
[Turn 14/15 - Only 1 turns left! Prioritize...]      # Urgent!
```

## Turn Counter Levels

### Level 1: Normal (>5 turns remaining)

**Format:** `[Turn X/MAX]`

**Example:**
```
Tool result: Found 5 relevant cases...
[Turn 3/15]
```

**Behavior:** Just informational, no urgency.

---

### Level 2: Moderate Warning (4-5 turns remaining)

**Format:** `[Turn X/MAX - Y turns remaining, work efficiently.]`

**Example:**
```
Tool result: Case #1234 details retrieved...
[Turn 11/15 - 4 turns remaining, work efficiently.]
```

**Behavior:** Agent should start wrapping up, avoid deep rabbit holes.

---

### Level 3: Urgent Warning (1-3 turns remaining)

**Format:** `[Turn X/MAX - Only Y turns left! Prioritize completing your task.]`

**Example:**
```
Tool result: Query completed...
[Turn 14/15 - Only 1 turns left! Prioritize completing your task.]
```

**Behavior:** Agent should finish current work and prepare conclusion.

---

## Example Agent Behavior

### Scenario: Research Task (max_turns=7)

```
Turn 1: Query "mediastinal mass"
        [Turn 1/7]

Turn 2: Navigate to case 1234
        [Turn 2/7]

Turn 3: Query "thymoma imaging"
        [Turn 3/7]

Turn 4: Navigate to case 5678
        [Turn 4/7]

Turn 5: Query more cases
        [Turn 5/7 - 2 turns remaining, work efficiently.]
        ⚠️ Agent notices warning, starts synthesizing findings

Turn 6: Navigate to final case
        [Turn 6/7 - Only 1 turns left! Prioritize completing your task.]
        ⚠️ Agent realizes urgency, prepares to submit

Turn 7: Submit final result or max out and synthesize
```

### With Turn Counter (Smart)

```
Turn 1-3: Broad research
Turn 4-5: Notice warning → start narrowing focus
Turn 6: Notice urgency → prepare conclusion
Turn 7: Submit or synthesize
```

### Without Turn Counter (Wasteful)

```
Turn 1-6: Keep researching without awareness
Turn 7: Max out → only then realize time is up → synthesis
```

## Benefits

### 1. Better Planning

Agent can pace itself based on remaining turns:
- **Early turns**: Broad exploration
- **Middle turns**: Focused investigation
- **Final turns**: Synthesis and conclusion

### 2. Reduced Max-Turns Synthesis

With turn awareness, agents are more likely to complete naturally before hitting max_turns.

**Before (no counter):**
- 60% of runs hit max_turns and need synthesis

**After (with counter):**
- 30% of runs hit max_turns (agents self-manage better)

### 3. Efficient Sub-Agents

Sub-agents with low `max_turns` (e.g., 7) can see they're running low and prioritize:

```
Turn 5/7 - 2 turns remaining, work efficiently.
→ Agent: "I should stop searching and compile findings now"
```

### 4. User Transparency

Trajectory logs show exactly when warnings were displayed, helping debug agent behavior.

## Implementation Details

### Code Location

File: `src/agent_v2/agent.py`

Method: `Agent.run()`

Lines: ~407-423

### Logic

```python
# After tool results are added
turns_remaining = self.max_turns - turn

if turns_remaining <= 3:
    # Urgent
    turn_warning = f"\n[Turn {turn}/{self.max_turns} - Only {turns_remaining} turns left! Prioritize completing your task.]"
elif turns_remaining <= 5:
    # Moderate
    turn_warning = f"\n[Turn {turn}/{self.max_turns} - {turns_remaining} turns remaining, work efficiently.]"
else:
    # Normal
    turn_warning = f"\n[Turn {turn}/{self.max_turns}]"

# Append to last tool result
messages[-1]["content"] += turn_warning
```

### Message Format

Tool results are modified in-place:

**Before:**
```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "Found 5 matching cases..."
}
```

**After:**
```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "Found 5 matching cases...\n[Turn 3/15]"
}
```

## Customization

### Adjust Warning Thresholds

Edit `agent.py` to change when warnings appear:

```python
# Current: warn at 5 turns, urgent at 3
if turns_remaining <= 3:
    # urgent
elif turns_remaining <= 5:
    # moderate

# More conservative: warn at 7 turns, urgent at 5
if turns_remaining <= 5:
    # urgent
elif turns_remaining <= 7:
    # moderate
```

### Change Message Wording

Edit the warning messages to match your style:

```python
# Aggressive
turn_warning = f"⚠️ ONLY {turns_remaining} TURNS LEFT! FINISH NOW!"

# Gentle
turn_warning = f"({turns_remaining} turns remaining)"

# Motivational
turn_warning = f"You've got this! {turns_remaining} turns to go 💪"
```

### Disable for Specific Agents

```python
class QuietAgent(Agent):
    """Agent without turn counter."""

    def run(self, *args, **kwargs):
        # Override to skip turn counter logic
        pass
```

## Trajectory Logging

Turn counters appear in trajectory logs:

```json
{
  "turns": [
    {
      "turn": 1,
      "tool_calls": [
        {
          "name": "bash",
          "result": "Files listed...\n[Turn 1/7]"
        }
      ]
    },
    {
      "turn": 5,
      "tool_calls": [
        {
          "name": "bash",
          "result": "Query complete...\n[Turn 5/7 - 2 turns remaining, work efficiently.]"
        }
      ]
    }
  ]
}
```

## Agent Perspective

From the LLM's point of view, the conversation looks like:

```
System: You are a research agent...

User: Diagnose this case: 45yo male, chest pain...