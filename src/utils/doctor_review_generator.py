#!/usr/bin/env python3
"""
Doctor Review Generator — two-part tool for radiologist case review.

Part 1 (single case):
    Generate a human-readable markdown section for one target case, including:
    - Full target case text (clinical history, imaging findings, discussion, options)
    - Each relevant case with full text + GPT-5.2 rating and rationale

Part 2 (batch review doc):
    Pick k cases from specified categories (wrong→correct, both-wrong, etc.)
    and generate a combined markdown for a radiologist to review.
    Includes relevance-grading rubric, doctor questions, and developer notes.

Usage:
    # Single case preview
    python src/utils/doctor_review_generator.py --case 9905

    # Pick 3 wrong→correct + 3 both-wrong cases (auto-selected from latest results)
    python src/utils/doctor_review_generator.py --wrong-to-correct 3 --both-wrong 3

    # Explicitly specify cases
    python src/utils/doctor_review_generator.py --cases 9905,10128,11692

    # Use a specific fewshot results JSON
    python src/utils/doctor_review_generator.py --both-wrong 4 \\
        --results src/agent_v2/fewshot_results/fewshot_results_20260222_094842.json
"""

import csv
import json
import re
import sys
import argparse
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

SRC_DIR = Path(__file__).parent.parent
PROJECT_ROOT = SRC_DIR.parent

BENCHMARK_CSV   = PROJECT_ROOT / "medd_selected_50.csv"
DATABASE_CSV    = PROJECT_ROOT / "deepsearch_complete.csv"
GPT52_DIR       = SRC_DIR / "gpt52_verification"
REVIEWS_FILE    = GPT52_DIR / "external_llm_reviews_v1.txt"
FEWSHOT_DIR     = SRC_DIR / "agent_v2" / "fewshot_results"
OUTPUT_DIR      = GPT52_DIR / "doctor_reviews"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def _open_csv(path: Path) -> dict[str, dict]:
    """Load a CSV keyed by case number extracted from case_title."""
    result = {}
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            with open(path, encoding=enc, errors="replace") as f:
                for row in csv.DictReader(f):
                    title = row.get("case_title", "")
                    m = re.search(r"(\d+)", title)
                    if m:
                        result[m.group(1)] = dict(row)
            break
        except UnicodeDecodeError:
            continue
    return result


def load_benchmark(path: Path = BENCHMARK_CSV) -> dict[str, dict]:
    return _open_csv(path)


def load_database(path: Path = DATABASE_CSV) -> dict[str, dict]:
    return _open_csv(path)


def load_gpt52_reviews(path: Path = REVIEWS_FILE) -> dict[str, dict]:
    """
    Parse external_llm_reviews_v1.txt.
    Returns {target_case_id: {
        "short_summary": str,
        "needs_image_understanding": bool,
        "needs_image_understanding_reason": str,
        "relevant_case_reviews": [{
            "case_id": str, "score": int,
            "rationale": str, "signal": str
        }]
    }}
    """
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"={40,}", text)
    reviews: dict[str, dict] = {}
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = re.match(r"CASE_ID:\s*(\d+)", block)
        if not m:
            continue
        case_id = m.group(1)
        js = block.find("{")
        je = block.rfind("}") + 1
        if js == -1 or je == 0:
            continue
        try:
            data = json.loads(block[js:je])
        except json.JSONDecodeError:
            continue
        rcs = []
        for rc in data.get("relevant_case_reviews", []):
            rc_id = str(rc.get("relevant_case_id", ""))
            if not re.match(r"^\d+$", rc_id):
                continue
            rcs.append({
                "case_id": rc_id,
                "score": rc.get("relevance_score", "?"),
                "rationale": rc.get("rationale", ""),
                "signal": rc.get("most_important_signal", ""),
            })
        reviews[case_id] = {
            "short_summary": data.get("short_target_summary", ""),
            "needs_image_understanding": data.get("needs_image_understanding", False),
            "needs_image_understanding_reason": data.get("needs_image_understanding_reason", ""),
            "relevant_case_reviews": rcs,
        }
    return reviews


def parse_comparison_md(path: Path) -> dict[str, list[dict]]:
    """
    Parse a fewshot_comparison_*.md file directly into categorized rows.

    Expected table format:
      | Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
      | 19078 | C | B | N | C | Y | +1 |
    """
    text = path.read_text(encoding="utf-8")
    cats: dict[str, list] = {
        "wrong_to_correct": [],
        "correct_to_wrong": [],
        "both_correct": [],
        "both_wrong": [],
    }
    # Match data rows: | case | GT | base_ans | base_ok | few_ans | few_ok | change |
    pattern = re.compile(
        r"^\|\s*(\d+)\s*\|\s*([A-E?])\s*\|\s*([A-E?-])\s*\|\s*([YN])\s*"
        r"\|\s*([A-E?-])\s*\|\s*([YN])\s*\|\s*([+\-=]1?)\s*\|",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        cn, gt, ba, bc_str, fa, fc_str, change = m.groups()
        bc = bc_str == "Y"
        fc = fc_str == "Y"
        row = {
            "case_number": cn,
            "case_title": f"Case number {cn}",
            "ground_truth": gt,
            "baseline_answer": ba,
            "fewshot_answer": fa,
            "baseline_correct": bc,
            "fewshot_correct": fc,
            "fewshot_cases_loaded": [],
        }
        if bc and fc:
            cats["both_correct"].append(row)
        elif not bc and not fc:
            cats["both_wrong"].append(row)
        elif not bc and fc:
            cats["wrong_to_correct"].append(row)
        else:
            cats["correct_to_wrong"].append(row)
    return cats


def load_fewshot_results(path: Optional[Path] = None) -> tuple[dict[str, list[dict]], str]:
    """
    Load results from a .md comparison file or .json results file.
    Returns (cats_dict, source_name).
    If path is None, loads the latest JSON.
    """
    if path is None:
        jsons = sorted(FEWSHOT_DIR.glob("fewshot_results_*.json"))
        if not jsons:
            raise FileNotFoundError(f"No fewshot JSONs in {FEWSHOT_DIR}")
        path = jsons[-1]

    print(f"[results] {path.name}", file=sys.stderr)

    if path.suffix == ".md":
        cats = parse_comparison_md(path)
        return cats, path.stem

    # JSON path
    with open(path) as f:
        data = json.load(f)
    cats = _categorize_json(data)
    return cats, Path(data.get("relevant_csv", path.stem)).stem


def _categorize_json(fewshot_data: dict) -> dict[str, list[dict]]:
    """Return {category: [row, ...]} where row has case_number + result fields."""
    base_map = {r["case_number"]: r for r in fewshot_data["modes"]["baseline"]["results"]}
    few_map  = {r["case_number"]: r for r in fewshot_data["modes"]["fewshot"]["results"]}
    cats: dict[str, list] = {
        "wrong_to_correct": [],
        "correct_to_wrong": [],
        "both_correct": [],
        "both_wrong": [],
    }
    for cn, b in base_map.items():
        f = few_map.get(cn, {})
        bc, fc = b.get("correct", False), f.get("correct", False)
        row = {
            "case_number": cn,
            "case_title": b.get("case_title", f"Case {cn}"),
            "ground_truth": b.get("ground_truth", "?"),
            "baseline_answer": b.get("agent_answer", "?"),
            "fewshot_answer": f.get("agent_answer", "?"),
            "baseline_correct": bc,
            "fewshot_correct": fc,
            "fewshot_cases_loaded": f.get("relevant_cases_loaded", []),
        }
        if bc and fc:
            cats["both_correct"].append(row)
        elif not bc and not fc:
            cats["both_wrong"].append(row)
        elif not bc and fc:
            cats["wrong_to_correct"].append(row)
        else:
            cats["correct_to_wrong"].append(row)
    return cats


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

SCORE_STARS = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}


def _stars(score) -> str:
    try:
        return SCORE_STARS.get(int(score), f"{score}/5")
    except (TypeError, ValueError):
        return f"{score}/5"


def _wrap(label: str, text: str, max_len: int = 0) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if max_len and len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return f"**{label}:** {text}"


def format_options(options_raw: str) -> str:
    try:
        opts = json.loads(options_raw.replace("'", '"'))
    except Exception:
        try:
            opts = eval(options_raw)
        except Exception:
            return options_raw
    return "\n".join(f"  - **{k}**: {v}" for k, v in sorted(opts.items()))


def format_img_texts(img_texts_raw: str) -> str:
    """Format image caption list from JSON string."""
    try:
        captions = json.loads(img_texts_raw)
        if isinstance(captions, list):
            return "\n".join(f"  - Image {i+1}: {c}" for i, c in enumerate(captions))
    except Exception:
        pass
    return img_texts_raw


def case_block(case_row: dict, db_row: Optional[dict], prefix: str = "##") -> list[str]:
    """Render a full case block from the benchmark or database row."""
    lines = []
    cn = re.search(r"\d+", case_row.get("case_title", "")).group()
    link = case_row.get("link") or db_row.get("link", "") if db_row else case_row.get("link", "")
    lines.append(f"{prefix} Case {cn}  ")
    if link:
        lines.append(f"[{link}]({link})")
    lines.append("")

    ch = (case_row.get("clinical_history") or (db_row.get("clinical_history") if db_row else "")).strip()
    if ch:
        lines.append(f"**Clinical History:**")
        lines.append(ch)
        lines.append("")

    imf = (case_row.get("imaging_findings") or (db_row.get("imaging_findings") if db_row else "")).strip()
    if imf:
        lines.append(f"**Imaging Findings:**")
        lines.append(imf)
        lines.append("")

    disc = (case_row.get("discussion") or (db_row.get("discussion") if db_row else "")).strip()
    if disc:
        lines.append(f"**Discussion:**")
        lines.append(disc[:800] + ("…" if len(disc) > 800 else ""))
        lines.append("")

    dd = (case_row.get("differential_diagnosis") or (db_row.get("differential_diagnosis") if db_row else "")).strip()
    if dd:
        lines.append(f"**Differential Diagnosis:**")
        lines.append(dd)
        lines.append("")

    fd = (case_row.get("final_diagnosis") or (db_row.get("final_diagnosis") if db_row else "")).strip()
    if fd:
        lines.append(f"**Final Diagnosis:** {fd}")
        lines.append("")

    cats = (case_row.get("Categories") or (db_row.get("Categories") if db_row else "")).strip()
    if cats:
        lines.append(f"**Categories:** {cats}")
        lines.append("")

    img_n = case_row.get("images") or (db_row.get("images") if db_row else "")
    img_t = case_row.get("img_texts", "")
    if img_n:
        lines.append(f"**Images:** {img_n} image(s)")
    if img_t:
        lines.append(format_img_texts(img_t))
    if img_n or img_t:
        lines.append("")

    return lines


def relevant_case_section(
    rc_id: str,
    db: dict[str, dict],
    gpt52_review: Optional[dict],  # the review entry for THIS relevant case
    index: int,
) -> list[str]:
    """Render one relevant case with its DB info and GPT-5.2 rating."""
    lines = []
    db_row = db.get(rc_id, {})

    score = gpt52_review["score"] if gpt52_review else "?"
    stars = _stars(score)
    lines.append(f"### Relevant Case {index}: #{rc_id}  {stars} ({score}/5)")

    link = db_row.get("link", "")
    if link:
        lines.append(f"[{link}]({link})")
    lines.append("")

    if gpt52_review:
        lines.append(f"> **GPT-5.2 Signal:** {gpt52_review['signal']}")
        lines.append(f">")
        lines.append(f"> **GPT-5.2 Rationale:** {gpt52_review['rationale']}")
        lines.append("")

    ch = db_row.get("clinical_history", "").strip()
    if ch:
        lines.append(f"**Clinical History:** {ch}")
        lines.append("")

    imf = db_row.get("imaging_findings", "").strip()
    if imf:
        lines.append(f"**Imaging Findings:** {imf[:500]}{'…' if len(imf) > 500 else ''}")
        lines.append("")

    fd = db_row.get("final_diagnosis", "").strip()
    if fd:
        lines.append(f"**Final Diagnosis:** {fd}")
        lines.append("")

    if not db_row:
        lines.append("_Case not found in database._")
        lines.append("")

    return lines


RUBRIC = """
## Relevance Grading Rubric

Please rate each relevant case on a **1–5** scale:

| Score | Meaning |
|---|---|
| **5 — Highly relevant** | Same pathology, same organ/location, same imaging modality; imaging features directly mirror the target case and would strongly guide the diagnosis |
| **4 — Relevant** | Same pathology family or strong imaging analogy; provides meaningful diagnostic support even if minor differences in location or patient demographics |
| **3 — Partially relevant** | Related differential or useful contrast case; provides supporting evidence but would not alone drive the diagnosis |
| **2 — Weakly relevant** | Tangentially related; useful mainly for exclusion or academic comparison |
| **1 — Not relevant** | Different pathology, different mechanism; unlikely to help a radiologist reach the target diagnosis |

**Grading dimensions to consider:**
1. **Pathology match** — same diagnosis vs. differential vs. unrelated
2. **Imaging feature overlap** — do the key imaging findings align (signal characteristics, enhancement pattern, morphology)?
3. **Organ / location** — same site vs. analogous site vs. different organ
4. **Clinical context** — age, sex, presentation — do they overlap meaningfully?
5. **Diagnostic utility** — would seeing this case help a radiologist identify the target condition?

""".strip()


DOCTOR_QUESTIONS = """
## Questions for the Radiologist

For **each case** in this document, please answer the following:

1. **Discriminating imaging features**: Which specific imaging features are most discriminating for reaching the correct diagnosis? (e.g. signal intensity, enhancement pattern, morphology, location)

2. **Image-reading necessity**: For this case, is direct image viewing essential — or is the written imaging findings text sufficient for a radiologist to identify the correct diagnosis? Please explain why.

3. **When images are essential vs. text is enough**:
   - *Cases where you must read the images*: What types of findings or diagnostic distinctions genuinely require looking at the actual images rather than reading the written report?
   - *Cases where imaging findings text is enough*: What types of cases can be reliably diagnosed from the written imaging findings alone, without viewing the images?

4. **GPT-5.2 reasoning check**: For each relevant case listed, does GPT-5.2's stated rationale correctly identify the key imaging link to the target case? Is the "most important signal" clinically accurate and meaningful?

5. **Your relevance rating**: Using the rubric above, assign your own 1–5 score for each relevant case. Note any disagreements with GPT-5.2's rating and explain why.

6. **Framework for relevance judgment**: What is your general framework for deciding whether a reference case would help a radiologist diagnose a new Eurorad case? Which dimensions matter most — pathology match, imaging modality, organ/location, clinical context, or something else?

""".strip()


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — SINGLE CASE SECTION
# ═══════════════════════════════════════════════════════════════════════════════

def build_single_case_section(
    case_number: str,
    benchmark: dict[str, dict],
    db: dict[str, dict],
    reviews: dict[str, dict],
    result_row: Optional[dict] = None,   # used only for dev notes, not shown to doctor
) -> list[str]:
    """
    Return markdown lines for one full case review section (doctor-facing).
    Contains: target case full text + relevant cases with GPT-5.2 reasoning.
    No model performance info, no GPT-5.2 summary header.
    """
    lines = []
    bench_row = benchmark.get(case_number, {})
    db_row    = db.get(case_number, {})
    gpt52     = reviews.get(case_number, {})

    # ── Target case header ────────────────────────────────────────────────────
    lines.append(f"---")
    lines.append("")
    lines.append(f"# Case {case_number}")
    lines.append("")

    # Clinical history first so options have context
    ch = (bench_row.get("clinical_history") or (db_row.get("clinical_history") if db_row else "")).strip()
    if ch:
        lines.append(f"**Clinical History:**")
        lines.append(ch)
        lines.append("")

    # Multiple choice options
    opts_raw = bench_row.get("options", "")
    if opts_raw:
        lines.append(f"**Diagnosis Options:**")
        lines.append(format_options(opts_raw))
        lines.append("")

    # Full target case text (clinical history will repeat here — acceptable for completeness)
    lines.append(f"## Target Case — Full Text")
    lines.append("")
    if bench_row:
        lines.extend(case_block(bench_row, db_row, prefix="###"))
    elif db_row:
        lines.extend(case_block(db_row, None, prefix="###"))
    else:
        lines.append("_Target case not found in database._")
        lines.append("")

    # ── Relevant cases ────────────────────────────────────────────────────────
    rc_reviews = {rc["case_id"]: rc for rc in gpt52.get("relevant_case_reviews", [])}
    all_rc_ids = list(rc_reviews.keys())

    # Also include any fewshot-loaded cases not covered by reviews
    if result_row:
        for lc in result_row.get("fewshot_cases_loaded", []):
            cid = str(lc.get("case_id", ""))
            if cid and cid not in rc_reviews:
                all_rc_ids.append(cid)

    if all_rc_ids:
        lines.append(f"## Relevant Reference Cases ({len(all_rc_ids)} total)")
        lines.append("")
        for i, rc_id in enumerate(all_rc_ids, 1):
            rc_review = rc_reviews.get(rc_id)
            lines.extend(relevant_case_section(rc_id, db, rc_review, i))
    else:
        lines.append("_No relevant cases found._")
        lines.append("")

    return lines


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2 — BATCH REVIEW DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════════

CATEGORY_LABELS = {
    "wrong_to_correct": "⬆️ Wrong → Correct (few-shot helped)",
    "both_wrong":       "❌ Both Wrong (few-shot did not help)",
    "correct_to_wrong": "⬇️ Correct → Wrong (few-shot confused model)",
    "both_correct":     "✅ Both Correct",
}


def build_review_doc(
    selected: list[tuple[str, str]],   # [(case_number, category_key), ...]
    benchmark: dict[str, dict],
    db: dict[str, dict],
    reviews: dict[str, dict],
    cats: dict[str, list[dict]],
    results_name: str = "",
) -> str:
    """Build the full doctor review markdown document."""
    # Build a lookup: case_number → result_row
    result_lookup: dict[str, dict] = {}
    for cat_rows in cats.values():
        for r in cat_rows:
            result_lookup[r["case_number"]] = r

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []

    # ── Cover page ─────────────────────────────────────────────────────────────
    lines.append("# Radiologist Case Review — Relevance Assessment")
    lines.append("")
    lines.append(f"_Generated: {now}_  ")
    lines.append(f"_Cases in this document: {len(selected)}_")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(
        "This document contains a set of Eurorad cases and their AI-retrieved relevant "
        "reference cases. For each target case you will see:"
    )
    lines.append("")
    lines.append("- The full target case text (clinical history, imaging findings, discussion)")
    lines.append("- A set of retrieved relevant reference cases with full text")
    lines.append("- GPT-5.2's automated relevance rating and reasoning for each reference case")
    lines.append("")

    # ── Rubric ─────────────────────────────────────────────────────────────────
    lines.append(RUBRIC)
    lines.append("")

    # ── Questions — once, at top ───────────────────────────────────────────────
    lines.append(DOCTOR_QUESTIONS)
    lines.append("")
    lines.append("_Please apply the questions above to each case below._")
    lines.append("")

    # ── Case sections ──────────────────────────────────────────────────────────
    for case_number, category_key in selected:
        result_row = result_lookup.get(case_number)
        section = build_single_case_section(
            case_number=case_number,
            benchmark=benchmark,
            db=db,
            reviews=reviews,
            result_row=result_row,
        )
        lines.extend(section)
        lines.append("")

    # ── Developer notes (bottom) ───────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## Developer Notes")
    lines.append("")
    lines.append("_This section is for the development team. Not part of the doctor's review task._")
    lines.append("")
    lines.append("### Case → Category Mapping")
    lines.append("")
    lines.append("| Case | Category | GT | Baseline | Few-shot |")
    lines.append("|---|---|---|---|---|")
    for case_number, category_key in selected:
        r = result_lookup.get(case_number, {})
        cat_label = CATEGORY_LABELS.get(category_key, category_key)
        lines.append(
            f"| {case_number} | {cat_label} "
            f"| {r.get('ground_truth','?')} "
            f"| {r.get('baseline_answer','?')} {'✅' if r.get('baseline_correct') else '❌'} "
            f"| {r.get('fewshot_answer','?')} {'✅' if r.get('fewshot_correct') else '❌'} |"
        )
    lines.append("")
    lines.append("### Category Summary (full run)")
    lines.append("")
    lines.append("| Category | Count | Case Numbers |")
    lines.append("|---|---|---|")
    for cat_key, cat_rows in cats.items():
        cns = ", ".join(r["case_number"] for r in cat_rows)
        lines.append(f"| {CATEGORY_LABELS[cat_key]} | {len(cat_rows)} | {cns} |")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate doctor-readable case review documents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Most common: pass a comparison .md file, use default selection (3 wrong→correct + 3 both-wrong)
  python src/utils/doctor_review_generator.py src/agent_v2/fewshot_results/fewshot_comparison_20260222_140646.md

  # Override counts
  python src/utils/doctor_review_generator.py fewshot_comparison_20260222_140646.md --wrong-to-correct 2 --both-wrong 4

  # Single case preview
  python src/utils/doctor_review_generator.py fewshot_comparison_20260222_140646.md --case 9905

  # Explicit cases
  python src/utils/doctor_review_generator.py fewshot_comparison_20260222_140646.md --cases 9905,10128,11692

  # Use a JSON results file instead
  python src/utils/doctor_review_generator.py src/agent_v2/fewshot_results/fewshot_results_20260222_094842.json
        """
    )
    parser.add_argument("results_file", type=Path, nargs="?", default=None,
        help="Path to fewshot_comparison_*.md or fewshot_results_*.json (default: latest JSON)")
    parser.add_argument("--case", type=str, default=None,
        help="Single case number to preview")
    parser.add_argument("--cases", type=str, default=None,
        help="Comma-separated list of case numbers")
    parser.add_argument("--wrong-to-correct", type=int, default=3, metavar="K",
        help="Pick K cases from wrong→correct category (default: 3)")
    parser.add_argument("--both-wrong", type=int, default=3, metavar="K",
        help="Pick K cases from both-wrong category (default: 3)")
    parser.add_argument("--correct-to-wrong", type=int, default=0, metavar="K",
        help="Pick K cases from correct→wrong category (default: 0)")
    parser.add_argument("--both-correct", type=int, default=0, metavar="K",
        help="Pick K cases from both-correct category (default: 0)")
    parser.add_argument("--seed", type=int, default=42,
        help="Random seed for case selection (default: 42)")
    parser.add_argument("--output", type=Path, default=None,
        help="Output markdown path (default: auto-named in gpt52_verification/doctor_reviews/)")
    parser.add_argument("--benchmark-csv", type=Path, default=BENCHMARK_CSV)
    parser.add_argument("--database-csv", type=Path, default=DATABASE_CSV)

    args = parser.parse_args()

    # ── Load data ──────────────────────────────────────────────────────────────
    print("Loading data...", file=sys.stderr)
    benchmark = load_benchmark(args.benchmark_csv)
    db        = load_database(args.database_csv)
    reviews   = load_gpt52_reviews()
    cats, results_name = load_fewshot_results(args.results_file)

    print(f"  benchmark:  {len(benchmark)} cases", file=sys.stderr)
    print(f"  database:   {len(db)} cases", file=sys.stderr)
    print(f"  reviews:    {len(reviews)} cases", file=sys.stderr)
    for ck, cv in cats.items():
        print(f"  {ck}: {len(cv)} cases", file=sys.stderr)
    print("", file=sys.stderr)

    # ── Build selected list ────────────────────────────────────────────────────
    selected: list[tuple[str, str]] = []
    rng = random.Random(args.seed)

    if args.case:
        # Single case — find its category
        found_cat = "unknown"
        for ck, rows in cats.items():
            if any(r["case_number"] == args.case for r in rows):
                found_cat = ck
                break
        selected = [(args.case, found_cat)]

    elif args.cases:
        for cn in [c.strip() for c in args.cases.split(",")]:
            found_cat = "unknown"
            for ck, rows in cats.items():
                if any(r["case_number"] == cn for r in rows):
                    found_cat = ck
                    break
            selected.append((cn, found_cat))

    else:
        picks = {
            "wrong_to_correct": args.wrong_to_correct,
            "both_wrong":       args.both_wrong,
            "correct_to_wrong": args.correct_to_wrong,
            "both_correct":     args.both_correct,
        }
        for cat_key, k in picks.items():
            if k <= 0:
                continue
            pool = [r["case_number"] for r in cats[cat_key]]
            chosen = rng.sample(pool, min(k, len(pool)))
            for cn in chosen:
                selected.append((cn, cat_key))

    if not selected:
        print("No cases selected. Use --case, --cases, or --wrong-to-correct / --both-wrong flags.")
        return 1

    print(f"\nSelected {len(selected)} cases:", file=sys.stderr)
    for cn, ck in selected:
        print(f"  {cn}  [{ck}]", file=sys.stderr)

    # ── Generate document ──────────────────────────────────────────────────────
    doc = build_review_doc(
        selected=selected,
        benchmark=benchmark,
        db=db,
        reviews=reviews,
        cats=cats,
        results_name=results_name,
    )

    # ── Write output ───────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        cases_str = "_".join(cn for cn, _ in selected[:4])
        if len(selected) > 4:
            cases_str += f"_and{len(selected)-4}more"
        out_path = OUTPUT_DIR / f"doctor_review_{ts}_{cases_str}.md"

    out_path.write_text(doc, encoding="utf-8")
    print(f"\nWritten: {out_path}", file=sys.stderr)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
