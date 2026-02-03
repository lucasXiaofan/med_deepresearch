# Related Cases Scripts

Two scripts for extracting and querying related medical cases.

## Scripts

### 1. `extract_related_cases.py`

Extracts all related cases from selected_50 and creates a CSV output.

**Features:**
- Reads all cases from `medd_selected_50.csv`
- Finds related cases from `deepsearch_complete.csv`
- **Filters out** related cases that exist in selected_50
- **Filters out** the source case itself
- Generates a CSV with all related case mappings

**Usage:**
```bash
uv run src/extract_related_cases.py
```

**Output:**
- File: `src/related_cases_output.csv`
- Columns:
  - `source_case_id` - ID from selected_50
  - `source_case_title` - Title of source case
  - `related_case_id` - ID of related case
  - `related_case_title` - Title of related case
  - `related_case_link` - URL to related case
  - `related_case_diagnosis` - Final diagnosis
  - `related_case_categories` - Case categories

**Recent Results:**
- Total cases processed: 50
- Related cases filtered (in selected_50): 16
- Total valid related cases: 1,996
- Average related cases per source: 51.18

---

### 2. `query_related_cases.py`

Query tool to get formatted details of related cases for a specific case ID.

**Features:**
- Input a case ID and get k related cases
- Returns full case details in formatted text
- **Filters out** cases that exist in selected_50
- **Filters out** the source case itself
- Easy to read, formatted output

**Usage:**
```bash
uv run src/query_related_cases.py <case_id> --k <number_of_cases>
```

**Examples:**
```bash
# Get 10 related cases for case 19172
uv run src/query_related_cases.py 19172 --k 10

# Get 5 related cases for case 19090
uv run src/query_related_cases.py 19090 --k 5

# Get 3 related cases for case 17930
uv run src/query_related_cases.py 17930 --k 3
```

**Output Format:**

Each case includes:
- Case ID and Title
- Date and Link
- Final Diagnosis
- Categories
- Clinical History (first 500 chars)
- Imaging Findings (first 500 chars)
- Differential Diagnosis

**Example Output:**
```
################################################################################
QUERY RESULTS FOR CASE ID: 19172
################################################################################

Source Case: Case number 19172
Total related cases found: 2 (limited to k=3)

================================================================================
RELATED CASE #1
================================================================================

Case ID: 18689
Case Title: Case number 18689
Date: 2024/12/9
Link: https://www.eurorad.org/case/18689

Final Diagnosis:
--------------------------------------------------------------------------------
Ovarian ectopic pregnancy

Categories:
--------------------------------------------------------------------------------
Area of InterestGenital / Reproductive system female, Obstetrics...

[etc...]
```

## Important Notes

1. **Filtering**: Both scripts automatically filter out:
   - The source case itself
   - Any cases that appear in `medd_selected_50.csv`

2. **File Paths**: Scripts expect data files at:
   - `/Users/xiaofanlu/Documents/github_repos/med_deepresearch/medd_selected_50.csv`
   - `/Users/xiaofanlu/Documents/github_repos/med_deepresearch/deepsearch_complete.csv`

3. **Encoding**: Scripts handle multiple encodings automatically (UTF-8, Latin-1, etc.)

4. **Error Handling**: If a case ID is not found or has no related cases, the scripts will inform you

## Requirements

- Python 3.x
- `uv` package manager
- CSV files in the expected locations
