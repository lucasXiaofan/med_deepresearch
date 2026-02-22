#!/usr/bin/env python3
"""
Create a filtered relevant-cases CSV for re-running fewshot_testing.py.

Filters to:
  1. Only target cases that are "both wrong" or "-1 (correct→wrong)"
  2. Only relevant cases with relevance score >= 4 from external_llm_reviews.txt

Output:
  src/agent_v2/results/med-diagnosis-relevant-search-filtered-high.csv
  (same format as med-diagnosis-relevant-search.csv so fewshot_testing.py
   can consume it with --relevant-csv)
"""

import csv
import json
import re
import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent
PROJECT_ROOT = SRC_DIR.parent
GPT52_DIR = SRC_DIR / "gpt52_verification"
FEWSHOT_DIR = SRC_DIR / "agent_v2" / "fewshot_results"
RESULTS_DIR = SRC_DIR / "agent_v2" / "results"

REVIEWS_FILE = GPT52_DIR / "external_llm_reviews_v1.txt"
ORIGINAL_CSV = RESULTS_DIR / "med-diagnosis-relevant-search.csv"
OUTPUT_CSV   = RESULTS_DIR / "med-diagnosis-relevant-search-filtered-high.csv"

MIN_SCORE = 4


# ── helpers ───────────────────────────────────────────────────────────────────

def load_latest_fewshot_results() -> dict:
    jsons = sorted(FEWSHOT_DIR.glob("fewshot_results_*.json"))
    if not jsons:
        raise FileNotFoundError(f"No fewshot result JSONs in {FEWSHOT_DIR}")
    path = jsons[-1]
    print(f"Fewshot results: {path.name}")
    with open(path) as f:
        return json.load(f)


def target_cases_to_keep(fewshot_data: dict) -> set[str]:
    """Return case numbers that are 'both wrong' or '-1 (correct→wrong)'."""
    baseline_map = {r["case_number"]: r for r in fewshot_data["modes"]["baseline"]["results"]}
    fewshot_map  = {r["case_number"]: r for r in fewshot_data["modes"]["fewshot"]["results"]}

    keep = set()
    for cn, b in baseline_map.items():
        f = fewshot_map.get(cn, {})
        bc = b.get("correct", False)
        fc = f.get("correct", False)
        # both wrong OR correct→wrong (-1)
        if not fc:
            keep.add(cn)
    return keep


def parse_high_score_ids(reviews_path: Path, min_score: int) -> dict[str, set[str]]:
    """
    Parse external_llm_reviews.txt.
    Returns {target_case_id: {relevant_case_id, ...}} for cases with score >= min_score.
    """
    text = reviews_path.read_text(encoding="utf-8")
    blocks = re.split(r"={40,}", text)
    high: dict[str, set[str]] = {}

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = re.match(r"CASE_ID:\s*(\d+)", block)
        if not m:
            continue
        case_id = m.group(1)

        json_start = block.find("{")
        json_end = block.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            continue
        try:
            data = json.loads(block[json_start:json_end])
        except json.JSONDecodeError:
            continue

        good_ids: set[str] = set()
        for rc in data.get("relevant_case_reviews", []):
            rc_id = str(rc.get("relevant_case_id", ""))
            score = rc.get("relevance_score", 0)
            if re.match(r"^\d+$", rc_id) and isinstance(score, int) and score >= min_score:
                good_ids.add(rc_id)

        high[case_id] = good_ids

    return high


def load_original_relevant_csv(path: Path) -> dict[str, dict]:
    """
    Load original CSV.
    Returns {case_number: {"case_title": ..., "relevant_cases": "id:reason;...", ...}}
    """
    result = {}
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            with open(path, encoding=enc, errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = row.get("case_title", "")
                    m = re.search(r"Case number (\d+)", title)
                    if not m:
                        continue
                    result[m.group(1)] = dict(row)
            break
        except UnicodeDecodeError:
            continue
    print(f"Original CSV: {len(result)} rows")
    return result


def filter_relevant_str(relevant_str: str, keep_ids: set[str]) -> str:
    """
    Parse 'id:reason;id:reason;...' and return only entries whose id is in keep_ids.
    """
    # Regex: capture id and everything up to next 'digits:' or end
    entries = re.findall(r"(\d+):(.+?)(?=;\d+:|$)", relevant_str)
    kept = [(cid, reason.strip()) for cid, reason in entries if cid in keep_ids]
    return ";".join(f"{cid}:{reason}" for cid, reason in kept)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    fewshot_data   = load_latest_fewshot_results()
    target_keep    = target_cases_to_keep(fewshot_data)
    high_score_ids = parse_high_score_ids(REVIEWS_FILE, MIN_SCORE)
    original_rows  = load_original_relevant_csv(ORIGINAL_CSV)

    print(f"\nTarget cases to keep (both-wrong + -1): {sorted(target_keep, key=int)}")
    print(f"Total: {len(target_keep)}")

    output_rows = []
    for case_num in sorted(target_keep, key=int):
        if case_num not in original_rows:
            print(f"  [WARN] Case {case_num} not found in original CSV — skipping")
            continue

        row = dict(original_rows[case_num])
        original_rel = row.get("relevant_cases", "")
        high_ids = high_score_ids.get(case_num, set())

        filtered_rel = filter_relevant_str(original_rel, high_ids)
        kept_count   = len(re.findall(r"\d+:", filtered_rel)) if filtered_rel else 0
        total_count  = len(re.findall(r"\d+:", original_rel)) if original_rel else 0

        print(f"  Case {case_num}: {total_count} → {kept_count} relevant cases "
              f"(kept IDs with score≥{MIN_SCORE}: {sorted(high_ids, key=int)})")

        row["relevant_cases"] = filtered_rel
        row["num_cases_found"] = str(kept_count)
        output_rows.append(row)

    # Write filtered CSV
    fieldnames = ["case_title", "relevant_cases", "num_cases_found", "timestamp"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nWritten: {OUTPUT_CSV}")
    print(f"Rows: {len(output_rows)}")
    print(f"\nRun fewshot_testing.py with:")
    print(f"  uv run python src/agent_v2/agent_runner/fewshot_testing.py \\")
    print(f"    --relevant-csv {OUTPUT_CSV.relative_to(PROJECT_ROOT)} \\")
    print(f"    --mode fewshot \\")
    print(f"    --model x-ai/grok-4.1-fast --model-type vision")


if __name__ == "__main__":
    main()
