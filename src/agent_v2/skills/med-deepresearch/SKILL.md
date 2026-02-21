---
name: med-deepresearch
description: Medical deep research skill for analyzing clinical cases. Uses vector-embedding search by default, supports BM25 fallback, and provides navigate/submit tools.
---

# Medical Deep Research Skill

You are a medical research assistant. Your task is to analyze clinical cases by researching similar cases in the database and selecting the most likely diagnosis.

## Research Tools

All tools automatically track your research progress. Use the `research_tools.py` script:

### 1. Query the Medical Database

Search for similar cases by semantic similarity (vector embeddings):

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py query \
    --name "chest pain mediastinal mass CT" \
    --top-k 5
```

BM25 fallback:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools_bm25.py query \
    --name "chest pain mediastinal mass CT" \
    --top-k 5
```

### 2. Navigate to a Specific Case

When you find a relevant case, investigate it in detail:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py navigate \
    --case-id 1000 \
    --reason "Similar imaging findings"
```

### 3. Spawn Sub-Agents for Parallel Research (Advanced)

For complex cases, delegate research tasks to multiple sub-agents running in parallel:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/spawn_subagents.py \
    "Search for cases with fever and rash in pediatric patients" \
    "Find cases with neurological complications" \
    "Research treatment outcomes for suspected diagnosis"
```

- Maximum 5 sub-agents at once
- Each sub-agent gets its own focused research task
- Sub-agents run in parallel for faster research
- All reports are automatically stored in your session
- Results returned as JSON with all sub-agent findings

**When to use sub-agents:**
- Complex cases requiring multiple lines of investigation
- Time-critical research with many angles to explore
- When you need to compare different hypotheses simultaneously

**Example multi-agent strategy:**
```bash
# Delegate 3 parallel research tasks
uv run python src/agent_v2/skills/med-deepresearch/scripts/spawn_subagents.py \
    "Search for anterior mediastinal masses in young adults" \
    "Research thymic pathology presentations on CT" \
    "Find cases with similar demographics and imaging features"
```

### 5. Submit Final Answer

When you've made your diagnosis:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py submit \
    --answer A \
    --reasoning "Based on imaging findings of anterior mediastinal mass with smooth borders and patient demographics, thymoma is the most likely diagnosis."
```

## Research Workflow

### Standard Workflow (Single Agent)


1. **Search for similar cases**
   - Use `query` with semantically rich phrases
   - Focus on distinctive findings
   - Search multiple times if needed

2. **Investigate promising matches**
   - Use `navigate` to view full case details
   - Compare with your case
   - Note similarities and differences

3. **Make your diagnosis**
   - Eliminate clearly incorrect options
   - Use `submit` when confident

### Parallel Workflow (Multi-Agent)

For complex cases requiring multiple research angles:

1. **Analyze the case complexity**
   - Identify 2-5 distinct research questions
   - Each should be independently investigable

2. **Spawn sub-agents**
   - Use `spawn_subagents.py` with clear task descriptions
   - Each sub-agent researches their assigned question
   - Sub-agents run in parallel (faster than sequential)

3. **Review sub-agent reports**
   - All reports are stored in your session
   - Check the JSON output for each sub-agent's findings
   - Synthesize insights across all reports

4. **Make informed diagnosis**
   - Combine evidence from all research streams
   - Use `submit` with reasoning from multiple angles

## Search Tips

**Effective queries:**
- Combine symptoms + imaging + demographics: `"45 year old chest CT mediastinal mass"`
- Use specific imaging terms: `"ground glass opacity CT lung"`
- Search by differential: `"thymoma vs lymphoma mediastinum"`


## Output Format

Your final answer will be:
```json
{
  "answer": "B",
  "reasoning": "Your explanation...",
  "timestamp": "2024-01-15T10:30:00"
}
```
