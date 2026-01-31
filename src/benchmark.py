#!/usr/bin/env python3
"""Benchmark script for medical diagnosis using agent_v2.

Usage:
    # From project root
    uv run python src/benchmark.py

    # Customize
    uv run python src/benchmark.py --limit 10 --model deepseek-chat

    # Use specific CSV
    uv run python src/benchmark.py --csv path/to/cases.csv --limit 5
"""
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# Get paths relative to this file
SRC_DIR = Path(__file__).parent
PROJECT_ROOT = SRC_DIR.parent

# Add src to path for imports
import sys
sys.path.insert(0, str(SRC_DIR))

from agent_v2.agent import Agent


def load_benchmark_cases(csv_path: str, limit: int = None) -> List[Dict[str, Any]]:
    """Load cases from the benchmark CSV file."""
    cases = []
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(csv_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break
                    cases.append(row)
            break
        except UnicodeDecodeError:
            cases = []
            continue
    return cases


def format_case_prompt(case: Dict[str, Any]) -> str:
    """Format a case into a prompt for the agent."""
    try:
        options = json.loads(case['options'].replace("'", '"'))
    except json.JSONDecodeError:
        options = eval(case['options'])

    options_text = "\n".join([f"{k}. {v}" for k, v in sorted(options.items())])

    prompt = f"""## Clinical Case: {case['case_title']}

### Clinical History
{case['clinical_history']}


### Question
Based on the clinical history and imaging findings above, what is the most likely diagnosis?

### Options
{options_text}

Please analyze this case and select the correct answer (A, B, C, D, or E).
Use the research_tools.py script to plan your research, query the database, and submit your answer.
"""
    return prompt


def extract_answer(result: str) -> Tuple[Optional[str], str]:
    """Extract answer letter and reasoning from agent result."""
    answer = None
    reasoning = ""

    try:
        data = json.loads(result)
        answer = data.get('answer', '').strip().upper()
        reasoning = data.get('reasoning', '')
        return answer, reasoning
    except json.JSONDecodeError:
        pass

    for letter in ['A', 'B', 'C', 'D', 'E']:
        if f'"answer": "{letter}"' in result or f'Answer: {letter}' in result:
            answer = letter
            break

    return answer, reasoning


def run_benchmark(
    csv_path: str = None,
    limit: int = 5,
    model: str = None,
    skills_dir: str = None,
    output_dir: str = None
) -> Dict[str, Any]:
    """Run the benchmark on cases.

    Args:
        csv_path: Path to benchmark CSV file (default: PROJECT_ROOT/medd_selected_50.csv)
        limit: Number of cases to run
        model: Model to use
        skills_dir: Path to skills directory (default: src/agent_v2/skills)
        output_dir: Directory to save results (default: src/agent_v2/benchmark_results)

    Returns:
        Dictionary with benchmark results
    """
    # Defaults
    if csv_path is None:
        csv_path = str(PROJECT_ROOT / "medd_selected_50.csv")
    if skills_dir is None:
        skills_dir = str(SRC_DIR / "agent_v2" / "skills")
    if output_dir is None:
        output_dir = str(SRC_DIR / "agent_v2" / "benchmark_results")

    skills_path = Path(skills_dir)
    results_dir = Path(output_dir)
    results_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"MEDICAL DIAGNOSIS BENCHMARK (agent_v2)")
    print(f"{'='*60}")

    cases = load_benchmark_cases(csv_path, limit=limit)
    print(f"Loaded {len(cases)} cases from {csv_path}")
    print(f"Model: {model or 'default (deepseek-chat)'}")
    print(f"Skills dir: {skills_path}")

    results = []
    correct = 0
    total = 0

    for i, case in enumerate(cases):
        print(f"\n{'='*60}")
        print(f"CASE {i+1}/{len(cases)}: {case['case_title']}")
        print(f"{'='*60}")

        prompt = format_case_prompt(case)
        gt_letter = case['gt_letter'].strip().upper()

        # Create fresh agent for each case
        agent = Agent(
            skills=["med-deepresearch"],
            skills_dir=skills_path,
            model=model,
            max_turns=15,
            temperature=0.3
        )

        result = agent.run(prompt, run_id=f"benchmark_{i+1}")
        agent_answer, agent_reasoning = extract_answer(result)

        is_correct = agent_answer == gt_letter
        if is_correct:
            correct += 1
        total += 1

        case_result = {
            'case_number': i + 1,
            'case_title': case['case_title'],
            'ground_truth': gt_letter,
            'agent_answer': agent_answer,
            'correct': is_correct,
            'reasoning': agent_reasoning,
            'session_id': agent.session_id,
            'tokens': agent.session.history[-1].get('tokens', {}) if agent.session.history else {}
        }
        results.append(case_result)

        status = "✓ CORRECT" if is_correct else "✗ INCORRECT"
        print(f"\n{status}")
        print(f"Ground Truth: {gt_letter} | Agent: {agent_answer}")
        print(f"Running Accuracy: {correct}/{total} ({100*correct/total:.1f}%)")

    # Summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"Total Cases: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {100*correct/total:.1f}%")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = results_dir / f"benchmark_results_{timestamp}.json"

    benchmark_data = {
        'timestamp': timestamp,
        'model': model,
        'csv_path': csv_path,
        'total_cases': total,
        'correct': correct,
        'accuracy': correct / total if total > 0 else 0,
        'results': results
    }

    with open(output_path, 'w') as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    return benchmark_data


def main():
    parser = argparse.ArgumentParser(
        description="Run medical diagnosis benchmark with agent_v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python src/benchmark.py
  uv run python src/benchmark.py --limit 10 --model deepseek-chat
  uv run python src/benchmark.py --csv ./data/cases.csv
        """
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to benchmark CSV (default: medd_selected_50.csv)"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=5,
        help="Number of cases (default: 5)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model to use (default: deepseek-chat)"
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Skills directory"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Results directory"
    )
    args = parser.parse_args()

    run_benchmark(
        csv_path=args.csv,
        limit=args.limit,
        model=args.model,
        skills_dir=args.skills_dir,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
