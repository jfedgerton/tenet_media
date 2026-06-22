#!/usr/bin/env python3
"""
2_download_audio.py — Download MP3 audio for every episode
==========================================================

Reads all JSON files produced by 1_pull_data.py (in json_data/) and
downloads each episode's audio to audio_temp/.

Filenames follow the project convention:
    {slug}_{YYYYMMDDHHMMSS}_{episode_number}.mp3

Features:
  - Parallel downloads via ThreadPoolExecutor (--workers flag)
  - Skips files that already exist and have size > 0
  - Exponential back-off (5 retries)
  - Logs failures to failed_downloads.csv
  - Exits with code 1 if any downloads failed

Usage:
    python 2_download_audio.py
    python 2_download_audio.py --workers 8
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import argparse
import csv
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

# ── Project paths ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Configuration ────────────────────────────────────────────────────────────

JSON_INPUT_DIR = PROJECT_ROOT / "json_data"
AUDIO_OUTPUT_DIR = PROJECT_ROOT / "audio_temp"
FAILED_CSV = PROJECT_ROOT / "failed_downloads.csv"

MAX_RETRIES = 5
RETRY_PAUSES = [5, 15, 45, 120, 300]   # seconds between retries

REQUEST_TIMEOUT = 300                    # 5 min per download
CHUNK_SIZE = 1024 * 256                  # 256 KB streaming chunks
REQUEST_HEADERS = {
    "User-Agent": "PodcastResearchBot/1.0 (academic research project)"
}

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
    Convert an RSS pubDate string into our 14-digit date_id (YYYYMMDDHHMMSS).

    If the date cannot be parsed, returns 'nodate'.
    """
    if not air_date:
        return "nodate"
    try:
        # RSS feeds use RFC-2822 dates, e.g. "Mon, 01 Jan 2024 12:00:00 +0000"
        dt = parsedate_to_datetime(air_date)
        return dt.strftime("%Y%m%d%H%M%S")
    except Exception:
        pass
    # Fallback: try ISO-style dates.
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(air_date, fmt)
            return dt.strftime("%Y%m%d%H%M%S")
        except ValueError:
            continue
    return "nodate"


def build_download_list() -> list[dict]:
    """
    Scan all JSON files in json_data/ and build a flat list of episodes
    to download.  Each item is a dict with keys:
        slug, date_id, ep_num, audio_url, filename
    """
    downloads = []

    json_files = sorted(JSON_INPUT_DIR.glob("*.json"))
    if not json_files:
        log.warning("No JSON files found in %s", JSON_INPUT_DIR)
        return downloads

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        slug = data.get("slug", jf.stem)
        episodes = data.get("episodes", [])

        for idx, ep in enumerate(episodes, start=1):
            audio_url = ep.get("audio_url", "")
            if not audio_url:
                continue

            date_id = parse_date_id(ep.get("air_date", ""))
            ep_num = str(idx).zfill(4)    # zero-padded episode number

            filename = f"{slug}_{date_id}_{ep_num}.mp3"

            downloads.append(
                {
                    "slug": slug,
                    "date_id": date_id,
                    "ep_num": ep_num,
                    "audio_url": audio_url,
                    "filename": filename,
                }
            )

    return downloads


def download_one(item: dict, output_dir: Path) -> dict:
    """
    Download a single MP3 file with retry logic.

    Returns the item dict with an added 'status' key:
        'skipped'  — file already exists
        'ok'       — downloaded successfully
        'failed'   — all retries exhausted (includes 'error' key)
    """
    dest = output_dir / item["filename"]

    # Skip if the file already exists and has content.
    if dest.exists() and dest.stat().st_size > 0:
        item["status"] = "skipped"
        return item

    url = item["audio_url"]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            # Stream to disk so we don't hold the whole file in memory.
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    fh.write(chunk)

            item["status"] = "ok"
            return item

        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                pause = RETRY_PAUSES[attempt - 1]
                log.debug(
                    "Retry %d/%d for %s in %ds: %s",
                    attempt, MAX_RETRIES, item["filename"], pause, exc,
                )
                time.sleep(pause)
            else:
                # Clean up partial file if it exists.
                if dest.exists():
                    dest.unlink()
                item["status"] = "failed"
                item["error"] = str(exc)
                return item

    # Should not reach here, but just in case:
    item["status"] = "failed"
    item["error"] = "unknown"
    return item


# ── Main logic ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Download podcast audio files in parallel."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel download threads (default: 4)",
    )
    args = parser.parse_args()

    # Build the list of episodes that need downloading.
    downloads = build_download_list()
    log.info("Found %d episodes with audio URLs", len(downloads))

    if not downloads:
        log.info("Nothing to download.")
        return

    # Ensure the output directory exists.
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Parallel downloads ───────────────────────────────────────────────
    ok_count = 0
    skip_count = 0
    fail_count = 0
    failed_items = []

    log.info("Starting downloads with %d workers ...", args.workers)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download_one, item, AUDIO_OUTPUT_DIR): item
            for item in downloads
        }
        for future in as_completed(futures):
            result = future.result()
            status = result["status"]
            if status == "ok":
                ok_count += 1
                if ok_count % 100 == 0:
                    log.info("  Downloaded %d so far ...", ok_count)
            elif status == "skipped":
                skip_count += 1
            else:
                fail_count += 1
                failed_items.append(result)
                log.warning(
                    "FAILED: %s — %s", result["filename"], result.get("error", "")
                )

    # ── Summary ──────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info(
        "Done.  ok=%d  skipped=%d  failed=%d  total=%d",
        ok_count, skip_count, fail_count, len(downloads),
    )

    # Write failed downloads to CSV for later inspection.
    if failed_items:
        with open(FAILED_CSV, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["slug", "filename", "audio_url", "error"],
            )
            writer.writeheader()
            for item in failed_items:
                writer.writerow(
                    {
                        "slug": item["slug"],
                        "filename": item["filename"],
                        "audio_url": item["audio_url"],
                        "error": item.get("error", ""),
                    }
                )
        log.info("Failed downloads written to %s", FAILED_CSV)
        sys.exit(1)


if __name__ == "__main__":
    main()
