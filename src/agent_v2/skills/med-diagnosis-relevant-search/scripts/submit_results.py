#!/usr/bin/env python3
"""
Submit diagnosis-relevant case search results.

Outputs structured JSON with relevant case IDs and reasoning.
Uses Final Result Protocol for proper termination.
"""

import json
import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="Submit diagnosis-relevant case search results"
    )
    parser.add_argument(
        '--relevant-cases',
        type=str,
        required=True,
        help='JSON string with relevant cases: {"case_id": "reason", ...}'
    )

    args = parser.parse_args()

    # Parse the relevant cases JSON
    try:
        relevant_cases = json.loads(args.relevant_cases)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}")
        exit(1)

    # Validate it's a dict
    if not isinstance(relevant_cases, dict):
        print("Error: relevant-cases must be a JSON object/dict, not array or primitive")
        exit(1)

    # Build the final result
    final_result = {
        "relevant_cases": relevant_cases,
        "num_cases_found": len(relevant_cases),
        "timestamp": datetime.now().isoformat()
    }

    # Output using Final Result Protocol
    print("<<<FINAL_RESULT>>>")
    print(json.dumps(final_result, indent=2))
    print("<<<END_FINAL_RESULT>>>")


if __name__ == "__main__":
    main()
