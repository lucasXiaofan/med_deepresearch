#!/usr/bin/env python3
"""Few-shot testing script for medical diagnosis using vision agent.

Tests the agent's diagnostic accuracy with two modes:
1. Baseline: No relevant case context (agent sees only clinical history + options + images)
2. Few-shot: With relevant case full text as reference context

This script can test different vision models via:
- --model-type: model profile in src/agent_v2/agent_config.yaml
- --model: direct model override (OpenRouter model id)

Relevant cases default to:
src/agent_v2/results/med-diagnosis-relevant-search.csv

Usage:
    # Run both modes on all cases with default vision model profile
    uv run python src/agent_v2/agent_runner/fewshot_testing.py

    # Explicitly test GPT-5-mini on baseline relevant-cases CSV
    uv run python src/agent_v2/agent_runner/fewshot_testing.py \
      --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv \
      --model openai/gpt-5-mini --model-type vision

    # Test Grok 4.1 Fast
    uv run python src/agent_v2/agent_runner/fewshot_testing.py \
      --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv \
      --model x-ai/grok-4.1-fast --model-type vision

    # Test Gemini 3 Flash Preview
    uv run python src/agent_v2/agent_runner/fewshot_testing.py \
      --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv \
      --model google/gemini-3-flash-preview --model-type vision

    # Use config profile directly (no --model override)
    uv run python src/agent_v2/agent_runner/fewshot_testing.py --model-type vision_grok
    uv run python src/agent_v2/agent_runner/fewshot_testing.py --model-type vision_gemini

    # Limit to N cases
    uv run python src/agent_v2/agent_runner/fewshot_testing.py --limit 3

    # Run only baseline or only fewshot
    uv run python src/agent_v2/agent_runner/fewshot_testing.py --mode baseline
    uv run python src/agent_v2/agent_runner/fewshot_testing.py --mode fewshot
"""

import sys
import csv
import json
import re
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# Paths
SRC_DIR = Path(__file__).parent.parent.parent  # src/
PROJECT_ROOT = SRC_DIR.parent
AGENT_V2_DIR = SRC_DIR / "agent_v2"

sys.path.insert(0, str(SRC_DIR))

from agent_v2.agent import Agent
from med_search import MedSearchEngine

# Default paths
DEFAULT_CASES_CSV = PROJECT_ROOT / "medd_selected_50.csv"
DEFAULT_RELEVANT_CSV = AGENT_V2_DIR / "results" / "med-diagnosis-relevant-search.csv"
DEFAULT_DATABASE_CSV = PROJECT_ROOT / "deepsearch_complete.csv"
DEFAULT_SKILLS_DIR = AGENT_V2_DIR / "skills"
DEFAULT_CONFIG_PATH = AGENT_V2_DIR / "agent_config.yaml"
DEFAULT_OUTPUT_DIR = AGENT_V2_DIR / "fewshot_results"
DEFAULT_SESSION_DIR = AGENT_V2_DIR / "sessions"

# Path to research_tools.py (relative to project root, used in bash commands)
RESEARCH_TOOLS_REL = "src/agent_v2/skills/med-deepresearch/scripts/research_tools.py"

SYSTEM_PROMPT_TEMPLATE = """You are a medical diagnosis agent with vision capabilities.
You are given a clinical case with limited information (clinical history and multiple choice options) along with medical images for this case.

Your task: analyze the clinical information and images to select the most likely diagnosis.

{relevant_cases_section}

After your analysis, submit your answer with this bash command:
uv run python {research_tools} submit --answer <LETTER> --reasoning "<your brief reasoning>"

Where <LETTER> is one of A, B, C, D, or E.

Rules:
- Carefully examine the medical images provided
- Consider the clinical history and any reference cases
- Select the single best answer from the options
- You MUST submit your answer before running out of turns"""

RELEVANT_CASES_SECTION = """You are also provided with full clinical information from relevant reference cases below.
Use these to inform your diagnosis by looking for matching imaging patterns, clinical presentations, and diagnostic features.

--- RELEVANT REFERENCE CASES ---
{relevant_text}
--- END REFERENCE CASES ---"""

NO_CONTEXT_SECTION = "No reference cases are provided. Rely on the clinical information and images only."


def extract_case_number(case_title: str) -> Optional[str]:
    """Extract case number from title like 'Case number 19087'."""
    match = re.search(r'Case number (\d+)', case_title)
    return match.group(1) if match else None


def load_relevant_cases_csv(csv_path: Path) -> Dict[str, List[Tuple[str, str]]]:
    """Load relevant cases from the search results CSV.

    Returns:
        Dict: target_case_number -> list of (relevant_case_id, reason).
        Excludes the target case itself.
    """
    result = {}

    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(csv_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    case_title = row.get('case_title', '')
                    target_num = extract_case_number(case_title)
                    if not target_num:
                        continue

                    relevant_str = row.get('relevant_cases', '')
                    if not relevant_str:
                        continue

                    # Parse "case_id:reason;case_id:reason;..." with regex
                    entries = re.findall(r'(\d+):(.+?)(?=;\d+:|$)', relevant_str)

                    relevant_list = []
                    for case_id, reason in entries:
                        if case_id == target_num:
                            continue  # skip the target case itself
                        relevant_list.append((case_id, reason.strip()))

                    if relevant_list:
                        result[target_num] = relevant_list
            break
        except UnicodeDecodeError:
            continue

    return result


def build_relevant_cases_fulltext(
    relevant_map: Dict[str, List[Tuple[str, str]]],
    search_engine: MedSearchEngine
) -> Dict[str, str]:
    """Build full text blocks for all relevant cases using MedSearchEngine.

    For each target case, looks up each relevant case by number in the database
    and formats it using MedCase.display() (same as med_search.py output).

    Returns:
        Dict: target_case_number -> combined full text string of all relevant cases.
    """
    fulltext_dict = {}

    for target_num, relevant_list in relevant_map.items():
        parts = []
        for case_id, reason in relevant_list:
            results = search_engine.search(case_id, top_k=1)
            if results:
                case_obj, _ = results[0]
                case_text = case_obj.display()
                parts.append(
                    f"[Relevant Case {case_id}]\n"
                    f"Reason for relevance: {reason}\n"
                    f"{case_text}"
                )
            else:
                parts.append(
                    f"[Relevant Case {case_id}]\n"
                    f"Reason for relevance: {reason}\n"
                    f"(Case not found in database)"
                )

        fulltext_dict[target_num] = "\n\n".join(parts)

    return fulltext_dict


def load_benchmark_cases(csv_path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
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


def format_limited_prompt(case: Dict[str, Any]) -> str:
    """Format a case with limited info: clinical history and options only."""
    try:
        options = json.loads(case['options'].replace("'", '"'))
    except (json.JSONDecodeError, KeyError):
        try:
            options = eval(case['options'])
        except Exception:
            options = {}

    options_text = "\n".join([f"{k}. {v}" for k, v in sorted(options.items())])

    prompt = f"""## Clinical Case: {case['case_title']}

### Clinical History
{case['clinical_history']}

### Question
Based on the clinical history and imaging findings, what is the most likely diagnosis?

### Options
{options_text}

Please analyze this case and select the correct answer (A, B, C, D, or E)."""
    return prompt


def extract_answer(result: str) -> Tuple[Optional[str], str]:
    """Extract answer letter and reasoning from agent result."""
    answer = None
    reasoning = ""

    # Try JSON parse first
    try:
        data = json.loads(result)
        answer = data.get('answer', '').strip().upper()
        reasoning = data.get('reasoning', '')
        return answer, reasoning
    except (json.JSONDecodeError, AttributeError):
        pass

    # Try to find answer in FINAL_RESULT block
    fr_match = re.search(r'<<<FINAL_RESULT>>>\s*(.*?)\s*<<<END_FINAL_RESULT>>>', result, re.DOTALL)
    if fr_match:
        try:
            data = json.loads(fr_match.group(1))
            answer = data.get('answer', '').strip().upper()
            reasoning = data.get('reasoning', '')
            return answer, reasoning
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: look for answer patterns
    for letter in ['A', 'B', 'C', 'D', 'E']:
        if f'"answer": "{letter}"' in result or f'Answer: {letter}' in result:
            answer = letter
            break

    # Parse command-style output, e.g.:
    # uv run python ... submit --answer E --reasoning "..."
    if answer is None:
        cmd_match = re.search(r'--answer\s+([A-E])\b', result, re.IGNORECASE)
        if cmd_match:
            answer = cmd_match.group(1).upper()

    # Generic textual fallback: "Final answer: B", "Diagnosis: C", etc.
    if answer is None:
        txt_match = re.search(r'\b(?:final answer|diagnosis|answer)\b\s*[:\-]?\s*([A-E])\b', result, re.IGNORECASE)
        if txt_match:
            answer = txt_match.group(1).upper()

    return answer, reasoning


def run_single_case(
    case: Dict[str, Any],
    case_index: int,
    relevant_fulltext: Optional[str],
    relevant_entries: Optional[List[Tuple[str, str]]],
    mode: str,
    model: Optional[str],
    model_type: str,
    config_path: Path,
    skills_dir: Path,
    session_dir: Path,
    retry_no_answer: int = 1,
) -> Dict[str, Any]:
    """Run a single case through the vision agent.

    Args:
        case: Case dict from CSV
        case_index: Index for logging
        relevant_fulltext: Full text of relevant cases (None for baseline)
        mode: "baseline" or "fewshot"
        config_path: Path to agent_config.yaml
        skills_dir: Path to skills directory
        session_dir: Path to session directory

    Returns:
        Dict with result data
    """
    case_title = case.get('case_title', f'Case {case_index}')
    case_number = extract_case_number(case_title)
    gt_letter = case['gt_letter'].strip().upper()

    # Build system prompt
    if relevant_fulltext and mode == "fewshot":
        relevant_section = RELEVANT_CASES_SECTION.format(relevant_text=relevant_fulltext)
    else:
        relevant_section = NO_CONTEXT_SECTION
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        relevant_cases_section=relevant_section,
        research_tools=RESEARCH_TOOLS_REL
    )

    # Format user prompt with limited info
    user_prompt = format_limited_prompt(case)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"fewshot_{mode}_{timestamp}_{case_index}"

    try:
        attempt = 0
        max_attempts = max(1, retry_no_answer + 1)
        elapsed_total = 0.0
        final_result_text = ""
        agent_answer: Optional[str] = None
        agent_reasoning = ""
        used_session_id = session_id

        while attempt < max_attempts:
            attempt += 1
            this_session_id = session_id if attempt == 1 else f"{session_id}_retry{attempt-1}"
            used_session_id = this_session_id
            this_system_prompt = system_prompt
            this_max_turns = 2
            this_temperature = 1

            if attempt > 1:
                this_system_prompt = (
                    system_prompt
                    + "\n\nMANDATORY OUTPUT RULE: If tool submission fails, you must end with exactly "
                      "`Final answer: <A-E>` on its own line."
                )
                this_max_turns = 3
                this_temperature = 0.2

            agent = Agent(
                session_id=this_session_id,
                session_dir=session_dir,
                skills=[],  # no skills, custom prompt only
                skills_dir=skills_dir,
                model=model,
                model_type=model_type,
                config_path=config_path,
                max_turns=this_max_turns,
                temperature=this_temperature,
                custom_system_prompt=this_system_prompt,
                agent_name=f"fewshot-{mode}-{case_index}"
            )

            start_time = time.time()
            result = agent.run(user_prompt, case_id=case_number, run_id=f"fewshot_{mode}_{case_index}_a{attempt}")
            elapsed_total += (time.time() - start_time)
            final_result_text = result or ""

            agent_answer, agent_reasoning = extract_answer(final_result_text)
            if agent_answer:
                break

            print(
                f"  [WARN] No answer parsed for case {case_number} ({mode}) "
                f"on attempt {attempt}/{max_attempts}."
            )

        is_correct = agent_answer == gt_letter

        return {
            'case_index': case_index,
            'case_title': case_title,
            'case_number': case_number,
            'ground_truth': gt_letter,
            'agent_answer': agent_answer,
            'correct': is_correct,
            'reasoning': agent_reasoning,
            'mode': mode,
            'relevant_cases_loaded': [
                {'case_id': case_id, 'reason': reason}
                for case_id, reason in (relevant_entries or [])
            ],
            'elapsed_time': round(elapsed_total, 1),
            'session_id': used_session_id,
            'attempts': attempt,
            'raw_output_preview': final_result_text[:500],
        }

    except Exception as e:
        print(f"\nError processing case {case_index + 1}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'case_index': case_index,
            'case_title': case_title,
            'case_number': case_number,
            'ground_truth': gt_letter,
            'agent_answer': None,
            'correct': False,
            'reasoning': f'Error: {str(e)}',
            'mode': mode,
            'relevant_cases_loaded': [
                {'case_id': case_id, 'reason': reason}
                for case_id, reason in (relevant_entries or [])
            ],
            'elapsed_time': 0,
            'session_id': None,
        }


def run_mode(
    cases: List[Dict[str, Any]],
    case_indices: List[int],
    relevant_map: Dict[str, List[Tuple[str, str]]],
    relevant_fulltext_dict: Dict[str, str],
    mode: str,
    model: Optional[str],
    model_type: str,
    config_path: Path,
    skills_dir: Path,
    session_dir: Path,
    workers: int,
    retry_no_answer: int,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Run all cases in a given mode.

    Returns:
        (results_list, correct_count, total_count)
    """
    total_cases = len(case_indices)
    workers = max(1, min(workers, total_cases))

    def _run_idx(idx: int) -> Dict[str, Any]:
        case = cases[idx]
        case_number = extract_case_number(case.get('case_title', ''))
        relevant_text = relevant_fulltext_dict.get(case_number) if mode == "fewshot" else None
        relevant_entries = relevant_map.get(case_number, []) if mode == "fewshot" else []
        return run_single_case(
            case=case,
            case_index=idx,
            relevant_fulltext=relevant_text,
            relevant_entries=relevant_entries,
            mode=mode,
            model=model,
            model_type=model_type,
            config_path=config_path,
            skills_dir=skills_dir,
            session_dir=session_dir,
            retry_no_answer=retry_no_answer,
        )

    # Sequential fallback (workers=1) to preserve existing behavior when desired.
    if workers == 1:
        results = []
        correct = 0
        total = 0
        for idx in case_indices:
            case = cases[idx]
            print(f"\n{'─'*60}")
            print(f"[{mode.upper()}] Case {total+1}/{total_cases}: {case.get('case_title', '')}")
            print(f"{'─'*60}")
            result = _run_idx(idx)
            results.append(result)
            total += 1
            if result['correct']:
                correct += 1
            status = "CORRECT" if result['correct'] else "INCORRECT"
            print(f"  {status} | GT: {result['ground_truth']} | Agent: {result['agent_answer']}")
            print(f"  Running Accuracy: {correct}/{total} ({100*correct/total:.1f}%)")
        return results, correct, total

    print(f"Running {mode} with {workers} workers...")
    results_by_idx: Dict[int, Dict[str, Any]] = {}
    done = 0
    correct = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_idx, idx): idx for idx in case_indices}
        for future in as_completed(futures):
            idx = futures[future]
            result = future.result()
            results_by_idx[idx] = result
            done += 1
            if result['correct']:
                correct += 1

            status = "CORRECT" if result['correct'] else "INCORRECT"
            print(
                f"[{mode.upper()}] {done}/{total_cases} {status} | "
                f"Case {result.get('case_number') or idx} | "
                f"GT: {result['ground_truth']} | Agent: {result['agent_answer']}"
            )

    ordered_results = [results_by_idx[idx] for idx in case_indices]
    return ordered_results, correct, total_cases


def print_summary(all_results: Dict[str, Dict[str, Any]]):
    """Print final summary comparing modes."""
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    for mode_name, data in all_results.items():
        print(f"\n{mode_name.upper()}:")
        print(f"  Total: {data['total']}")
        print(f"  Correct: {data['correct']}")
        print(f"  Accuracy: {100*data['accuracy']:.1f}%")

    # Comparison if both modes ran
    if "baseline" in all_results and "fewshot" in all_results:
        diff = all_results["fewshot"]["accuracy"] - all_results["baseline"]["accuracy"]
        print(f"\nFew-shot improvement: {100*diff:+.1f}%")

        print(f"\nPer-case comparison:")
        print(f"{'Case':<30} {'Baseline':>10} {'Few-shot':>10} {'Change':>8}")
        print(f"{'─'*58}")

        for b, f in zip(all_results["baseline"]["results"], all_results["fewshot"]["results"]):
            b_status = "Correct" if b['correct'] else "Wrong"
            f_status = "Correct" if f['correct'] else "Wrong"
            if b['correct'] != f['correct']:
                change = "+1" if f['correct'] else "-1"
            else:
                change = "="
            title = b['case_title'][:29]
            print(f"{title:<30} {b_status:>10} {f_status:>10} {change:>8}")


def _bool_icon(value: bool) -> str:
    return "Y" if value else "N"


def save_markdown_summary(
    output_path: Path,
    all_results: Dict[str, Dict[str, Any]],
    model: Optional[str],
    model_type: str,
    relevant_csv: Path,
) -> None:
    """Save a markdown summary table for baseline vs few-shot comparison."""
    lines: List[str] = []
    lines.append("# Few-shot Comparison Report")
    lines.append("")
    lines.append(f"- Model type: `{model_type}`")
    lines.append(f"- Model id: `{model or '(from config)'}`")
    lines.append(f"- Relevant CSV: `{relevant_csv}`")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append("| Mode | Correct | Total | Accuracy |")
    lines.append("|---|---:|---:|---:|")
    for mode_name in ["baseline", "fewshot"]:
        if mode_name in all_results:
            data = all_results[mode_name]
            lines.append(
                f"| {mode_name} | {data['correct']} | {data['total']} | {100*data['accuracy']:.1f}% |"
            )
    lines.append("")

    if "baseline" in all_results and "fewshot" in all_results:
        b_map = {r["case_number"]: r for r in all_results["baseline"]["results"]}
        f_map = {r["case_number"]: r for r in all_results["fewshot"]["results"]}
        shared_case_nums = [c for c in b_map.keys() if c in f_map]

        lines.append("## Per-case Comparison")
        lines.append("")
        lines.append("| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |")
        lines.append("|---|---|---|---|---|---|---|")
        for case_num in shared_case_nums:
            b = b_map[case_num]
            f = f_map[case_num]
            if b["correct"] == f["correct"]:
                change = "="
            else:
                change = "+1" if f["correct"] else "-1"
            lines.append(
                f"| {case_num} | {b['ground_truth']} | {b.get('agent_answer') or '-'} | "
                f"{_bool_icon(b['correct'])} | {f.get('agent_answer') or '-'} | "
                f"{_bool_icon(f['correct'])} | {change} |"
            )
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Few-shot testing: medical diagnosis with relevant case context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python src/agent_v2/agent_runner/fewshot_testing.py
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv --model openai/gpt-5-mini --model-type vision
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv --model x-ai/grok-4.1-fast --model-type vision
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --relevant-csv src/agent_v2/results/med-diagnosis-relevant-search.csv --model google/gemini-3-flash-preview --model-type vision
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --model-type vision_grok
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --model-type vision_gemini
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --limit 3
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --mode baseline
  uv run python src/agent_v2/agent_runner/fewshot_testing.py --mode fewshot
        """
    )
    parser.add_argument(
        "--cases-csv", type=Path, default=DEFAULT_CASES_CSV,
        help="Path to benchmark cases CSV"
    )
    parser.add_argument(
        "--relevant-csv", type=Path, default=DEFAULT_RELEVANT_CSV,
        help="Path to relevant search results CSV"
    )
    parser.add_argument(
        "--database-csv", type=Path, default=DEFAULT_DATABASE_CSV,
        help="Path to full case database CSV"
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=None,
        help="Max number of cases to test (default: all with relevant data)"
    )
    parser.add_argument(
        "--mode", choices=["both", "baseline", "fewshot"], default="both",
        help="Run mode: both runs baseline then fewshot (default: both)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override model id (e.g. openai/gpt-5-mini or anthropic/claude-3.5-sonnet)"
    )
    parser.add_argument(
        "--model-type", type=str, default="vision",
        help="Model profile key from agent_config.yaml (default: vision)"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Directory for result JSON files"
    )
    parser.add_argument(
        "--config-path", type=Path, default=DEFAULT_CONFIG_PATH,
        help="Path to agent_config.yaml"
    )
    parser.add_argument(
        "--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR,
        help="Path to skills directory"
    )
    parser.add_argument(
        "--session-dir", type=Path, default=DEFAULT_SESSION_DIR,
        help="Path to session directory"
    )
    parser.add_argument(
        "--workers", type=int, default=5,
        help="Parallel workers per mode (default: 5)"
    )
    parser.add_argument(
        "--retry-no-answer", type=int, default=1,
        help="Retries when no answer can be parsed (default: 1)"
    )

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("FEW-SHOT MEDICAL DIAGNOSIS TESTING")
    print(f"{'='*60}")

    # Step 1: Load relevant cases mapping
    print("\n[1] Loading relevant cases from search results...")
    relevant_map = load_relevant_cases_csv(args.relevant_csv)
    print(f"    Found relevant cases for {len(relevant_map)} target cases")
    for case_num, entries in relevant_map.items():
        print(f"    Case {case_num}: {len(entries)} relevant cases")

    # Step 2: Build full text for relevant cases from the database
    print("\n[2] Loading case database and building reference text...")
    engine = MedSearchEngine(str(args.database_csv))
    relevant_fulltext = build_relevant_cases_fulltext(relevant_map, engine)
    for case_num, text in relevant_fulltext.items():
        print(f"    Case {case_num}: {len(text):,} chars of reference text")

    # Step 3: Load benchmark cases
    print("\n[3] Loading benchmark cases...")
    all_cases = load_benchmark_cases(args.cases_csv)
    print(f"    Loaded {len(all_cases)} total cases")

    # Filter to cases that have relevant search results
    case_indices = []
    for i, case in enumerate(all_cases):
        case_num = extract_case_number(case.get('case_title', ''))
        if case_num and case_num in relevant_map:
            case_indices.append(i)

    if args.limit:
        case_indices = case_indices[:args.limit]

    print(f"    Testing {len(case_indices)} cases with relevant search data")

    if not case_indices:
        print("\nNo cases to test. Check that relevant-csv has matching entries.")
        return 1

    # Step 4: Run tests
    all_results = {}
    if args.mode in ("both", "baseline"):
        print(f"\n{'='*60}")
        print("MODE: BASELINE (no relevant case context)")
        print(f"{'='*60}")

        baseline_results, baseline_correct, baseline_total = run_mode(
            all_cases, case_indices, relevant_map, relevant_fulltext,
            mode="baseline",
            model=args.model,
            model_type=args.model_type,
            config_path=args.config_path,
            skills_dir=args.skills_dir,
            session_dir=args.session_dir,
            workers=args.workers,
            retry_no_answer=args.retry_no_answer,
        )
        all_results["baseline"] = {
            "results": baseline_results,
            "correct": baseline_correct,
            "total": baseline_total,
            "accuracy": baseline_correct / baseline_total if baseline_total > 0 else 0
        }

    if args.mode in ("both", "fewshot"):
        print(f"\n{'='*60}")
        print("MODE: FEW-SHOT (with relevant case context)")
        print(f"{'='*60}")

        fewshot_results, fewshot_correct, fewshot_total = run_mode(
            all_cases, case_indices, relevant_map, relevant_fulltext,
            mode="fewshot",
            model=args.model,
            model_type=args.model_type,
            config_path=args.config_path,
            skills_dir=args.skills_dir,
            session_dir=args.session_dir,
            workers=args.workers,
            retry_no_answer=args.retry_no_answer,
        )
        all_results["fewshot"] = {
            "results": fewshot_results,
            "correct": fewshot_correct,
            "total": fewshot_total,
            "accuracy": fewshot_correct / fewshot_total if fewshot_total > 0 else 0
        }

    # Step 5: Summary
    print_summary(all_results)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output_dir / f"fewshot_results_{timestamp}.json"

    save_data = {
        "timestamp": timestamp,
        "cases_csv": str(args.cases_csv),
        "relevant_csv": str(args.relevant_csv),
        "database_csv": str(args.database_csv),
        "model": args.model,
        "model_type": args.model_type,
        "num_cases": len(case_indices),
        "modes": {}
    }
    for mode_name, data in all_results.items():
        save_data["modes"][mode_name] = {
            "correct": data["correct"],
            "total": data["total"],
            "accuracy": data["accuracy"],
            "results": data["results"]
        }

    with open(output_path, 'w') as f:
        json.dump(save_data, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    md_output_path = args.output_dir / f"fewshot_comparison_{timestamp}.md"
    save_markdown_summary(
        output_path=md_output_path,
        all_results=all_results,
        model=args.model,
        model_type=args.model_type,
        relevant_csv=args.relevant_csv,
    )
    print(f"Markdown report saved to: {md_output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
