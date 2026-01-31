# Final Result Protocol

## Overview

When a skill needs to signal that the agent should stop and return a final result, it uses the **Final Result Protocol**. This allows bash scripts to communicate structured output that terminates the agent run.

## Protocol Format

Scripts output text in this format:

```
<<<FINAL_RESULT>>>
{"key": "value", ...}
<<<END_FINAL_RESULT>>>
```

The agent's run loop:
1. Checks every bash output for `<<<FINAL_RESULT>>>`
2. Extracts JSON between the markers
3. Terminates the run loop immediately
4. Returns the JSON string as the agent's output

## Why This Design?

1. **Explicit termination**: Agent knows exactly when to stop
2. **Structured output**: JSON allows rich, parseable results
3. **Skill flexibility**: Each skill defines its own output schema
4. **Bash-compatible**: Works with any script language that can print

## Implementing in Your Skill

### 1. Create a submission script

```python
#!/usr/bin/env python3
# skills/my-skill/scripts/submit_result.py
import json
import sys

def main():
    # Your logic to build the result
    result = {
        "status": "complete",
        "data": "whatever your skill outputs"
    }

    # Output with markers
    print("<<<FINAL_RESULT>>>")
    print(json.dumps(result, indent=2))
    print("<<<END_FINAL_RESULT>>>")

if __name__ == "__main__":
    main()
```

### 2. Document in SKILL.md

Tell the agent how to use the script:

```markdown
## Submitting Results

When ready to submit your final result:

\`\`\`bash
python skills/my-skill/scripts/submit_result.py --arg value
\`\`\`
```

### 3. Agent detects and terminates

The agent run loop automatically:
- Parses the markers
- Extracts the JSON
- Stops execution
- Returns the result

## Examples

### Medical Diagnosis Skill

```bash
python submit_answer.py --answer A --reasoning "Classic presentation"
```

Output:
```
<<<FINAL_RESULT>>>
{
  "answer": "A",
  "reasoning": "Classic presentation",
  "timestamp": "2024-01-15T10:30:00"
}
<<<END_FINAL_RESULT>>>
```

### Code Review Skill (hypothetical)

```bash
python submit_review.py --status approved --comments "LGTM"
```

Output:
```
<<<FINAL_RESULT>>>
{
  "status": "approved",
  "comments": "LGTM",
  "issues": []
}
<<<END_FINAL_RESULT>>>
```

## Parsing Logic

```python
import re
import json

def parse_final_result(bash_output: str) -> tuple[bool, dict | None]:
    """
    Check if bash output contains a final result.

    Returns:
        (is_final, result_dict or None)
    """
    pattern = r'<<<FINAL_RESULT>>>\s*(.*?)\s*<<<END_FINAL_RESULT>>>'
    match = re.search(pattern, bash_output, re.DOTALL)

    if match:
        try:
            result = json.loads(match.group(1))
            return True, result
        except json.JSONDecodeError:
            return False, None

    return False, None
```

## Best Practices

1. **Always include timestamp**: Helps with debugging and logging
2. **Keep JSON simple**: Flat structures are easier to parse
3. **Document your schema**: Users of your skill need to know the output format
4. **Handle errors**: If submission fails, print a clear error (without markers)
5. **One result per run**: Only output FINAL_RESULT once; agent stops on first match
