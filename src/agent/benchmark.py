"""Benchmark script for medical diagnosis agent."""
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime

from single_agent import SingleAgent


def load_benchmark_cases(csv_path: str, limit: int = None) -> list[dict]:
    """Load cases from the benchmark CSV file."""
    cases = []
    # Try different encodings
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


def format_case_prompt(case: dict) -> str:
    """Format a case into a prompt for the agent."""
    # Parse options from JSON string
    try:
        options = json.loads(case['options'].replace("'", '"'))
    except json.JSONDecodeError:
        options = eval(case['options'])  # Fallback for Python dict format

    options_text = "\n".join([f"{k}. {v}" for k, v in sorted(options.items())])

    prompt = f"""## Clinical Case: {case['case_title']}

### Clinical History
{case['clinical_history']}


### Question
Based on the clinical history and imaging findings above, what is the most likely diagnosis?

### Options
{options_text}

Please analyze this case and select the correct answer (A, B, C, D, or E).
"""
    return prompt


def run_benchmark(csv_path: str, limit: int = 10, model: str = None, agent_name: str = "med_simple_agent") -> dict:
    """Run the benchmark on cases."""
    print(f"\n{'='*60}")
    print(f"MEDICAL DIAGNOSIS BENCHMARK")
    print(f"{'='*60}")

    cases = load_benchmark_cases(csv_path, limit=limit)
    print(f"Loaded {len(cases)} cases")
    print(f"Using agent: {agent_name}")

    agent = SingleAgent(agent_name, model_name=model)

    results = []
    correct = 0
    total = 0

    for i, case in enumerate(cases):
        print(f"\n{'='*60}")
        print(f"CASE {i+1}/{len(cases)}: {case['case_title']}")
        print(f"{'='*60}")

        prompt = format_case_prompt(case)
        gt_letter = case['gt_letter'].strip().upper()

        # Run the agent
        result = agent.run(prompt, episode_id=f"benchmark_{i+1}")

        # Extract the answer
        agent_answer = None
        agent_reasoning = None

        if isinstance(result.get('result'), str):
            try:
                answer_data = json.loads(result['result'])
                agent_answer = answer_data.get('answer', '').strip().upper()
                agent_reasoning = answer_data.get('reasoning', '')
            except json.JSONDecodeError:
                # Try to extract answer from raw text
                raw = result['result']
                for letter in ['A', 'B', 'C', 'D', 'E']:
                    if f"answer\": \"{letter}" in raw or f"Answer: {letter}" in raw:
                        agent_answer = letter
                        break

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
            'turns': result.get('turns', 0),
            'tokens': result.get('total_tokens', {})
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
    output_path = Path(__file__).parent / "benchmark_results" / f"benchmark_results_{timestamp}.json"
    with open(output_path, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'total_cases': total,
            'correct': correct,
            'accuracy': correct / total if total > 0 else 0,
            'results': results
        }, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    return {
        'total': total,
        'correct': correct,
        'accuracy': correct / total if total > 0 else 0,
        'results': results
    }


def main():
    parser = argparse.ArgumentParser(description="Run medical diagnosis benchmark")
    parser.add_argument(
        "--csv",
        default=str(Path(__file__).parent.parent.parent / "medd_selected_50.csv"),
        help="Path to benchmark CSV file"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=5,
        help="Number of cases to run (default: 10)"
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Override model from config"
    )
    parser.add_argument(
        "--agent", "-a",
        default="med_simple_agent",
        help="Agent to use (default: med_simple_agent). Use 'med_research_agent' for full research agent."
    )
    args = parser.parse_args()

    run_benchmark(args.csv, limit=args.limit, model=args.model, agent_name=args.agent)


if __name__ == "__main__":
    main()
