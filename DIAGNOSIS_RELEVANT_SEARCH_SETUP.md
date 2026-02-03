# Diagnosis-Relevant Case Search - Setup Complete

## Overview

A new agent skill system has been created to find diagnosis-relevant medical cases using parallel research sub-agents.

**What it does:**
- Takes clinical cases from CSV
- For each case, spawns an agent with specialized skill
- Agent uses 3-5 parallel sub-agents to search database from different angles
- Identifies most diagnosis-relevant cases
- Saves results incrementally to CSV

## What Was Created

### 1. New Skill: `med-diagnosis-relevant-search`

Location: `src/agent_v2/skills/med-diagnosis-relevant-search/`

```
med-diagnosis-relevant-search/
├── SKILL.md                          # Main skill documentation
├── README.md                         # Skill usage guide
├── subagent_prompt.md               # Sub-agent system prompt
└── scripts/
    ├── spawn_subagents.py           # Spawns parallel research agents
    └── terminate_and_update_csv.py  # Saves results and terminates
```

**Key Features:**
- Parallel sub-agent research (2-5 agents per case)
- Thread-safe CSV updates (multiple agents can update same file)
- Comprehensive session tracking
- Structured result format with reasoning

### 2. Agent Runner Script

Location: `src/agent_v2/agent_runner/`

```
agent_runner/
├── README.md                        # Runner documentation
└── run_diagnosis_relevant_search.py # Batch processing script
```

**Capabilities:**
- Process N cases from start
- Process specific case indices
- Custom input/output paths
- Progress monitoring and error handling

### 3. Results Directory

Location: `results/`

Created to store CSV output files.

### 4. Updated Dependencies

Modified: `pyproject.toml`

Added `filelock>=3.13.0` for thread-safe CSV writing.

## Quick Start

### Step 1: Install Dependencies

```bash
cd /Users/xiaofanlu/Documents/github_repos/med_deepresearch
uv sync
```

### Step 2: Test Run (2 cases)

```bash
cd src/agent_v2/agent_runner
python run_diagnosis_relevant_search.py
```

This will:
1. Read first 2 cases from `medd_selected_50.csv`
2. For each case:
   - Create agent with `med-diagnosis-relevant-search` skill
   - Agent spawns 3-5 parallel sub-agents
   - Sub-agents search database for relevant cases
   - Agent compiles findings
   - Results saved to `results/med-diagnosis-relevant-search.csv`

### Step 3: View Results

```bash
cat ../../results/med-diagnosis-relevant-search.csv
```

Format:
```csv
case_id,relevant_cases,num_relevant_found,timestamp
"Case number 19172","1000:Thymoma similar CT findings;1234:Mediastinal mass in young adult;1567:Smooth bordered thymic lesion",3,2026-02-02T16:30:00
```

## Usage Examples

### Process First N Cases

```bash
# Process first 5 cases
python run_diagnosis_relevant_search.py --num-cases 5

# Process all 50 cases
python run_diagnosis_relevant_search.py --num-cases 50
```

### Process Specific Cases

```bash
# Process cases at indices 0, 5, 10
python run_diagnosis_relevant_search.py --case-indices 0 5 10
```

### Custom Paths

```bash
python run_diagnosis_relevant_search.py \
    --input-csv /path/to/cases.csv \
    --output-csv /path/to/output.csv \
    --num-cases 10
```

## How It Works

### Architecture

```
Runner Script
    ├── For each case:
    │   └── Main Agent (med-diagnosis-relevant-search skill)
    │       ├── Analyzes case features
    │       ├── Designs 3-5 research queries
    │       ├── spawn_subagents.py
    │       │   ├── Sub-Agent 1: Query specific symptoms
    │       │   ├── Sub-Agent 2: Query imaging findings
    │       │   ├── Sub-Agent 3: Query demographics + condition
    │       │   ├── Sub-Agent 4: Query differential diagnosis
    │       │   └── Sub-Agent 5: Query feature combinations
    │       │   └── (All run in parallel via ThreadPoolExecutor)
    │       ├── Reviews all sub-agent findings
    │       ├── Identifies 5-10 most relevant cases
    │       └── terminate_and_update_csv.py
    │           └── Saves: case_id, relevant_cases, reasoning
    └── Final summary report
```

### Parallel Research Strategy

For a case like "27-year-old with anterior mediastinal mass on CT":

**Main Agent spawns 5 sub-agents:**
1. "Search for anterior mediastinal masses in patients aged 20-30"
2. "Find thymoma cases with CT imaging features"
3. "Research mediastinal masses presenting with chest pain"
4. "Look for cases with smooth-bordered masses on imaging"
5. "Find differential diagnoses for anterior mediastinal lesions in young adults"

**Each sub-agent:**
- Runs queries using `research_tools.py`
- Navigates to promising cases
- Reports findings with case IDs and reasoning

**Main agent:**
- Synthesizes all sub-agent reports
- Identifies cases mentioned by multiple sub-agents (high relevance)
- Selects 5-10 most diagnostically useful cases
- Saves with detailed reasoning

### Session Tracking

All research is tracked:
- **Main agent session**: `diagsearch_20260202_163000_0`
- **Sub-agent sessions**: `diagsearch_20260202_163000_0_diagsearch_sub1`, `..._sub2`, etc.

Sessions stored in: `sessions/`

View session details:
```bash
cat sessions/diagsearch_20260202_163000_0.json | jq
```

## Output Format

### CSV Columns

| Column | Description | Example |
|--------|-------------|---------|
| `case_id` | Query case analyzed | "Case number 19172" |
| `relevant_cases` | Semicolon-separated "case_id:reason" | "1000:Thymoma similar CT;1234:Young adult mediastinal mass" |
| `num_relevant_found` | Count of relevant cases | 2 |
| `timestamp` | When search completed | "2026-02-02T16:30:00" |

### Example Output

```csv
case_id,relevant_cases,num_relevant_found,timestamp
"Case number 19172","1000:Anterior mediastinal thymoma with similar age and CT findings showing smooth borders;1234:Thymic mass in 25-year-old patient with comparable imaging;1567:Young adult with chest pain and mediastinal mass on CT;2045:Thymoma case with similar smooth-bordered appearance;2389:Mediastinal lymphoma for differential comparison",5,2026-02-02T16:30:00
"Case number 19090","3456:IgG4-related disease in breast tissue;4567:Lymphocytic infiltrate mimicking carcinoma;5678:Sclerosing mastitis case;6789:Autoimmune breast lesion",4,2026-02-02T16:31:30
```

## Monitoring Progress

The runner script provides real-time progress:

```
================================================================================
Processing Case 1: Case number 19172
================================================================================

[Agent spawns sub-agents...]
[Sub-agents research in parallel...]
[Agent synthesizes findings...]
[Results saved...]

================================================================================
Completed Case 1 in 45.3s
================================================================================

Pausing 2 seconds before next case...

================================================================================
Processing Case 2: Case number 19090
================================================================================
...
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

## Performance & Cost

### Timing
- **Per case**: 30-60 seconds (with 3-5 parallel sub-agents)
- **2 cases**: ~1-2 minutes
- **50 cases**: ~25-50 minutes

### Token Usage (estimated per case)
- Main agent: ~30K tokens
- 5 sub-agents: ~52.5K tokens
- **Total**: ~82.5K tokens

### Cost (estimated, GPT-4 pricing)
- **Per case**: $0.25-$0.50
- **2 cases**: $0.50-$1.00
- **50 cases**: $12-$25

## Troubleshooting

### Common Issues

**1. Module import errors**
```bash
# Make sure you're in the right directory
cd /Users/xiaofanlu/Documents/github_repos/med_deepresearch/src/agent_v2/agent_runner

# And dependencies are installed
cd ../.. && uv sync
```

**2. CSV file not found**
```bash
# Check the input CSV path
ls /Users/xiaofanlu/Documents/github_repos/med_deepresearch/medd_selected_50.csv

# Or specify custom path
python run_diagnosis_relevant_search.py --input-csv /path/to/your/cases.csv
```

**3. Sub-agent errors**
Check session files for detailed logs:
```bash
cat sessions/diagsearch_*_sub1.json | jq '.trajectory[-1]'
```

**4. API rate limits**
Add delays between cases:
```python
# Edit run_diagnosis_relevant_search.py line 178
time.sleep(5)  # Increase from 2 to 5 seconds
```

## Next Steps

### 1. Test with 2 cases
```bash
cd src/agent_v2/agent_runner
python run_diagnosis_relevant_search.py
```

### 2. Review results
```bash
cat ../../results/med-diagnosis-relevant-search.csv
```

### 3. Check sessions for quality
```bash
ls ../../sessions/diagsearch_*
cat ../../sessions/diagsearch_*.json | jq '.store'
```

### 4. Scale up
```bash
# Process more cases
python run_diagnosis_relevant_search.py --num-cases 10
```

### 5. Analyze results
- Import CSV into spreadsheet
- Review reasoning quality
- Verify case relevance
- Identify patterns

## File Reference

**Skill Files:**
- `src/agent_v2/skills/med-diagnosis-relevant-search/SKILL.md` - Main documentation
- `src/agent_v2/skills/med-diagnosis-relevant-search/README.md` - Usage guide
- `src/agent_v2/skills/med-diagnosis-relevant-search/subagent_prompt.md` - Sub-agent prompt
- `src/agent_v2/skills/med-diagnosis-relevant-search/scripts/spawn_subagents.py` - Parallel spawner
- `src/agent_v2/skills/med-diagnosis-relevant-search/scripts/terminate_and_update_csv.py` - Result saver

**Runner Files:**
- `src/agent_v2/agent_runner/README.md` - Runner documentation
- `src/agent_v2/agent_runner/run_diagnosis_relevant_search.py` - Batch processor

**Data Files:**
- `medd_selected_50.csv` - Input cases
- `results/med-diagnosis-relevant-search.csv` - Output results
- `sessions/diagsearch_*.json` - Research sessions

## Support

For issues or questions:
1. Check the README files in each directory
2. Review session files for detailed logs
3. Verify dependencies with `uv sync`
4. Test with 1-2 cases first before scaling

---

**Setup completed on**: 2026-02-02
**Ready to run**: ✓ Yes
**Test command**: `cd src/agent_v2/agent_runner && python run_diagnosis_relevant_search.py`
