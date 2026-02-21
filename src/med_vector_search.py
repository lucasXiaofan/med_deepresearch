#!/usr/bin/env python3
"""
Vector search for medical cases using OpenRouter embeddings + Qdrant.

Usage:
  Index CSV into Qdrant:
    python src/med_vector_search.py index --csv deepsearch_complete.csv --recreate

  Query top-k similar cases:
    python src/med_vector_search.py query "chest pain dyspnea" -k 5
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client.models import Distance, PointStruct, VectorParams

try:
    from qdrant_vector_embedding import (
        DEFAULT_EMBEDDING_MODEL,
        embed_texts,
        get_openrouter_client,
        get_qdrant_client,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from qdrant_vector_embedding import (  # type: ignore
        DEFAULT_EMBEDDING_MODEL,
        embed_texts,
        get_openrouter_client,
        get_qdrant_client,
    )


@dataclass
class MedCase:
    case_title: str
    case_date: str
    link: str
    clinical_history: str
    imaging_findings: str
    discussion: str
    differential_diagnosis: str
    final_diagnosis: str
    images: str
    relate_case: str
    categories: str

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "MedCase":
        return cls(
            case_title=row.get("case_title", ""),
            case_date=row.get("case_date", ""),
            link=row.get("link", ""),
            clinical_history=row.get("clinical_history", ""),
            imaging_findings=row.get("imaging_findings", ""),
            discussion=row.get("discussion", ""),
            differential_diagnosis=row.get("differential_diagnosis", ""),
            final_diagnosis=row.get("final_diagnosis", ""),
            images=row.get("images", ""),
            relate_case=row.get("relate_case", ""),
            categories=row.get("Categories", ""),
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "MedCase":
        return cls(
            case_title=str(payload.get("case_title", "")),
            case_date=str(payload.get("case_date", "")),
            link=str(payload.get("link", "")),
            clinical_history=str(payload.get("clinical_history", "")),
            imaging_findings=str(payload.get("imaging_findings", "")),
            discussion=str(payload.get("discussion", "")),
            differential_diagnosis=str(payload.get("differential_diagnosis", "")),
            final_diagnosis=str(payload.get("final_diagnosis", "")),
            images=str(payload.get("images", "")),
            relate_case=str(payload.get("relate_case", "")),
            categories=str(payload.get("categories", "")),
        )

    @property
    def searchable_text(self) -> str:
        return (
            f"{self.clinical_history} {self.imaging_findings} {self.discussion} "
            f"{self.differential_diagnosis} {self.final_diagnosis}"
        ).strip()

    @property
    def related_cases_top5(self) -> str:
        if not self.relate_case:
            return "N/A"
        return ";".join(self.relate_case.split(";")[:10])

    def payload(self) -> dict[str, Any]:
        return {
            "case_title": self.case_title,
            "case_date": self.case_date,
            "link": self.link,
            "clinical_history": self.clinical_history,
            "imaging_findings": self.imaging_findings,
            "discussion": self.discussion,
            "differential_diagnosis": self.differential_diagnosis,
            "final_diagnosis": self.final_diagnosis,
            "images": self.images,
            "relate_case": self.relate_case,
            "categories": self.categories,
        }

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
{self.related_cases_top5}
{separator}
"""


def _stable_point_id(case: MedCase, row_index: int) -> int:
    match = re.search(r"Case number (\d+)", case.case_title)
    if match:
        return int(match.group(1))

    seed = case.link or f"{case.case_title}:{row_index}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def load_cases(csv_path: str) -> list[MedCase]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    cases: list[MedCase] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(MedCase.from_row(row))
    return cases


def ensure_collection(
    client: Any,
    collection_name: str,
    vector_size: int,
    distance: Distance,
    recreate: bool,
) -> None:
    exists = client.collection_exists(collection_name=collection_name)
    if exists and recreate:
        client.delete_collection(collection_name=collection_name)
        exists = False

    if not exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )


def index_cases(
    csv_path: str,
    collection_name: str,
    embed_model: str,
    batch_size: int,
    recreate: bool,
) -> None:
    qdrant = get_qdrant_client()
    openrouter = get_openrouter_client()

    print(f"Loading CSV: {csv_path}")
    cases = load_cases(csv_path)
    if not cases:
        raise RuntimeError("No cases found in CSV.")

    probe_text = next((c.searchable_text for c in cases if c.searchable_text), None)
    if not probe_text:
        raise RuntimeError("All cases have empty searchable text.")

    probe_vector = embed_texts([probe_text], model=embed_model, client=openrouter)[0]
    vector_size = len(probe_vector)
    print(f"Embedding model: {embed_model} (dimension={vector_size})")

    ensure_collection(
        client=qdrant,
        collection_name=collection_name,
        vector_size=vector_size,
        distance=Distance.COSINE,
        recreate=recreate,
    )

    total = len(cases)
    print(f"Indexing {total} cases into '{collection_name}' with batch_size={batch_size}...")
    upserted = 0

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_cases = cases[start:end]
        texts = [c.searchable_text for c in batch_cases]
        vectors = embed_texts(texts, model=embed_model, client=openrouter)

        points = [
            PointStruct(
                id=_stable_point_id(case, start + idx),
                vector=vectors[idx],
                payload=case.payload(),
            )
            for idx, case in enumerate(batch_cases)
        ]
        qdrant.upsert(collection_name=collection_name, points=points, wait=True)
        upserted += len(points)
        print(f"  upserted {upserted}/{total}")

    print("Indexing complete.")


def query_cases(
    query: str,
    top_k: int,
    collection_name: str,
    embed_model: str,
) -> int:
    if not query.strip():
        print("Empty query.")
        return 1

    qdrant = get_qdrant_client()
    openrouter = get_openrouter_client()

    print(f"\nSearching for: '{query}'")
    print("-" * 40)

    query_vector = embed_texts([query], model=embed_model, client=openrouter)[0]

    response = qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    points = response.points

    if not points:
        print("No results found.")
        return 1

    print(f"\nTop {len(points)} vector results:\n")
    for rank, point in enumerate(points, 1):
        case = MedCase.from_payload(point.payload or {})
        print(f"{'=' * 80}")
        print(f"RANK {rank} | VECTOR SCORE: {point.score:.4f}")
        print(case.display())

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Medical case vector search (OpenRouter embeddings + Qdrant)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_csv = str(Path(__file__).parent.parent / "deepsearch_complete.csv")
    default_collection = "med_deepresearch_qwen3_8b"

    index_parser = subparsers.add_parser("index", help="Index CSV into Qdrant")
    index_parser.add_argument("--csv", type=str, default=default_csv, help="Path to CSV")
    index_parser.add_argument(
        "--collection",
        type=str,
        default=default_collection,
        help="Qdrant collection name",
    )
    index_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help="OpenRouter embedding model",
    )
    index_parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding/upsert",
    )
    index_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete collection before re-indexing",
    )

    query_parser = subparsers.add_parser("query", help="Query similar cases")
    query_parser.add_argument("query", type=str, help="Search query text")
    query_parser.add_argument(
        "--top_k",
        "-k",
        type=int,
        default=5,
        help="Number of top results",
    )
    query_parser.add_argument(
        "--collection",
        type=str,
        default=default_collection,
        help="Qdrant collection name",
    )
    query_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help="OpenRouter embedding model",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "index":
        index_cases(
            csv_path=args.csv,
            collection_name=args.collection,
            embed_model=args.model,
            batch_size=args.batch_size,
            recreate=args.recreate,
        )
        return 0

    if args.command == "query":
        return query_cases(
            query=args.query,
            top_k=args.top_k,
            collection_name=args.collection,
            embed_model=args.model,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
