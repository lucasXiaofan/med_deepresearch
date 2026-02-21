#!/usr/bin/env python3
"""Build an LLM-ready relevance review prompt for one target case.

Given a target case ID (from medd_selected_50.csv), this script:
1. Finds the target row in medd_selected_50.csv
2. Finds its relevant case IDs from src/agent_v2/results/med-diagnosis-relevant-search.csv
3. Loads full-text info for each relevant case from deepsearch_complete.csv
4. Prints one prompt string for external LLM evaluation
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    encodings = ["utf-8", "iso-8859-1", "cp1252", "latin-1"]
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, errors="replace") as f:
                return list(csv.DictReader(f))
        except Exception:
            continue
    raise RuntimeError(f"Failed to read CSV: {path}")


def extract_case_id(case_title: str, link: str = "") -> Optional[str]:
    match = re.search(r"Case number (\d+)", str(case_title))
    if match:
        return match.group(1)
    link_match = re.search(r"/case/(\d+)", str(link))
    if link_match:
        return link_match.group(1)
    return None


def build_case_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        case_id = extract_case_id(row.get("case_title", ""), row.get("link", ""))
        if case_id:
            index[case_id] = row
    return index


def parse_relevant_cases(raw: str) -> List[Tuple[str, str]]:
    """Parse 'id:reason;id:reason' into [(id, reason), ...]."""
    out: List[Tuple[str, str]] = []
    if not raw:
        return out

    for chunk in str(raw).split(";"):
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            case_id, reason = item.split(":", 1)
            out.append((case_id.strip(), reason.strip()))
        else:
            out.append((item, ""))
    return out


def format_case_full(case: Dict[str, str]) -> str:
    return f"""CASE: {case.get('case_title', 'N/A')}
Date: {case.get('case_date', 'N/A')}
Link: {case.get('link', 'N/A')}
Categories: {case.get('Categories', case.get('categories', 'N/A'))}

--- CLINICAL HISTORY ---
{case.get('clinical_history', 'N/A') or 'N/A'}

--- IMAGING FINDINGS ---
{case.get('imaging_findings', 'N/A') or 'N/A'}

--- DIFFERENTIAL DIAGNOSIS ---
{case.get('differential_diagnosis', 'N/A') or 'N/A'}

--- FINAL DIAGNOSIS ---
{case.get('final_diagnosis', case.get('correct_answer_text', 'N/A')) or 'N/A'}
"""


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    selected_csv = repo_root / "medd_selected_50.csv"
    relevant_csv = repo_root / "src" / "agent_v2" / "results" / "med-diagnosis-relevant-search.csv"
    corpus_csv = repo_root / "deepsearch_complete.csv"

    parser = argparse.ArgumentParser(description="Build relevance review prompt for one target case")
    parser.add_argument("--case-id", required=True, help="Target case ID, e.g., 13775")
    parser.add_argument("--selected-csv", type=Path, default=selected_csv)
    parser.add_argument("--relevant-csv", type=Path, default=relevant_csv)
    parser.add_argument("--corpus-csv", type=Path, default=corpus_csv)
    args = parser.parse_args()

    target_case_id = str(args.case_id).strip()

    selected_rows = read_csv_rows(args.selected_csv)
    relevant_rows = read_csv_rows(args.relevant_csv)
    corpus_rows = read_csv_rows(args.corpus_csv)

    selected_index = build_case_index(selected_rows)
    corpus_index = build_case_index(corpus_rows)

    target_row = selected_index.get(target_case_id)
    if not target_row:
        raise SystemExit(f"Target case ID {target_case_id} not found in {args.selected_csv}")

    target_title = target_row.get("case_title", "")
    result_row = next((r for r in relevant_rows if r.get("case_title", "") == target_title), None)
    if not result_row:
        raise SystemExit(
            f"Target case {target_case_id} ({target_title}) not found in {args.relevant_csv}"
        )

    parsed_relevant = parse_relevant_cases(result_row.get("relevant_cases", ""))
    relevant_blocks: List[str] = []
    for i, (rel_id, retrieval_reason) in enumerate(parsed_relevant, 1):
        rel_row = corpus_index.get(rel_id)
        if not rel_row:
            block = (
                f"### Relevant Case {i}\n"
                f"Retrieved Case ID: {rel_id}\n"
                f"Retriever Reason: {retrieval_reason or 'N/A'}\n"
                f"[Full text not found in corpus CSV]\n"
            )
        else:
            block = (
                f"### Relevant Case {i}\n"
                f"Retrieved Case ID: {rel_id}\n"
                f"Retriever Reason: {retrieval_reason or 'N/A'}\n\n"
                f"{format_case_full(rel_row)}"
            )
        relevant_blocks.append(block)

    prompt = f"""
TASK:
For case {target_case_id} Evaluate whether the retrieved cases are directly relevant to diagnosing the target case .
You are a radiology relevance judge.
Return:
1) target_case_id
2) short_target_summary (1-3 sentences)
3) needs_image_understanding (true/false)
4) needs_image_understanding_reason (why image nuance is required or not)
5) per relevant case:
   - relevant_case_id
   - relevance_score
   - rationale
   - most_important_signal (what specifically helps diagnosis, or why misleading)

Scoring guide:
- 5: highly and directly supports/helps distinguish target diagnosis
- 4: strong relevance with minor mismatch
- 3: partially relevant, limited diagnostic value
- 2: weak relevance, mostly tangential
- 1: not relevant or misleading

Output format:
Return strict JSON:
{{
  "target_case_id": "...",
  "short_target_summary": "...",
  "needs_image_understanding": true,
  "needs_image_understanding_reason": "...",
  "relevant_case_reviews": [
    {{
      "relevant_case_id": "...",
      "relevance_score": 5,
      "rationale": "...",
      "most_important_signal": "..."
    }}
  ]
}}

================ TARGET CASE ================
Target Case ID: {target_case_id}
{format_case_full(target_row)}

================ RETRIEVED RELEVANT CASES ================
{chr(10).join(relevant_blocks)}
"""

    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

