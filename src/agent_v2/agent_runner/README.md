# Agent Runner Scripts

This directory contains scripts for running agents in batch mode.

## Available Runners

### run_diagnosis_relevant_search.py

Processes multiple clinical cases and finds diagnosis-relevant cases from the database using parallel sub-agents.

**Quick Start:**

```bash
cd /Users/xiaofanlu/Documents/github_repos/med_deepresearch/src/agent_v2/agent_runner

# Process first 2 cases (initial test)
python run_diagnosis_relevant_search.py
```

**Options:**

```bash
# Process first N cases
python run_diagnosis_relevant_search.py --num-cases 5

# Process specific cases by index (0-based)
python run_diagnosis_relevant_search.py --case-indices 0 5 10 15

# Custom input/output files
python run_diagnosis_relevant_search.py \
    --input-csv /path/to/cases.csv \
    --output-csv /path/to/results.csv \
    --num-cases 10

# Custom session directory
python run_diagnosis_relevant_search.py \
    --session-dir /path/to/sessions \
    --num-cases 3
```

**How It Works:**

1. Reads clinical cases from CSV (default: `medd_selected_50.csv`)
2. For each case:
   - Creates an agent with `med-diagnosis-relevant-search` skill
   - Agent analyzes the case features
   - Agent spawns 3-5 parallel sub-agents for research
   - Sub-agents search database from different angles
   - Agent synthesizes findings and identifies most relevant cases
   - Results saved to CSV (incrementally updated)
3. Generates summary report

**Output:**

Results saved to `results/med-diagnosis-relevant-search.csv`:

| case_id | relevant_cases | num_relevant_found | timestamp |
|---------|----------------|-------------------|-----------|
| Case number 19172 | 1000:Thymoma similar CT;1234:Mediastinal mass | 2 | 2026-02-02T16:30:00 |

**Sessions:**

Each agent run creates a session in `sessions/` directory:
- Main agent: `diagsearch_YYYYMMDD_HHMMSS_N`
- Sub-agents: `diagsearch_YYYYMMDD_HHMMSS_N_diagsearch_sub1`, `..._sub2`, etc.

Sessions contain full research trajectory for debugging.

## Prerequisites

1. Install dependencies:
```bash
cd /Users/xiaofanlu/Documents/github_repos/med_deepresearch
uv sync
```

2. Set up environment variables in `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
# Or whichever LLM provider you're using
```

3. Ensure medical database is accessible (via `med_search.py`)

## Examples

### Test Run (2 cases)

```bash
python run_diagnosis_relevant_search.py
```

### Production Run (all 50 cases)

```bash
python run_diagnosis_relevant_search.py --num-cases 50
```

### Specific Cases

```bash
# Process cases at indices 0, 10, 20, 30, 40
python run_diagnosis_relevant_search.py --case-indices 0 10 20 30 40
```

## Monitoring

The script prints progress for each case:

```
================================================================================
Processing Case 1: Case number 19172
================================================================================

[Agent output...]

================================================================================
Completed Case 1 in 45.3s
================================================================================
```

Final summary:

```
================================================================================
BATCH RUN COMPLETE
================================================================================
Total cases processed: 2
Successful: 2
Failed: 0

Results saved to: results/med-diagnosis-relevant-search.csv
Sessions saved to: sessions/
================================================================================

✓ Case 1: Case number 19172
  Time: 45.3s, Session: diagsearch_20260202_163000_0
✓ Case 2: Case number 19090
  Time: 42.1s, Session: diagsearch_20260202_163100_1
```

## Troubleshooting

**Error: Input CSV file not found**
- Check the path in `--input-csv`
- Default expects `medd_selected_50.csv` in project root

**Error: AGENT_SESSION_ID not set**
- This is normal - the script sets this automatically
- If you see this, it means the sub-scripts are being called incorrectly

**Sub-agent errors**
- Check session files for detailed error messages
- Verify `research_tools.py` is accessible
- Ensure medical database (`med_search.py`) is working

**CSV formatting issues**
- The script uses filelock for thread-safe writes
- If CSV is corrupted, delete it and re-run
- Check for special characters in case descriptions

## Performance

- Each case takes ~30-60 seconds with parallel sub-agents
- 50 cases: ~25-50 minutes total
- Time varies based on:
  - API response time
  - Number of sub-agents spawned (2-5 per case)
  - Database query complexity
  - Number of cases navigated

## Cost Estimation

With parallel sub-agents (assuming GPT-4 or similar):
- Main agent: ~15 turns × 2K tokens = ~30K tokens
- 5 sub-agents: 5 × 7 turns × 1.5K tokens = ~52.5K tokens
- **Total per case**: ~82.5K tokens (~$0.25-$0.50)
- **50 cases**: ~4M tokens (~$12-$25)

Actual costs depend on your LLM provider and model choice.
