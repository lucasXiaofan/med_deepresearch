#!/usr/bin/env python3
"""
Medical Case BM25 Search Engine

Supports two search modes:
1. Text query mode: Uses BM25 to rank cases based on clinical_history, imaging_findings, and discussion
2. Case number mode: Direct lookup by case number (e.g., "1000" matches "Case number 1000")
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi


@dataclass
class MedCase:
    """Represents a medical case from the dataset."""
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

    @property
    def case_number(self) -> Optional[int]:
        """Extract case number from title."""
        match = re.search(r'Case number (\d+)', self.case_title)
        if match:
            return int(match.group(1))
        return None

    @property
    def searchable_text(self) -> str:
        """Combined text for BM25 indexing."""
        return f"{self.clinical_history} {self.imaging_findings} {self.discussion}"

    @property
    def related_cases_top5(self) -> str:
        """Get top 5 related cases."""
        if not self.relate_case:
            return 'N/A'
        cases = self.relate_case.split(';')[:5]
        return ';'.join(cases)

    def display(self) -> str:
        """Format case for display."""
        separator = "=" * 80
        return f"""
{separator}
CASE: {self.case_title}
{separator}
Date: {self.case_date}
Link: {self.link}
Categories: {self.categories}

--- CLINICAL HISTORY ---
{self.clinical_history or 'N/A'}

--- IMAGING FINDINGS ---
{self.imaging_findings or 'N/A'}

--- DISCUSSION ---
{self.discussion or 'N/A'}

--- DIFFERENTIAL DIAGNOSIS ---
{self.differential_diagnosis or 'N/A'}

--- FINAL DIAGNOSIS ---
{self.final_diagnosis or 'N/A'}

--- IMAGES ---
{self.images or 'N/A'}

--- RELATED CASES (Top 5) ---
{self.related_cases_top5}
{separator}
"""


class MedSearchEngine:
    """BM25-based medical case search engine."""

    def __init__(self, csv_path: str):
        self.cases: list[MedCase] = []
        self.case_number_index: dict[int, MedCase] = {}
        self.bm25: Optional[BM25Okapi] = None
        self._load_data(csv_path)
        self._build_index()

    def _load_data(self, csv_path: str) -> None:
        """Load cases from CSV file."""
        print(f"Loading data from {csv_path}...")
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                case = MedCase(
                    case_title=row.get('case_title', ''),
                    case_date=row.get('case_date', ''),
                    link=row.get('link', ''),
                    clinical_history=row.get('clinical_history', ''),
                    imaging_findings=row.get('imaging_findings', ''),
                    discussion=row.get('discussion', ''),
                    differential_diagnosis=row.get('differential_diagnosis', ''),
                    final_diagnosis=row.get('final_diagnosis', ''),
                    images=row.get('images', ''),
                    relate_case=row.get('relate_case', ''),
                    categories=row.get('Categories', ''),
                )
                self.cases.append(case)

                # Index by case number
                if case.case_number is not None:
                    self.case_number_index[case.case_number] = case

        print(f"Loaded {len(self.cases)} cases.")

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric."""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens

    def _build_index(self) -> None:
        """Build BM25 index from cases."""
        print("Building BM25 index...")
        tokenized_corpus = [self._tokenize(case.searchable_text) for case in self.cases]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print("Index built successfully.")

    def _is_case_number_query(self, query: str) -> Optional[int]:
        """Check if query is a case number lookup."""
        query = query.strip()
        # Match pure numbers or "case 1000" or "case number 1000"
        if query.isdigit():
            return int(query)
        match = re.match(r'^case\s*(?:number\s*)?(\d+)$', query, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def search(self, query: str, top_k: int = 5) -> list[tuple[MedCase, float]]:
        """
        Search for cases matching the query.

        Returns list of (case, score) tuples.
        For case number queries, score is 1.0 for exact match.
        For text queries, score is BM25 score.
        """
        # Check if it's a case number query
        case_number = self._is_case_number_query(query)
        if case_number is not None:
            if case_number in self.case_number_index:
                return [(self.case_number_index[case_number], 1.0)]
            else:
                print(f"Case number {case_number} not found.")
                return []

        # Text query mode - use BM25
        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            print("Empty query after tokenization.")
            return []

        scores = self.bm25.get_scores(tokenized_query)

        # Get top k results
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            if score > 0:
                results.append((self.cases[idx], score))

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Medical Case BM25 Search Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by text query (returns top 5 by default)
  python med_search.py "chest pain dyspnea"

  # Search with custom top_k
  python med_search.py "brain tumor" --top_k 10

  # Search by case number
  python med_search.py "1000"
  python med_search.py "case 1000"
  python med_search.py "case number 1000"
        """
    )
    parser.add_argument("query", help="Search query (text or case number)")
    parser.add_argument(
        "--top_k", "-k",
        type=int,
        default=5,
        help="Number of top results to return for text queries (default: 5)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=str(Path(__file__).parent / "deepsearch列表信息.csv"),
        help="Path to the CSV data file"
    )

    args = parser.parse_args()

    # Initialize search engine
    engine = MedSearchEngine(args.csv)

    # Perform search
    print(f"\nSearching for: '{args.query}'")
    print("-" * 40)

    results = engine.search(args.query, top_k=args.top_k)

    if not results:
        print("No results found.")
        sys.exit(0)

    # Check if it's a case number search (single result with score 1.0)
    is_case_number_search = len(results) == 1 and results[0][1] == 1.0 and engine._is_case_number_query(args.query) is not None

    if is_case_number_search:
        # Case number mode: show everything
        case, _ = results[0]
        print(f"\nFound exact match for case number:")
        print(case.display())
    else:
        # Text query mode: show top k results with scores
        print(f"\nTop {len(results)} results:\n")
        for rank, (case, score) in enumerate(results, 1):
            print(f"{'='*80}")
            print(f"RANK {rank} | SCORE: {score:.4f}")
            print(case.display())


if __name__ == "__main__":
    main()
