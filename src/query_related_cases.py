#!/usr/bin/env python3
"""
Script to query related cases for a given case ID.

Usage:
    python query_related_cases.py <case_id> [--k <number_of_cases>]

Example:
    python query_related_cases.py 17930 --k 10
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


def extract_case_id(case_title):
    """Extract numeric case ID from case title."""
    match = re.search(r'Case number (\d+)', str(case_title))
    if match:
        return match.group(1)
    return None


def read_csv_to_dict(filepath):
    """Read a CSV file and return a list of dictionaries."""
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-8-sig']
    data = []

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            return data
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            continue

    raise ValueError(f"Could not read {filepath} with any encoding")


def format_case_details(case_data: Dict, case_number: int) -> str:
    """Format a single case's details as readable text."""
    case_id = extract_case_id(case_data['case_title'])

    output = f"\n{'='*80}\n"
    output += f"RELATED CASE #{case_number}\n"
    output += f"{'='*80}\n\n"

    output += f"Case ID: {case_id}\n"
    output += f"Case Title: {case_data.get('case_title', 'N/A')}\n"
    output += f"Date: {case_data.get('case_date', 'N/A')}\n"
    output += f"Link: {case_data.get('link', 'N/A')}\n\n"

    output += f"Final Diagnosis:\n{'-'*80}\n"
    output += f"{case_data.get('final_diagnosis', 'N/A')}\n\n"

    output += f"Categories:\n{'-'*80}\n"
    output += f"{case_data.get('Categories', 'N/A')}\n\n"

    output += f"Clinical History:\n{'-'*80}\n"
    clinical = case_data.get('clinical_history', 'N/A')
    output += f"{clinical[:500]}{'...' if len(clinical) > 500 else ''}\n\n"

    output += f"Imaging Findings:\n{'-'*80}\n"
    imaging = case_data.get('imaging_findings', 'N/A')
    output += f"{imaging[:500]}{'...' if len(imaging) > 500 else ''}\n\n"

    output += f"Differential Diagnosis:\n{'-'*80}\n"
    output += f"{case_data.get('differential_diagnosis', 'N/A')}\n\n"

    return output


def get_related_cases(case_id: str, k: int = 10) -> str:
    """
    Get k related cases for a given case ID.

    Args:
        case_id: The case ID to query (e.g., "17930")
        k: Number of related cases to return (default: 10)

    Returns:
        Formatted text with case details
    """
    # Define file paths
    base_dir = Path('/Users/xiaofanlu/Documents/github_repos/med_deepresearch')
    selected_50_path = base_dir / 'medd_selected_50.csv'
    deepsearch_complete_path = base_dir / 'deepsearch_complete.csv'

    # Load data
    print(f"Loading data...", file=sys.stderr)
    selected_cases = read_csv_to_dict(selected_50_path)
    complete_cases = read_csv_to_dict(deepsearch_complete_path)

    # Create sets for quick lookup
    selected_case_ids = {extract_case_id(row['case_title']) for row in selected_cases}

    # Index complete cases by ID
    complete_cases_dict = {}
    for row in complete_cases:
        cid = extract_case_id(row['case_title'])
        if cid:
            complete_cases_dict[cid] = row

    # Find the source case
    source_case = None
    for row in selected_cases:
        if extract_case_id(row['case_title']) == case_id:
            source_case = row
            break

    if not source_case:
        return f"Error: Case ID {case_id} not found in selected_50.csv"

    # Get related cases
    relate_case_str = source_case.get('relate_case', '')
    if not relate_case_str or relate_case_str.strip() == '':
        return f"No related cases found for case ID {case_id}"

    # Split and filter related case IDs
    related_case_ids = [cid.strip() for cid in str(relate_case_str).split(';')]

    # Filter out:
    # 1. The source case itself
    # 2. Cases that are in selected_50
    # 3. Cases not in deepsearch_complete
    valid_related_ids = []
    for related_id in related_case_ids:
        if related_id == case_id:
            continue  # Skip source case
        if related_id in selected_case_ids:
            continue  # Skip cases in selected_50
        if related_id not in complete_cases_dict:
            continue  # Skip cases not in complete dataset
        valid_related_ids.append(related_id)

    # Limit to k cases
    valid_related_ids = valid_related_ids[:k]

    if not valid_related_ids:
        return f"No valid related cases found for case ID {case_id} (after filtering)"

    # Format output
    output = f"\n{'#'*80}\n"
    output += f"QUERY RESULTS FOR CASE ID: {case_id}\n"
    output += f"{'#'*80}\n"
    output += f"\nSource Case: {source_case.get('case_title', 'N/A')}\n"
    output += f"Total related cases found: {len(valid_related_ids)} (limited to k={k})\n"

    for i, related_id in enumerate(valid_related_ids, 1):
        case_data = complete_cases_dict[related_id]
        output += format_case_details(case_data, i)

    return output


def main():
    """Main function to handle command-line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python query_related_cases.py <case_id> [--k <number>]")
        print("Example: python query_related_cases.py 17930 --k 10")
        sys.exit(1)

    case_id = sys.argv[1]
    k = 10  # Default value

    # Parse optional --k parameter
    if '--k' in sys.argv:
        try:
            k_index = sys.argv.index('--k')
            k = int(sys.argv[k_index + 1])
        except (IndexError, ValueError):
            print("Error: Invalid value for --k parameter")
            sys.exit(1)

    result = get_related_cases(case_id, k)
    print(result)


if __name__ == '__main__':
    main()
