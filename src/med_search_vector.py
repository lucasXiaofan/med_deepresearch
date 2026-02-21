#!/usr/bin/env python3
"""Medical case vector-embedding search over Qdrant payloads."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qdrant_vector_embedding import (
    DEFAULT_EMBEDDING_MODEL,
    embed_texts,
    get_openrouter_client,
    get_qdrant_client,
)


@dataclass
class MedCaseView:
    case_title: str
    case_date: str
    link: str
    clinical_history: str
    imaging_findings: str
    differential_diagnosis: str
    final_diagnosis: str
    categories: str

    @property
    def related_cases_top20(self) -> str:
        return "N/A"

    def display(self) -> str:
        separator = "=" * 20
        return f"""
{separator}
CASE: {self.case_title}
Date: {self.case_date}
Link: {self.link}
Categories: {self.categories}

--- CLINICAL HISTORY ---
{self.clinical_history or 'N/A'}

--- IMAGING FINDINGS ---
{self.imaging_findings or 'N/A'}

--- DIFFERENTIAL DIAGNOSIS ---
{self.differential_diagnosis or 'N/A'}

--- FINAL DIAGNOSIS ---
{self.final_diagnosis or 'N/A'}

--- RELATED CASES ---
{self.related_cases_top20}
{separator}
"""


def extract_case_id(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"Case number (\d+)", text)
    if match:
        return int(match.group(1))
    link_match = re.search(r"/case/(\d+)", text)
    if link_match:
        return int(link_match.group(1))
    if text.strip().isdigit():
        return int(text.strip())
    return None


def load_case_index(csv_path: Path) -> dict[int, dict[str, str]]:
    index: dict[int, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_id = extract_case_id(f"{row.get('case_title', '')} {row.get('link', '')}")
            if case_id is not None:
                index[case_id] = row
    return index


def row_to_view(row: dict[str, str]) -> MedCaseView:
    return MedCaseView(
        case_title=row.get("case_title", ""),
        case_date=row.get("case_date", ""),
        link=row.get("link", ""),
        clinical_history=row.get("clinical_history", ""),
        imaging_findings=row.get("imaging_findings", ""),
        differential_diagnosis=row.get("differential_diagnosis", ""),
        final_diagnosis=row.get("final_diagnosis", ""),
        categories=row.get("Categories", row.get("categories", "")),
    )


def payload_to_view(payload: dict[str, Any]) -> MedCaseView:
    return MedCaseView(
        case_title=str(payload.get("case_title", "")),
        case_date=str(payload.get("case_date", "")),
        link=str(payload.get("link", "")),
        clinical_history=str(payload.get("clinical_history", "")),
        imaging_findings=str(payload.get("imaging_findings", "")),
        differential_diagnosis=str(payload.get("differential_diagnosis", "")),
        final_diagnosis=str(payload.get("final_diagnosis", "")),
        categories=str(payload.get("Categories", payload.get("categories", ""))),
    )


def vector_search(
    query: str,
    top_k: int,
    candidate_limit: int,
    collection: str,
    model: str,
) -> list[tuple[MedCaseView, float]]:
    qdrant = get_qdrant_client()
    openrouter = get_openrouter_client()

    query_vector = embed_texts([query], model=model, client=openrouter)[0]
    response = qdrant.query_points(
        collection_name=collection,
        query=query_vector,
        limit=max(top_k, candidate_limit),
        with_payload=True,
    )

    results: list[tuple[MedCaseView, float]] = []
    for point in response.points:
        payload = point.payload or {}
        score = float(point.score) if point.score is not None else 0.0
        results.append((payload_to_view(payload), score))
        if len(results) >= top_k:
            break

    return results


def main() -> int:
    default_csv = Path(__file__).parent.parent / "deepsearch_filtered.csv"

    parser = argparse.ArgumentParser(
        description="Medical case vector search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="Search query text or case number")
    parser.add_argument("--top_k", "-k", type=int, default=5, help="Number of results")
    parser.add_argument("--candidate-limit", type=int, default=20, help="Vector candidates to fetch")
    parser.add_argument("--collection", type=str, default="med_deepresearch_qwen3_8b", help="Qdrant collection")
    parser.add_argument("--model", type=str, default=DEFAULT_EMBEDDING_MODEL, help="Embedding model")
    parser.add_argument("--csv", type=Path, default=default_csv, help="CSV path for case-id navigation")
    args = parser.parse_args()

    print(f"\nSearching for: '{args.query}'")
    print("-" * 40)

    case_id_query = extract_case_id(args.query)
    if case_id_query is not None:
        case_index = load_case_index(args.csv)
        if case_id_query not in case_index:
            print(f"Error: Case number {case_id_query} does not exist in the database.")
            return 1
        case = row_to_view(case_index[case_id_query])
        print("\nFound exact match for case number:")
        print(case.display())
        return 0

    try:
        results = vector_search(
            query=args.query,
            top_k=args.top_k,
            candidate_limit=args.candidate_limit,
            collection=args.collection,
            model=args.model,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error running vector search: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("No results found.")
        return 1

    print(f"\nTop {len(results)} results:\n")
    for rank, (case, score) in enumerate(results, 1):
        print(f"{'=' * 80}")
        print(f"RANK {rank} | VECTOR SCORE: {score:.4f}")
        print(case.display())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
