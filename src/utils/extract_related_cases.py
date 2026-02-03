#!/usr/bin/env python3
"""
Script to extract related cases from medical case datasets.

This script reads cases from medd_selected_50.csv, finds their related cases,
and creates a new CSV with IDs from selected_50 and relevant cases from
deepsearch_complete.csv, ensuring related cases don't contain the source ID.
"""

import csv
import re
from pathlib import Path


def extract_case_id(case_title):
    """
    Extract numeric case ID from case title (e.g., 'Case number 19172' -> '19172')
    """
    match = re.search(r'Case number (\d+)', str(case_title))
    if match:
        return match.group(1)
    return None


def read_csv_to_dict(filepath, key_column='case_title'):
    """
    Read a CSV file and return a list of dictionaries.
    Try different encodings if utf-8 fails.
    """
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-8-sig']
    data = []

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            print(f"  Successfully read file using {encoding} encoding")
            return data
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            print(f"  Error reading file with {encoding}: {e}")
            continue

    raise ValueError(f"Could not read {filepath} with any of the attempted encodings: {encodings}")


def main():
    # Define file paths
    base_dir = Path('/Users/xiaofanlu/Documents/github_repos/med_deepresearch')
    selected_50_path = base_dir / 'medd_selected_50.csv'
    deepsearch_complete_path = base_dir / 'deepsearch_complete.csv'
    output_path = base_dir / 'src' / 'related_cases_output.csv'

    print("Loading selected_50.csv...")
    selected_cases = read_csv_to_dict(selected_50_path)
    print(f"Loaded {len(selected_cases)} cases from selected_50.csv")

    print("Loading deepsearch_complete.csv...")
    complete_cases = read_csv_to_dict(deepsearch_complete_path)
    print(f"Loaded {len(complete_cases)} cases from deepsearch_complete.csv")

    # Create a set of case IDs from selected_50 for filtering
    selected_case_ids = set()
    for row in selected_cases:
        case_id = extract_case_id(row['case_title'])
        if case_id:
            selected_case_ids.add(case_id)

    print(f"Found {len(selected_case_ids)} case IDs in selected_50.csv")

    # Create a dictionary for quick lookup of cases in deepsearch_complete
    # Key: case_id, Value: row data
    complete_cases_dict = {}
    for row in complete_cases:
        case_id = extract_case_id(row['case_title'])
        if case_id:
            complete_cases_dict[case_id] = row

    print(f"Indexed {len(complete_cases_dict)} cases in deepsearch_complete.csv")

    # Process each case in selected_50
    results = []
    processed_count = 0
    filtered_count = 0

    for selected_row in selected_cases:
        source_case_id = extract_case_id(selected_row['case_title'])
        if not source_case_id:
            print(f"Warning: Could not extract case ID from '{selected_row['case_title']}'")
            continue

        processed_count += 1
        print(f"Processing case {source_case_id}...")

        # Get related cases
        relate_case_str = selected_row.get('relate_case', '')
        if not relate_case_str or relate_case_str.strip() == '':
            print(f"  No related cases found for {source_case_id}")
            continue

        # Split by semicolon to get individual case IDs
        related_case_ids = [cid.strip() for cid in str(relate_case_str).split(';')]

        # Filter out the source case ID and find matching cases in deepsearch_complete
        for related_id in related_case_ids:
            # Skip if the related case is the same as the source case
            if related_id == source_case_id:
                continue

            # Skip if the related case is in selected_50.csv
            if related_id in selected_case_ids:
                print(f"  Skipping related case {related_id} (exists in selected_50)")
                filtered_count += 1
                continue

            # Check if this related case exists in deepsearch_complete
            if related_id in complete_cases_dict:
                related_case_data = complete_cases_dict[related_id]

                # Create a result entry
                result_entry = {
                    'source_case_id': source_case_id,
                    'source_case_title': selected_row['case_title'],
                    'related_case_id': related_id,
                    'related_case_title': related_case_data['case_title'],
                    'related_case_link': related_case_data.get('link', ''),
                    'related_case_diagnosis': related_case_data.get('final_diagnosis', ''),
                    'related_case_categories': related_case_data.get('Categories', ''),
                }
                results.append(result_entry)
                print(f"  Found related case: {related_id}")
            else:
                print(f"  Warning: Related case {related_id} not found in deepsearch_complete.csv")

    # Save to CSV
    print(f"\nCreating output CSV with {len(results)} related case entries...")

    if results:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['source_case_id', 'source_case_title', 'related_case_id',
                         'related_case_title', 'related_case_link', 'related_case_diagnosis',
                         'related_case_categories']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"Output saved to: {output_path}")
    else:
        print("No results to save!")

    # Print summary statistics
    print("\n=== Summary ===")
    print(f"Total selected cases processed: {processed_count}")
    print(f"Related cases filtered out (exist in selected_50): {filtered_count}")
    print(f"Total related case entries: {len(results)}")
    if results:
        unique_source_cases = len(set(r['source_case_id'] for r in results))
        print(f"Unique source cases with related cases: {unique_source_cases}")
        avg_related = len(results) / unique_source_cases if unique_source_cases > 0 else 0
        print(f"Average related cases per source case: {avg_related:.2f}")


if __name__ == '__main__':
    main()
