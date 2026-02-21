#!/usr/bin/env python3
"""Run external-LLM GUI automation with separate forward/backward passes.

Workflow:
1. Forward pass for each case: new chat -> paste prompt -> send
2. Wait global delay
3. Backward pass repeated N times:
   - Click new chat
   - Click first message
   - Click copy button and save clipboard
   - Right click first message, Down x4, Enter, Enter
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def build_prompt(case_id: str, repo_root: Path) -> str:
    script = repo_root / "src" / "utils" / "build_relevance_review_prompt.py"
    cmd = ["uv", "run", "python", str(script), "--case-id", case_id]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "prompt build failed")
    prompt = result.stdout
    if not prompt.strip():
        raise RuntimeError("prompt builder returned empty text")
    return prompt


def append_output(output_file: Path, case_id: str, content: str) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat()
    block = (
        f"\n{'=' * 100}\n"
        f"CASE_ID: {case_id}\n"
        f"TIMESTAMP: {stamp}\n"
        f"{'-' * 100}\n"
        f"{content.rstrip()}\n"
    )
    with output_file.open("a", encoding="utf-8") as f:
        f.write(block)


def load_processed_case_ids(output_file: Path) -> set[str]:
    if not output_file.exists():
        return set()
    text = output_file.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"CASE_ID:\s*(\d+)", text))


def extract_case_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"\d+", str(value))
    return m.group(0) if m else None


def load_case_ids_from_csv(csv_file: Path) -> list[str]:
    case_ids: list[str] = []
    seen: set[str] = set()
    with csv_file.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_id = (
                extract_case_id(row.get("case_id"))
                or extract_case_id(row.get("case_title"))
                or extract_case_id(next(iter(row.values()), None))
            )
            if case_id and case_id not in seen:
                case_ids.append(case_id)
                seen.add(case_id)
    return case_ids


def send_message(pyautogui, send_key: str) -> None:
    if send_key == "enter":
        pyautogui.press("enter")
    elif send_key == "command-enter":
        pyautogui.hotkey("command", "enter", interval=0.05)
    elif send_key == "ctrl-enter":
        pyautogui.hotkey("ctrl", "enter", interval=0.05)
    else:
        raise ValueError(f"Unsupported send key: {send_key}")


def focus_input_box(pyautogui, x: int | None, y: int | None, pause_seconds: float) -> None:
    if x is not None and y is not None:
        pyautogui.click(x, y, button="left")
    else:
        width, height = pyautogui.size()
        pyautogui.click(width // 2, max(10, height - 120), button="left")
    time.sleep(pause_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run forward-then-backward GUI automation for multiple cases")
    parser.add_argument("--case-ids", nargs="+", help="Case ids, e.g. 19172 19173 (overrides auto-pick)")
    parser.add_argument("--k", type=int, default=5, help="Auto-pick this many unprocessed case ids")
    parser.add_argument(
        "--source-csv",
        type=Path,
        default=Path("src/agent_v2/results/med-diagnosis-relevant-search.csv"),
        help="CSV containing case list",
    )
    parser.add_argument("--output-file", type=Path, default=Path("src/gpt52_verification/external_llm_reviews.txt"))
    parser.add_argument("--new-chat-x", type=int, default=160)
    parser.add_argument("--new-chat-y", type=int, default=58)
    parser.add_argument("--input-x", type=int, default=None)
    parser.add_argument("--input-y", type=int, default=None)
    parser.add_argument("--first-message-x", type=int, default=107)
    parser.add_argument("--first-message-y", type=int, default=311)
    parser.add_argument("--copy-x", type=int, default=284)
    parser.add_argument("--copy-y", type=int, default=887)
    parser.add_argument(
        "--send-key",
        choices=["enter", "command-enter", "ctrl-enter"],
        default="enter",
        help="Key combination to send prompt after paste",
    )
    parser.add_argument("--forward-gap-seconds", type=float, default=5.0)
    parser.add_argument("--forward-open-chat-wait-seconds", type=float, default=1.5)
    parser.add_argument("--wait-before-backward-seconds", type=float, default=15.0)
    parser.add_argument("--backward-gap-seconds", type=float, default=5.0)
    parser.add_argument("--open-chat-wait-seconds", type=float, default=1.5)
    parser.add_argument("--copy-retries", type=int, default=3)
    parser.add_argument("--copy-retry-wait-seconds", type=float, default=10.0)
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent

    try:
        import pyautogui
        import pyperclip
    except Exception as exc:  # noqa: BLE001
        print(
            "Missing required packages. Install with:\n"
            "  uv add pyautogui pyperclip\n"
            f"Import error: {exc}",
            file=sys.stderr,
        )
        return 1

    selected_case_ids: list[str]
    if args.case_ids:
        selected_case_ids = args.case_ids
    else:
        all_case_ids = load_case_ids_from_csv(args.source_csv)
        processed_case_ids = load_processed_case_ids(args.output_file)
        selected_case_ids = [cid for cid in all_case_ids if cid not in processed_case_ids][: max(0, args.k)]
        if not selected_case_ids:
            print("[INFO] No unprocessed case ids found.")
            return 0
        print(
            f"[INFO] Auto-picked {len(selected_case_ids)} case ids: {', '.join(selected_case_ids)} "
            f"(processed={len(processed_case_ids)})"
        )

    prompts: dict[str, str] = {}
    for case_id in selected_case_ids:
        try:
            prompts[case_id] = build_prompt(case_id, repo_root)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Failed to build prompt for case {case_id}: {exc}", file=sys.stderr)
            return 1
        print(f"[INFO] Prompt built for case {case_id} ({len(prompts[case_id])} chars)")

    print("[INFO] Starting GUI automation in 2 seconds...")
    time.sleep(2)

    # Forward pass: create new chat -> paste -> send
    for i, case_id in enumerate(selected_case_ids, start=1):
        pyautogui.click(args.new_chat_x, args.new_chat_y, button="left")
        time.sleep(args.forward_open_chat_wait_seconds)
        focus_input_box(pyautogui, args.input_x, args.input_y, args.pause_seconds)
        pyperclip.copy(prompts[case_id])
        if sys.platform == "darwin":
            pyautogui.hotkey("command", "v", interval=0.05)
        else:
            pyautogui.hotkey("ctrl", "v", interval=0.05)
        time.sleep(args.pause_seconds)
        send_message(pyautogui, args.send_key)
        print(f"[INFO] Forward {i}/{len(selected_case_ids)} sent: case {case_id}")
        time.sleep(args.forward_gap_seconds)

    print(f"[INFO] Waiting {args.wait_before_backward_seconds:.1f}s before backward pass...")
    time.sleep(args.wait_before_backward_seconds)

    # Backward pass: create new chat, process first message repeatedly.
    backward_case_order = list(reversed(selected_case_ids))
    for i, case_id in enumerate(backward_case_order, start=1):
        pyautogui.click(args.new_chat_x, args.new_chat_y, button="left")
        time.sleep(args.pause_seconds)

        pyautogui.click(args.first_message_x, args.first_message_y, button="left")
        time.sleep(args.open_chat_wait_seconds)

        sentinel = f"__COPY_SENTINEL__{time.time_ns()}__"
        pyperclip.copy(sentinel)
        copied_text = None
        for attempt in range(1, args.copy_retries + 1):
            pyautogui.click(args.copy_x, args.copy_y, button="left")
            print(f"[INFO] Backward copy {i}/{len(backward_case_order)} attempt {attempt}/{args.copy_retries}...")
            time.sleep(args.copy_retry_wait_seconds)
            after_clipboard = pyperclip.paste()
            if after_clipboard and after_clipboard != sentinel:
                copied_text = after_clipboard
                break

        if not copied_text:
            print(
                f"[FAILED] Backward {i}/{len(backward_case_order)} case {case_id}: clipboard did not update.",
                file=sys.stderr,
            )
            return 2

        append_output(args.output_file, case_id, copied_text)
        print(f"[OK] Saved backward {i}/{len(backward_case_order)} for case {case_id}")

        pyautogui.click(args.first_message_x, args.first_message_y, button="right")
        time.sleep(args.pause_seconds)
        for _ in range(4):
            pyautogui.press("down")
            time.sleep(0.05)
        pyautogui.press("enter")
        time.sleep(args.pause_seconds)
        pyautogui.press("enter")

        if i < len(backward_case_order):
            time.sleep(args.backward_gap_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
