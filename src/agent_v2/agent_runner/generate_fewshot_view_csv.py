#!/usr/bin/env python3
"""Generate CSVs that mirror what fewshot_testing.py provides to the model.

For each target case in a relevant-cases CSV, output:
- target case id/title
- relevant case ids
- target limited information text (same formatter as fewshot_testing.py)
- relevant cases full information text (same builder as fewshot_testing.py)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

# Ensure src/ imports resolve when run from repo root.
SRC_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from med_search import MedSearchEngine
from agent_v2.agent_runner.fewshot_testing import (
    build_relevant_cases_fulltext,
    extract_case_number,
    format_limited_prompt,
    load_benchmark_cases,
    load_relevant_cases_csv,
)


def _build_case_lookup(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_num = extract_case_number(case.get("case_title", ""))
        if case_num:
            lookup[case_num] = case
    return lookup


def _write_output_csv(
    relevant_csv: Path,
    output_csv: Path,
    case_lookup: dict[str, dict[str, Any]],
    relevant_map: dict[str, list[tuple[str, str]]],
    relevant_fulltext: dict[str, str],
) -> None:
    rows: list[dict[str, str]] = []
    for target_case_id, entries in relevant_map.items():
        target_case = case_lookup.get(target_case_id, {})
        target_case_title = str(target_case.get("case_title", f"Case number {target_case_id}"))
        limited_info = format_limited_prompt(target_case) if target_case else ""
        relevant_ids = ";".join([case_id for case_id, _ in entries])
        relevant_with_reason = ";".join([f"{case_id}:{reason}" for case_id, reason in entries])
        full_info = relevant_fulltext.get(target_case_id, "")

        rows.append(
            {
                "source_relevant_csv": str(relevant_csv),
                "target_case_id": target_case_id,
                "target_case_title": target_case_title,
                "relevant_case_ids": relevant_ids,
                "relevant_cases_with_reason": relevant_with_reason,
                "num_relevant_cases": str(len(entries)),
                "target_limited_information": limited_info,
                "relevant_cases_full_information": full_info,
            }
        )

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "source_relevant_csv",
            "target_case_id",
            "target_case_title",
            "relevant_case_ids",
            "relevant_cases_with_reason",
            "num_relevant_cases",
            "target_limited_information",
            "relevant_cases_full_information",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {output_csv} ({len(rows)} rows)")


def main() -> int:
    default_results_dir = PROJECT_ROOT / "src" / "agent_v2" / "results"
    default_relevant_csvs = [
        default_results_dir / "med-diagnosis-relevant-search.csv",
        default_results_dir / "med-diagnosis-relevant-search-vector-similarity.csv",
    ]

    parser = argparse.ArgumentParser(description="Generate fewshot-view CSVs for relevant case files")
    parser.add_argument(
        "--relevant-csv",
        type=Path,
        action="append",
        default=None,
        help="Relevant cases CSV (can pass multiple times). Defaults to baseline + vector files.",
    )
    parser.add_argument(
        "--cases-csv",
        type=Path,
        default=PROJECT_ROOT / "medd_selected_50.csv",
        help="Benchmark cases CSV (limited-info source)",
    )
    parser.add_argument(
        "--database-csv",
        type=Path,
        default=PROJECT_ROOT / "deepsearch_complete.csv",
        help="Full database CSV (relevant full-info source)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_results_dir,
        help="Output directory for generated CSV files",
    )
    args = parser.parse_args()

    relevant_csvs = args.relevant_csv or default_relevant_csvs
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading benchmark cases: {args.cases_csv}")
    benchmark_cases = load_benchmark_cases(args.cases_csv)
    case_lookup = _build_case_lookup(benchmark_cases)
    print(f"Loaded {len(benchmark_cases)} benchmark cases ({len(case_lookup)} with valid case IDs)")

    print(f"Loading full database: {args.database_csv}")
    engine = MedSearchEngine(str(args.database_csv))

    for relevant_csv in relevant_csvs:
        print(f"\nProcessing: {relevant_csv}")
        relevant_map = load_relevant_cases_csv(relevant_csv)
        relevant_fulltext = build_relevant_cases_fulltext(relevant_map, engine)

        output_name = f"{relevant_csv.stem}-fewshot-view.csv"
        output_csv = args.output_dir / output_name
        _write_output_csv(
            relevant_csv=relevant_csv,
            output_csv=output_csv,
            case_lookup=case_lookup,
            relevant_map=relevant_map,
            relevant_fulltext=relevant_fulltext,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
