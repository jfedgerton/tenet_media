#!/usr/bin/env python3
"""
3_create_key.py — Build a file key and identify missing transcripts
====================================================================

Reads all JSON files produced by 1_pull_data.py and creates a master
file key mapping every episode to its expected transcript filename.
Then compares against transcript_key/ to find which episodes still
need transcription.

This was originally an R script; rewritten in Python for consistency
with the rest of the pipeline.

Outputs (in PROJECT_ROOT):
    file_key.csv       — all episodes with their expected filenames
    missing_files.csv  — only the episodes that lack a transcript

Usage:
    python 3_create_key.py
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import csv
import json
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Configuration ────────────────────────────────────────────────────────────

JSON_INPUT_DIR    = PROJECT_ROOT / "json_data"
TRANSCRIPT_DIR    = PROJECT_ROOT / "transcript_key"
FILE_KEY_CSV      = PROJECT_ROOT / "file_key.csv"
MISSING_FILES_CSV = PROJECT_ROOT / "missing_files.csv"

# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Helper functions ─────────────────────────────────────────────────────────


def parse_date_id(air_date: str) -> str:
    """
    Convert an RSS pubDate string into YYYYMMDDHHMMSS.
    Returns 'nodate' if parsing fails.
    """
    if not air_date:
        return "nodate"
    try:
        dt = parsedate_to_datetime(air_date)
        return dt.strftime("%Y%m%d%H%M%S")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(air_date, fmt)
            return dt.strftime("%Y%m%d%H%M%S")
        except ValueError:
            continue
    return "nodate"


def scan_existing_transcripts() -> set[str]:
    """
    Walk transcript_key/{show_name}/ and collect all filenames that
    already exist.  Returns a set of (show_name, filename) tuples for
    fast lookup.
    """
    found = set()
    if not TRANSCRIPT_DIR.exists():
        log.warning("Transcript directory does not exist: %s", TRANSCRIPT_DIR)
        return found

    for show_dir in TRANSCRIPT_DIR.iterdir():
        if not show_dir.is_dir():
            continue
        for f in show_dir.iterdir():
            if f.is_file():
                # Store as "show_name/filename" for easy matching.
                found.add(f"{show_dir.name}/{f.name}")
    return found


# ── Main logic ───────────────────────────────────────────────────────────────


def main():
    # --- Step 1: Build the file key from all JSON files ---
    json_files = sorted(JSON_INPUT_DIR.glob("*.json"))
    if not json_files:
        log.error("No JSON files found in %s", JSON_INPUT_DIR)
        return

    log.info("Reading %d JSON files from %s", len(json_files), JSON_INPUT_DIR)

    rows = []           # list of dicts for the file key
    seen_urls = set()   # for deduplication on audio URL

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        slug = data.get("slug", jf.stem)
        episodes = data.get("episodes", [])

        for idx, ep in enumerate(episodes, start=1):
            url = ep.get("audio_url", "")

            # Deduplicate on URL — some feeds contain duplicate entries.
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            date_id = parse_date_id(ep.get("air_date", ""))
            ep_num = str(idx).zfill(4)

            # The transcript filename uses .txt extension.
            new_title = f"{slug}_{date_id}_{ep_num}.txt"

            rows.append(
                {
                    "json_name": slug,
                    "new_title": new_title,
                    "date_id": date_id,
                    "episode_number": ep_num,
                    "url": url,
                }
            )

    log.info("Total unique episodes in file key: %d", len(rows))

    # --- Step 2: Write file_key.csv (all episodes) ---
    fieldnames = ["json_name", "new_title", "date_id", "episode_number", "url"]

    with open(FILE_KEY_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Wrote file_key.csv → %s", FILE_KEY_CSV)

    # --- Step 3: Compare against existing transcripts ---
    existing = scan_existing_transcripts()
    log.info("Found %d existing transcript files in %s", len(existing), TRANSCRIPT_DIR)

    # An episode is "missing" if its expected path doesn't exist in
    # transcript_key/{json_name}/{new_title}.
    missing = []
    for row in rows:
        key = f"{row['json_name']}/{row['new_title']}"
        if key not in existing:
            missing.append(row)

    # --- Step 4: Write missing_files.csv ---
    with open(MISSING_FILES_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(missing)

    log.info("Wrote missing_files.csv → %s", MISSING_FILES_CSV)

    # --- Summary ---
    log.info("=" * 60)
    log.info("Total episodes expected:       %d", len(rows))
    log.info("Found in transcript_key:       %d", len(rows) - len(missing))
    log.info("Missing (need transcription):  %d", len(missing))


if __name__ == "__main__":
    main()
