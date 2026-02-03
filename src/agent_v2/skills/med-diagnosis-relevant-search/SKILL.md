---
name: med-diagnosis-relevant-search
description: Find cases relevant to making the correct diagnosis. Use parallel sub-agents with mixed strategies (case investigation + feature search) to find diagnostically relevant cases.
---

# Medical Diagnosis Relevant Case Search

You know the CORRECT DIAGNOSIS. Find cases that would help make this diagnosis. 8-10 turns max.

## WORKFLOW

### Step 1: Initial Query (1-2 queries)

Query the database to get candidate cases:

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/research_tools.py query \
    --name "septate uterus placental implantation" \
    --top-k 15
```

**Goal:** Get candidate case IDs and understand what's in the database.

### Step 2: Spawn 3-5 Sub-Agents with MIXED Strategies (REQUIRED)

Spawn sub-agents with DIFFERENT strategies - some investigate case IDs, some search features. Mix it up!

**Example: For diagnosis "Gravid septate uterus with septal placental implantation"**

```bash
uv run python src/agent_v2/skills/med-deepresearch/scripts/spawn_subagents.py \
    "Investigate cases 1234, 5678, 9012 from initial search - determine if they show septate uterus features relevant to this diagnosis and WHY they help make this diagnosis Gravid septate uterus with septal placental implantation" \
    "Search for uterine septum imaging cases - find cases showing clear septum anatomy that would help identify septate uterus, return case IDs and diagnostic relevance, Gravid septate uterus with septal placental implantation" \
    "Investigate cases 3456, 7890 - check if placental implantation patterns match our diagnosis and explain diagnostic value, Gravid septate uterus with septal placental implantation" \
    "Search for gravid uterine anomalies - find pregnancy cases with congenital malformations, identify which are relevant to diagnosing septate uterus, Gravid septate uterus with septal placental implantation" \
    "Search for septate vs bicornuate uterus - find cases showing differential features that help distinguish septate uterus diagnosis, Gravid septate uterus with septal placental implantation"
```

**CRITICAL - Each sub-agent must:**
1. Find relevant cases (by investigating case IDs OR searching)
2. Return case IDs they found
3. Explain WHY each case is relevant to the CORRECT DIAGNOSIS
4. Focus on diagnostic value: "This case shows X feature which helps confirm/distinguish this diagnosis"


**Each sub-agent reports back:**
- Case IDs found
- WHY those cases help make the diagnosis (specific features, imaging findings, clinical presentation)

### Step 3: Submit Results (REQUIRED)

Compile all relevant cases from sub-agents and submit:

```bash
uv run python src/agent_v2/skills/med-diagnosis-relevant-search/scripts/submit_results.py \
    --relevant-cases '{"1234": "Septate uterus with clear septum on ultrasound - demonstrates key diagnostic feature for identifying uterine septum", "5678": "Placental implantation on septum - shows the specific placental location diagnostic of this condition", "9012": "Gravid septate uterus imaging - shows complete diagnostic presentation with pregnancy and septum visible"}'
```

**IMPORTANT:**
- You MUST call submit_results.py
- Case reasons must explain DIAGNOSTIC RELEVANCE (why this case helps make the diagnosis)
- Focus on cases showing key diagnostic features

## Key Points

- **You know the correct diagnosis** - Find cases relevant to MAKING that diagnosis
- **Initial query first** - Get candidate cases
- **Mix strategies** - Some sub-agents investigate case IDs, some search features
- **Goal: Diagnostic relevance** - Cases must help make/confirm the diagnosis
- **8-10 turns max** - Be efficient
- **Always submit** - Use submit_results.py with diagnostically relevant cases
- **5-10 cases** - Quality over quantity

## Example Strategies

**Diagnosis: "Thymoma"**
```bash
spawn_subagents.py \
    "Investigate cases 1000, 2000, 3000 - check if anterior mediastinal location and imaging features are diagnostic of thymoma" \
    "Search for thymic masses in young adults - find cases with age demographics that help identify thymoma" \
    "Search for smooth-bordered mediastinal masses - find imaging patterns diagnostic of thymoma vs lymphoma" \
    "Investigate cases 4000, 5000 - verify if CT characteristics match thymoma diagnosis"
```

**Diagnosis: "Osteoid osteoma"**
```bash
spawn_subagents.py \
    "Search for night pain bone lesions - find cases showing classic clinical presentation of osteoid osteoma" \
    "Investigate cases 1500, 2500 - check if nidus on CT is visible, diagnostic feature for osteoid osteoma" \
    "Search for aspirin-responsive bone pain - find cases with this pathognomonic feature" \
    "Search for cortical bone lesions in young patients - find demographic and location patterns diagnostic of osteoid osteoma"
```
