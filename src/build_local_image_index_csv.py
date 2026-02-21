#!/usr/bin/env python3
"""Build local image index CSV from downloaded EURORAD files.

This script maps each image in deepresearch metadata to a local downloaded file
by image ID (filename stem), and writes a CSV that ImageLoader can use as
pre-cached local paths.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def extract_case_id(plink: str) -> str:
    match = re.search(r"/case/(\d+)", str(plink))
    return match.group(1) if match else ""


def build_local_stem_index(eurorad_dir: Path) -> dict[str, list[Path]]:
    stem_index: dict[str, list[Path]] = defaultdict(list)
    valid_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

    for path in eurorad_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in valid_ext:
            continue
        stem_index[path.stem].append(path.resolve())

    return dict(stem_index)


def pick_candidate(candidates: list[Path], case_id: str) -> Path:
    if len(candidates) == 1:
        return candidates[0]

    # Prefer paths containing "Case number {case_id}" if available.
    case_hint = f"Case number {case_id}"
    for candidate in candidates:
        if case_hint in str(candidate):
            return candidate

    # Fallback: deterministic ordering.
    return sorted(candidates)[0]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_metadata_csv = repo_root / "deepresearch图片链接.csv"
    default_eurorad_dir = repo_root / "EURORAD"
    default_output_csv = repo_root / "data" / "image_local_index.csv"

    parser = argparse.ArgumentParser(description="Build local image index CSV")
    parser.add_argument("--metadata-csv", type=Path, default=default_metadata_csv)
    parser.add_argument("--eurorad-dir", type=Path, default=default_eurorad_dir)
    parser.add_argument("--output-csv", type=Path, default=default_output_csv)
    args = parser.parse_args()

    if not args.metadata_csv.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {args.metadata_csv}")
    if not args.eurorad_dir.exists():
        raise FileNotFoundError(f"EURORAD directory not found: {args.eurorad_dir}")

    print(f"Scanning local images under: {args.eurorad_dir}")
    stem_index = build_local_stem_index(args.eurorad_dir)
    print(f"Indexed {sum(len(v) for v in stem_index.values())} local files, {len(stem_index)} unique image IDs")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    matched = 0
    multi = 0
    missing = 0

    rows: list[dict[str, str]] = []
    with args.metadata_csv.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            img_id = (row.get("img_id") or "").strip()
            if not img_id:
                continue

            case_id = extract_case_id(row.get("plink", ""))
            candidates = stem_index.get(img_id, [])

            status = "missing"
            local_path = ""
            candidate_count = len(candidates)
            if candidate_count == 1:
                matched += 1
                status = "matched"
                local_path = str(candidates[0])
            elif candidate_count > 1:
                matched += 1
                multi += 1
                status = "matched_multiple"
                local_path = str(pick_candidate(candidates, case_id))
            else:
                missing += 1

            rows.append(
                {
                    "case_id": case_id,
                    "img_id": img_id,
                    "local_path": local_path,
                    "status": status,
                    "candidate_count": str(candidate_count),
                    "img_url": row.get("img_url", ""),
                    "plink": row.get("plink", ""),
                }
            )

    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["case_id", "img_id", "local_path", "status", "candidate_count", "img_url", "plink"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved index CSV: {args.output_csv}")
    print(f"Metadata rows: {total}")
    print(f"Matched rows: {matched}")
    print(f"Missing rows: {missing}")
    print(f"Matched rows with multiple candidates: {multi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

