#!/usr/bin/env python3
"""
Run diagnosis-relevant case search for multiple cases from CSV.

This script:
1. Reads clinical cases from medd_selected_50.csv
2. For each case, spawns an agent with med-diagnosis-relevant-search skill
3. Each agent uses parallel sub-agents to find diagnosis-relevant cases
4. Results are incrementally saved to a CSV file

Usage:
    # Process first 2 cases (default)
    python run_diagnosis_relevant_search.py

    # Process first N cases
    python run_diagnosis_relevant_search.py --num-cases 5

    # Process specific cases by index
    python run_diagnosis_relevant_search.py --case-indices 0 5 10

    # Custom input/output files
    python run_diagnosis_relevant_search.py \
        --input-csv /path/to/cases.csv \
        --output-csv results/custom_output.csv \
        --num-cases 10
"""

import sys
import csv
import json
import fcntl
import argparse
import time
from pathlib import Path
from datetime import datetime

# Add project root to path (src/)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # src/
sys.path.insert(0, str(PROJECT_ROOT))

from agent_v2.agent import Agent

# Default paths
REPO_ROOT = PROJECT_ROOT.parent
AGENT_V2_DIR = PROJECT_ROOT / "agent_v2"
DEFAULT_INPUT_CSV = REPO_ROOT / "medd_selected_50.csv"
DEFAULT_OUTPUT_CSV = AGENT_V2_DIR / "results" / "med-diagnosis-relevant-search.csv"
DEFAULT_SESSION_DIR = AGENT_V2_DIR / "sessions"
DEFAULT_SKILLS_DIR = AGENT_V2_DIR / "skills"
DEFAULT_CONFIG_PATH = AGENT_V2_DIR / "agent_config.yaml"


def load_cases_from_csv(csv_path: Path, start_index: int = 0, num_cases: int = 2):
    """Load clinical cases from CSV file.

    Args:
        csv_path: Path to CSV file
        start_index: Starting row index (0-based)
        num_cases: Number of cases to process starting from start_index

    Returns:
        List of (global_index, case_dict) tuples
    """
    all_cases = []

    # Try different encodings in order
    encodings = ['utf-8', 'iso-8859-1', 'cp1252', 'latin-1']

    for encoding in encodings:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                all_cases = list(reader)
            print(f"Successfully loaded CSV with {encoding} encoding ({len(all_cases)} total cases)")
            break
        except (UnicodeDecodeError, UnicodeError):
            if encoding == encodings[-1]:
                raise
            continue

    # Slice from start_index for num_cases
    end_index = min(start_index + num_cases, len(all_cases))
    if start_index >= len(all_cases):
        print(f"Warning: start_index {start_index} >= total cases {len(all_cases)}")
        return []

    selected = [(i, all_cases[i]) for i in range(start_index, end_index)]
    print(f"Selected cases: index {start_index} to {end_index - 1} ({len(selected)} cases)")
    return selected


def format_case_for_agent(case: dict) -> str:
    """Format a case dictionary into a prompt for the agent.

    Args:
        case: Dictionary with case data from CSV

    Returns:
        Formatted string describing the case
    """
    case_title = case.get('case_title', 'Unknown Case')
    clinical_history = case.get('clinical_history', 'N/A')
    imaging_findings = case.get('imaging_findings', 'N/A')
    differential_diagnosis = case.get('differential_diagnosis', 'N/A')
    correct_answer = case.get('correct_answer', 'N/A')
    correct_answer_text = case.get('correct_answer_text', 'N/A')

    prompt = f"""Find cases relevant to making this diagnosis.

CASE: {case_title}

CLINICAL HISTORY:
{clinical_history}

IMAGING FINDINGS:
{imaging_findings}

DIFFERENTIAL DIAGNOSIS OPTIONS:
{differential_diagnosis}

CORRECT DIAGNOSIS: {correct_answer_text} (Option {correct_answer})

YOUR TASK:
You know the CORRECT DIAGNOSIS. Find cases with imaging evidence that would help MAKE this diagnosis.
You are a VISION agent — when you navigate to a case, its medical images are automatically shown to you.

WORKFLOW:
1. Query the database 2-3 times with different keyword strategies
2. Navigate to the most promising cases (at most 10 total navigations)
3. For each navigated case, EXAMINE THE IMAGES and note specific imaging features
4. MUST call submit_results.py with case IDs and WHY they're relevant (citing imaging features)

Focus on cases showing:
- Key imaging features that define {correct_answer_text}
- Imaging patterns that distinguish this from other differential diagnoses
- Clinical presentations + imaging that confirm this diagnosis
"""

    return prompt


def save_result_to_csv(case: dict, relevant_cases: dict, output_csv: Path):
    """Save result to CSV incrementally.

    Args:
        case: Original case dictionary
        relevant_cases: Dict of {case_id: reason}
        output_csv: Path to output CSV file
    """
    # Ensure output directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # Format relevant cases as semicolon-separated list
    relevant_cases_str = ";".join([f"{cid}:{reason}" for cid, reason in relevant_cases.items()])

    row = {
        "case_title": case.get('case_title', 'Unknown'),
        "relevant_cases": relevant_cases_str,
        "num_cases_found": len(relevant_cases),
        "timestamp": datetime.now().isoformat()
    }

    # Append to CSV with file locking
    file_exists = output_csv.exists()

    with open(output_csv, 'a', newline='') as f:
        # Acquire exclusive lock
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            f.flush()  # Ensure data is written immediately
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def run_agent_for_case(case: dict, case_index: int, output_csv: Path, session_dir: Path):
    """Run an agent to find diagnosis-relevant cases for a single clinical case.

    Args:
        case: Case dictionary
        case_index: Index of this case
        output_csv: Path to output CSV
        session_dir: Directory for agent sessions

    Returns:
        Dict with results
    """
    case_title = case.get('case_title', f'Case {case_index}')

    print(f"\n{'='*80}")
    print(f"Processing Case {case_index + 1}: {case_title}")
    print(f"{'='*80}\n")

    # Create session ID for this agent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"diagsearch_{timestamp}_{case_index}"

    # Format case as prompt
    prompt = format_case_for_agent(case)

    try:
        # Create agent with vision model (gpt-5-mini) for image analysis
        agent = Agent(
            session_id=session_id,
            session_dir=session_dir,
            skills=["med-diagnosis-relevant-search"],
            skills_dir=DEFAULT_SKILLS_DIR,
            model_type="vision",
            config_path=DEFAULT_CONFIG_PATH,
            max_turns=20,
            temperature=1,
            agent_name=f"diagsearch-agent-{case_index}"
        )

        # Run the agent
        start_time = time.time()
        result = agent.run(prompt)
        elapsed_time = time.time() - start_time

        # Extract final result from trajectory
        final_result_data = None
        print(f"\n[DEBUG] Checking trajectory for final_result_data...")
        print(f"[DEBUG] Has trajectory: {hasattr(agent, 'trajectory')}")

        if hasattr(agent, 'trajectory'):
            print(f"[DEBUG] Trajectory keys: {agent.trajectory.keys()}")
            print(f"[DEBUG] Termination reason: {agent.trajectory.get('termination_reason')}")
            final_result_data = agent.trajectory.get('final_result_data')
            print(f"[DEBUG] final_result_data: {final_result_data}")

        if final_result_data and 'relevant_cases' in final_result_data:
            # Save to CSV
            relevant_cases = final_result_data['relevant_cases']
            save_result_to_csv(case, relevant_cases, output_csv)
            print(f"\n✓ Saved {len(relevant_cases)} relevant cases to CSV: {output_csv}")
        else:
            print(f"\n⚠ WARNING: No final result data found!")
            print(f"[DEBUG] Agent probably hit max_turns or didn't call submit_results.py")
            if hasattr(agent, 'trajectory'):
                print(f"[DEBUG] Total turns used: {agent.trajectory.get('total_turns')}")
                print(f"[DEBUG] Last few turns (check if submit was called):")
                turns = agent.trajectory.get('turns', [])
                for turn in turns[-3:]:
                    tool_calls = [tc.get('name') for tc in turn.get('tool_calls', [])]
                    print(f"  Turn {turn.get('turn')}: {tool_calls}")

        print(f"\n{'='*80}")
        print(f"Completed Case {case_index + 1} in {elapsed_time:.1f}s")
        print(f"{'='*80}\n")

        return {
            "case_index": case_index,
            "case_title": case_title,
            "status": "success",
            "result": result,
            "relevant_cases": final_result_data.get('relevant_cases', {}) if final_result_data else {},
            "elapsed_time": elapsed_time,
            "session_id": session_id
        }

    except Exception as e:
        print(f"\nError processing case {case_index + 1}: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return {
            "case_index": case_index,
            "case_title": case_title,
            "status": "error",
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run diagnosis-relevant case search for multiple clinical cases"
    )
    parser.add_argument(
        '--input-csv',
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help=f'Input CSV file with cases (default: {DEFAULT_INPUT_CSV})'
    )
    parser.add_argument(
        '--output-csv',
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f'Output CSV file for results (default: {DEFAULT_OUTPUT_CSV})'
    )
    parser.add_argument(
        '--start-index',
        type=int,
        default=0,
        help='Starting case index in the CSV, 0-based (default: 0)'
    )
    parser.add_argument(
        '--num-cases',
        type=int,
        default=2,
        help='Number of cases to process from start-index (default: 2)'
    )
    parser.add_argument(
        '--session-dir',
        type=Path,
        default=DEFAULT_SESSION_DIR,
        help=f'Directory for agent sessions (default: {DEFAULT_SESSION_DIR})'
    )

    args = parser.parse_args()

    # Validate input file exists
    if not args.input_csv.exists():
        print(f"Error: Input CSV file not found: {args.input_csv}")
        sys.exit(1)

    # Create output directory
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    # Create session directory
    args.session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print("DIAGNOSIS-RELEVANT CASE SEARCH - BATCH RUN")
    print(f"{'='*80}")
    print(f"Input CSV: {args.input_csv}")
    print(f"Output CSV: {args.output_csv}")
    print(f"Session Directory: {args.session_dir}")

    # Load cases
    indexed_cases = load_cases_from_csv(
        args.input_csv,
        start_index=args.start_index,
        num_cases=args.num_cases,
    )

    print(f"Cases to process: {len(indexed_cases)}")
    print(f"{'='*80}\n")

    # Process each case
    results = []
    for global_idx, case in indexed_cases:
        result = run_agent_for_case(
            case=case,
            case_index=global_idx,
            output_csv=args.output_csv,
            session_dir=args.session_dir
        )
        results.append(result)

        # Brief pause between cases
        if len(results) < len(indexed_cases):
            print("\nPausing 2 seconds before next case...\n")
            time.sleep(2)

    # Print summary
    print(f"\n{'='*80}")
    print("BATCH RUN COMPLETE")
    print(f"{'='*80}")
    print(f"Total cases processed: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'error')}")
    print(f"\nResults saved to: {args.output_csv}")
    print(f"Sessions saved to: {args.session_dir}")
    print(f"{'='*80}\n")

    # Print individual results
    for result in results:
        status_symbol = "✓" if result['status'] == 'success' else "✗"
        print(f"{status_symbol} Case {result['case_index'] + 1}: {result['case_title']}")
        if result['status'] == 'success':
            print(f"  Time: {result['elapsed_time']:.1f}s, Session: {result['session_id']}")
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
