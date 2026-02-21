---
name: med-diagnosis-relevant-search
description: Vision-based medical case search agent. Queries the database, navigates cases to inspect images, and submits diagnosis-relevant cases with imaging evidence.
---

# Medical Diagnosis-Relevant Case Search

When you navigate to a case, its medical images are **automatically displayed** to you.

## Your Goal

Given a target case with a known correct diagnosis, find cases from the database whose **imaging features** help confirm or differentiate that diagnosis. You must examine images and cite specific visual findings.

## Tools

### 1. Query the Database

Search by semantic meaning (diagnosis, imaging patterns, clinical context):

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py query \
    --name "ground glass opacity CT lung" \
    --top-k 5
```

- Returns case summaries ranked by vector similarity (embedding search)
- Each result includes: clinical history, imaging findings, diagnosis, and **image captions**
- Use 2-3 queries with different semantic phrasing strategies

### 2. Navigate to a Case (Images Auto-Loaded)

Inspect a case in detail — **images are automatically shown to you**:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py navigate \
    --case-id 1000 \
    --reason "Similar CT pattern to target case"
```

- Shows full case details (history, findings, diagnosis, related cases)
- **Medical images for the case are automatically injected into your context**
- You can directly see and analyze the images
- **LIMIT: Navigate at most 12 cases total** — choose wisely

### 3. Submit Results

When done, submit your findings with `submit_results.py`:

```bash
uv run python src/agent_v2/skills/med-diagnosis-relevant-search/scripts/submit_results.py \
    --relevant-cases '{"1234": "CT shows ground-glass opacity with crazy-paving pattern, consistent with alveolar proteinosis - same pattern as target case", "5678": "MRI demonstrates periventricular white matter lesions distinguishing MS from ADEM"}'
```

- `--relevant-cases` is a JSON object: `{"case_id": "reason citing imaging features", ...}`
- **You MUST call this** — it terminates the agent and saves results
- Every reason should cite **specific imaging features** you observed

### Step-by-Step

1. **Query** the database with different semantic strategies to cover the candidate diagnoses:
   - Search by the correct diagnosis name
   - Search by key imaging findings from the target case
   - Search by differential diagnosis and look-alike patterns

2. **Select candidates** from query results — pick cases whose summaries suggest relevant imaging

3. **Navigate** to each candidate (max 10 total):
   - **Look at the images** shown to you
   - Note specific imaging features (e.g., "enhancing ring lesion", "ground-glass opacity")
   - Compare with the target case's imaging findings
   - Decide: does this case help confirm or differentiate the diagnosis?

4. **Submit results** with `submit_results.py`:
   - Include only cases with clear imaging relevance
   - Each reason must cite specific imaging features you observed
   - Quality over quantity — exclude weak matches

## Case Inclusion Criteria

**Include** a case if:
- At least one defining imaging feature is shared with the target case
- The imaging evidence helps confirm the correct diagnosis OR meaningfully distinguishes it from a differential
- Features cited are directly observable in the images or described in imaging findings

**Exclude** a case if:
- No shared imaging features with the target case
- Key imaging features are not assessable
- The case is non-discriminative (matches everything without adding diagnostic insight)

## Search Tips

**Effective queries:**
- Combine anatomy + modality + finding: `"liver CT hypervascular lesion"`
- Use the diagnosis name directly: `"hepatocellular carcinoma"`
- Search differential terms: `"hemangioma vs HCC liver"`


## Output Format

Your final result (via `submit_results.py`) will be:
```json
{
  "relevant_cases": {
    "1234": "CT shows characteristic finding X that confirms diagnosis Y",
    "5678": "MRI demonstrates feature Z that distinguishes A from B"
  },
  "num_cases_found": 2,
  "timestamp": "2026-02-09T..."
}
```
