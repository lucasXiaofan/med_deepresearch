#!/usr/bin/env python3
"""
Generate vector-similarity related cases for target cases in a CSV.

For each target case title from med-diagnosis-relevant-search.csv:
1. Find the same case in deepsearch_complete.csv
2. Build query text from searchable fields
3. Query Qdrant vector index
4. Exclude target case ID itself
5. Save top-k related case IDs to output CSV
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(REPO_ROOT))

from qdrant_vector_embedding import DEFAULT_EMBEDDING_MODEL, embed_texts, get_openrouter_client, get_qdrant_client


def extract_case_id(case_title: str, link: str = "") -> str | None:
    match = re.search(r"Case number (\d+)", str(case_title))
    if match:
        return match.group(1)
    link_match = re.search(r"/case/(\d+)", str(link))
    if link_match:
        return link_match.group(1)
    return None


def searchable_text(row: dict[str, str]) -> str:
    return (
        f"{row.get('clinical_history', '')} "
        f"{row.get('imaging_findings', '')} "
        f"{row.get('discussion', '')} "
        f"{row.get('differential_diagnosis', '')} "
        f"{row.get('final_diagnosis', '')}"
    ).strip()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def build_case_index(corpus_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in corpus_rows:
        case_id = extract_case_id(row.get("case_title", ""), row.get("link", ""))
        if case_id:
            index[case_id] = row
    return index


def extract_point_case_id(payload: dict[str, Any]) -> str | None:
    case_title = str(payload.get("case_title", ""))
    link = str(payload.get("link", ""))
    return extract_case_id(case_title, link)


def main() -> int:
    repo_root = REPO_ROOT
    default_input = repo_root / "src" / "agent_v2" / "results" / "med-diagnosis-relevant-search.csv"
    default_corpus = repo_root / "deepsearch_complete.csv"
    default_output = repo_root / "src" / "agent_v2" / "results" / "med-diagnosis-relevant-search-vector-similarity.csv"

    parser = argparse.ArgumentParser(description="Generate vector-similarity top-k related case IDs")
    parser.add_argument("--input-csv", type=Path, default=default_input, help="Target cases CSV")
    parser.add_argument("--corpus-csv", type=Path, default=default_corpus, help="Corpus CSV")
    parser.add_argument("--output-csv", type=Path, default=default_output, help="Output CSV path")
    parser.add_argument("--collection", type=str, default="med_deepresearch_qwen3_8b", help="Qdrant collection")
    parser.add_argument("--model", type=str, default=DEFAULT_EMBEDDING_MODEL, help="Embedding model")
    parser.add_argument("--top-k", type=int, default=7, help="Number of related case IDs to keep")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=30,
        help="How many vector candidates to fetch before filtering",
    )
    args = parser.parse_args()

    target_rows = read_csv_rows(args.input_csv)
    corpus_rows = read_csv_rows(args.corpus_csv)
    corpus_index = build_case_index(corpus_rows)

    qdrant = get_qdrant_client()
    openrouter = get_openrouter_client()

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    output_rows: list[dict[str, str]] = []
    missing_targets = 0

    for idx, target in enumerate(target_rows, 1):
        target_title = target.get("case_title", "")
        target_id = extract_case_id(target_title)
        if not target_id or target_id not in corpus_index:
            missing_targets += 1
            output_rows.append(
                {
                    "case_title": target_title,
                    "relevant_cases": "",
                    "num_cases_found": "0",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"[{idx}/{len(target_rows)}] missing target in corpus: {target_title}")
            continue

        query_text = searchable_text(corpus_index[target_id])
        query_vector = embed_texts([query_text], model=args.model, client=openrouter)[0]
        response = qdrant.query_points(
            collection_name=args.collection,
            query=query_vector,
            limit=args.candidate_limit,
            with_payload=True,
        )

        related_ids: list[str] = []
        seen = {target_id}
        for point in response.points:
            payload = point.payload or {}
            related_id = extract_point_case_id(payload)
            if not related_id or related_id in seen:
                continue
            seen.add(related_id)
            related_ids.append(related_id)
            if len(related_ids) >= args.top_k:
                break

        # Keep exact schema with baseline CSV:
        # relevant_cases = "id:reason;id:reason;..."
        relevant_cases_value = ";".join([f"{rid}:vector_similarity" for rid in related_ids])
        output_rows.append(
            {
                "case_title": target_title,
                "relevant_cases": relevant_cases_value,
                "num_cases_found": str(len(related_ids)),
                "timestamp": datetime.now().isoformat(),
            }
        )
        print(f"[{idx}/{len(target_rows)}] {target_id} -> {len(related_ids)} related IDs")

    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["case_title", "relevant_cases", "num_cases_found", "timestamp"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nSaved output: {args.output_csv}")
    print(f"Rows written: {len(output_rows)}")
    print(f"Missing targets: {missing_targets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
