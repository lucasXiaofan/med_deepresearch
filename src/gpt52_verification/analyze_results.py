#!/usr/bin/env python3
"""
Analyze fewshot vs baseline comparison results and generate first-level analysis.

Reads:
  - Latest fewshot results JSON (src/agent_v2/fewshot_results/)
  - external_llm_reviews.txt (GPT-5.2 relevant case IDs and ratings)

Outputs:
  - analysis_first_level.md in src/gpt52_verification/
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

SRC_DIR = Path(__file__).parent.parent
PROJECT_ROOT = SRC_DIR.parent
FEWSHOT_DIR = SRC_DIR / "agent_v2" / "fewshot_results"
GPT52_DIR = SRC_DIR / "gpt52_verification"
REVIEWS_FILE = GPT52_DIR / "external_llm_reviews_v1.txt"


# ── helpers ──────────────────────────────────────────────────────────────────

def load_latest_fewshot_results() -> dict:
    """Load the most-recently created fewshot results JSON."""
    jsons = sorted(FEWSHOT_DIR.glob("fewshot_results_*.json"))
    if not jsons:
        raise FileNotFoundError(f"No fewshot result JSONs in {FEWSHOT_DIR}")
    path = jsons[-1]
    print(f"Loading fewshot results from: {path.name}", file=sys.stderr)
    with open(path) as f:
        return json.load(f)


def parse_external_reviews(path: Path) -> dict[str, dict]:
    """
    Parse external_llm_reviews.txt into a dict keyed by target_case_id.

    Each value:
        {
          "short_summary": str,
          "needs_image_understanding": bool,
          "relevant_cases": [
              {"case_id": str, "score": int, "rationale": str, "signal": str},
              ...
          ]
        }
    """
    text = path.read_text(encoding="utf-8")
    # Split on the separator line
    blocks = re.split(r"={40,}", text)
    reviews: dict[str, dict] = {}

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Extract CASE_ID header
        m = re.match(r"CASE_ID:\s*(\d+)", block)
        if not m:
            continue
        case_id = m.group(1)

        # Find the JSON object in this block
        json_start = block.find("{")
        json_end = block.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            continue
        try:
            data = json.loads(block[json_start:json_end])
        except json.JSONDecodeError:
            continue

        relevant_cases = []
        for rc in data.get("relevant_case_reviews", []):
            rc_id = rc.get("relevant_case_id", "")
            # Skip placeholder entries
            if not re.match(r"^\d+$", str(rc_id)):
                continue
            relevant_cases.append({
                "case_id": str(rc_id),
                "score": rc.get("relevance_score", "?"),
                "rationale": rc.get("rationale", ""),
                "signal": rc.get("most_important_signal", ""),
            })

        reviews[case_id] = {
            "short_summary": data.get("short_target_summary", ""),
            "needs_image_understanding": data.get("needs_image_understanding", False),
            "relevant_cases": relevant_cases,
        }

    print(f"Parsed {len(reviews)} external reviews.", file=sys.stderr)
    return reviews


def build_comparison(data: dict) -> list[dict]:
    """
    Merge baseline + fewshot results into per-case comparison rows.

    Returns list of:
        {
          "case_number": str,
          "case_title": str,
          "baseline_correct": bool,
          "fewshot_correct": bool,
          "change": int,          # +1 / -1 / 0
          "ground_truth": str,
          "baseline_answer": str,
          "fewshot_answer": str,
          "fewshot_cases_loaded": [{"case_id": str, "reason": str}, ...],
        }
    """
    baseline_map = {r["case_number"]: r for r in data["modes"]["baseline"]["results"]}
    fewshot_map  = {r["case_number"]: r for r in data["modes"]["fewshot"]["results"]}

    rows = []
    for cn, b in baseline_map.items():
        f = fewshot_map.get(cn, {})
        bc = b.get("correct", False)
        fc = f.get("correct", False)
        change = (1 if fc else 0) - (1 if bc else 0)
        rows.append({
            "case_number": cn,
            "case_title": b.get("case_title", f"Case {cn}"),
            "baseline_correct": bc,
            "fewshot_correct": fc,
            "change": change,
            "ground_truth": b.get("ground_truth", "?"),
            "baseline_answer": b.get("agent_answer", "?"),
            "fewshot_answer": f.get("agent_answer", "?"),
            "fewshot_cases_loaded": f.get("relevant_cases_loaded", []),
        })

    # Sort by case_number numerically for stable output
    rows.sort(key=lambda r: int(r["case_number"]))
    return rows



def rc_cell(review: Optional[dict]) -> tuple[str, int]:
    """Return (inline string of relevant cases, count of score>=4) for a case review."""
    if not review or not review["relevant_cases"]:
        return "_none_", 0
    parts = [f"{rc['case_id']}({rc['score']})" for rc in review["relevant_cases"]]
    high = sum(1 for rc in review["relevant_cases"] if isinstance(rc["score"], int) and rc["score"] >= 4)
    return " ".join(parts), high


def section_table(rows: list[dict], reviews: dict[str, dict],
                  baseline_mark: str, fewshot_mark: str) -> list[str]:
    """Render one simple table: Case | Relevant Cases (id/score) | #4+ | GT | Base | Few-shot"""
    lines = []
    lines.append("| Target Case | Relevant Cases (id/score) | #score≥4 | GT | Baseline | Few-shot |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        cn = r["case_number"]
        rc_str, high = rc_cell(reviews.get(cn))
        lines.append(
            f"| {cn} | {rc_str} | {high} "
            f"| {r['ground_truth']} | {r['baseline_answer']} {baseline_mark} "
            f"| {r['fewshot_answer']} {fewshot_mark} |"
        )
    return lines


def generate_markdown(rows: list[dict], reviews: dict[str, dict],
                      fewshot_data: dict) -> str:
    """Generate the full first-level analysis markdown."""
    baseline_stats = fewshot_data["modes"]["baseline"]
    fewshot_stats  = fewshot_data["modes"]["fewshot"]
    model          = fewshot_data.get("model", "unknown")

    plus_one     = [r for r in rows if r["change"] == +1]
    minus_one    = [r for r in rows if r["change"] == -1]
    both_correct = [r for r in rows if r["baseline_correct"] and r["fewshot_correct"]]
    both_wrong   = [r for r in rows if not r["baseline_correct"] and not r["fewshot_correct"]]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    improvement = (fewshot_stats['accuracy'] - baseline_stats['accuracy']) * 100

    md = []
    md.append(f"# Fewshot vs Baseline — First-Level Analysis")
    md.append(f"")
    md.append(f"_Generated: {now} · Model: `{model}` · Cases: {fewshot_data.get('num_cases', len(rows))}_")
    md.append(f"")
    md.append(f"| Mode | Correct | Total | Accuracy |")
    md.append(f"|---|---|---|---|")
    md.append(f"| Baseline | {baseline_stats['correct']} | {baseline_stats['total']} | {baseline_stats['accuracy']*100:.1f}% |")
    md.append(f"| Few-shot | {fewshot_stats['correct']} | {fewshot_stats['total']} | {fewshot_stats['accuracy']*100:.1f}% |")
    md.append(f"| **Improvement** | | | **{improvement:+.1f}%** |")
    md.append(f"")
    md.append(f"| ⬆️ +1 | ⬇️ -1 | ✅ Both Correct | ❌ Both Wrong |")
    md.append(f"|---|---|---|---|")
    md.append(f"| {len(plus_one)} | {len(minus_one)} | {len(both_correct)} | {len(both_wrong)} |")
    md.append(f"")

    # ── +1 ───────────────────────────────────────────────────────────────────
    md.append(f"---")
    md.append(f"")
    md.append(f"## ⬆️ +1  Baseline Wrong → Few-shot Correct  ({len(plus_one)} cases)")
    md.append(f"")
    md.extend(section_table(plus_one, reviews, "❌", "✅"))
    md.append(f"")

    # ── -1 ───────────────────────────────────────────────────────────────────
    md.append(f"---")
    md.append(f"")
    md.append(f"## ⬇️ -1  Baseline Correct → Few-shot Wrong  ({len(minus_one)} cases)")
    md.append(f"")
    md.extend(section_table(minus_one, reviews, "✅", "❌"))
    md.append(f"")

    # ── Both Correct ──────────────────────────────────────────────────────────
    md.append(f"---")
    md.append(f"")
    md.append(f"## ✅ Both Correct  ({len(both_correct)} cases)")
    md.append(f"")
    md.extend(section_table(both_correct, reviews, "✅", "✅"))
    md.append(f"")

    # ── Both Wrong ────────────────────────────────────────────────────────────
    md.append(f"---")
    md.append(f"")
    md.append(f"## ❌ Both Wrong  ({len(both_wrong)} cases)")
    md.append(f"")
    md.extend(section_table(both_wrong, reviews, "❌", "❌"))
    md.append(f"")

    return "\n".join(md)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    fewshot_data = load_latest_fewshot_results()
    reviews = parse_external_reviews(REVIEWS_FILE)
    rows = build_comparison(fewshot_data)
    md = generate_markdown(rows, reviews, fewshot_data)

    out_path = GPT52_DIR / "analysis_first_level.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"Written: {out_path}", file=sys.stderr)

    # Also print quick summary to stdout
    plus_one  = [r for r in rows if r["change"] == +1]
    minus_one = [r for r in rows if r["change"] == -1]
    both_correct = [r for r in rows if r["baseline_correct"] and r["fewshot_correct"]]
    both_wrong   = [r for r in rows if not r["baseline_correct"] and not r["fewshot_correct"]]

    print(f"\n=== Category Counts ===")
    print(f"+1  (Wrong→Correct): {len(plus_one)}")
    print(f"-1  (Correct→Wrong): {len(minus_one)}")
    print(f"✅  Both Correct:    {len(both_correct)}")
    print(f"❌  Both Wrong:      {len(both_wrong)}")
    print(f"\nCase IDs by category:")
    print(f"+1  : {[r['case_number'] for r in plus_one]}")
    print(f"-1  : {[r['case_number'] for r in minus_one]}")
    print(f"✅  : {[r['case_number'] for r in both_correct]}")
    print(f"❌  : {[r['case_number'] for r in both_wrong]}")


if __name__ == "__main__":
    main()
