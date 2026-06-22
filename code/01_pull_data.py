#!/usr/bin/env python3
"""
1_pull_data.py — Fetch RSS feeds and extract episode metadata
=============================================================

For each podcast in podcast_feeds.csv, this script:
  1. Downloads the RSS XML feed
  2. Parses it with BeautifulSoup to extract episode-level metadata
  3. Optionally joins Podchaser episode IDs from data/episodes/
  4. Saves a per-podcast JSON file to json_data/{slug}.json

Usage:
    python 1_pull_data.py
    python 1_pull_data.py --feeds-csv /path/to/feeds.csv

Output:
    PROJECT_ROOT/json_data/{slug}.json  (one file per podcast)
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Project paths ────────────────────────────────────────────────────────────
# PROJECT_ROOT is the *pipeline* directory (parent of code/).
# All data directories hang off PROJECT_ROOT.

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Configuration ────────────────────────────────────────────────────────────

# Retry / back-off settings for HTTP requests.
MAX_RETRIES = 3
RETRY_PAUSES = [30, 90, 300]        # seconds to wait after attempt 1, 2, 3

REQUEST_TIMEOUT = 60                 # seconds per HTTP request
REQUEST_HEADERS = {
    "User-Agent": "PodcastResearchBot/1.0 (academic research project)"
}

# Where to read / write data (all relative to PROJECT_ROOT).
DEFAULT_FEEDS_CSV = PROJECT_ROOT / "code" / "podcast_feeds.csv"
JSON_OUTPUT_DIR   = PROJECT_ROOT / "json_data"
PODCHASER_DIR     = PROJECT_ROOT / "data" / "episodes"

# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Helper functions ─────────────────────────────────────────────────────────


def fetch_with_retry(url: str) -> requests.Response | None:
    """
    GET *url* with exponential back-off.

    Returns the Response on success, or None after all retries are exhausted.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                pause = RETRY_PAUSES[attempt - 1]
                log.warning(
                    "Attempt %d/%d failed for %s — retrying in %ds: %s",
                    attempt, MAX_RETRIES, url, pause, exc,
                )
                time.sleep(pause)
            else:
                log.error(
                    "All %d attempts failed for %s: %s",
                    MAX_RETRIES, url, exc,
                )
    return None


def parse_rss_feed(xml_text: str) -> list[dict]:
    """
    Parse RSS XML and return a list of episode dicts.

    Each dict contains:
        title, description, air_date, audio_url
    """
    soup = BeautifulSoup(xml_text, "xml")
    episodes = []

    # Each <item> in an RSS feed is one episode.
    for item in soup.find_all("item"):

        # Episode title — plain text inside <title>.
        title_tag = item.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Description — try <description>, fall back to <itunes:summary>.
        desc_tag = item.find("description") or item.find("itunes:summary")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Publication date — <pubDate> is standard in RSS 2.0.
        pub_tag = item.find("pubDate")
        air_date = pub_tag.get_text(strip=True) if pub_tag else ""

        # Audio URL — lives in the <enclosure> tag's "url" attribute.
        enc_tag = item.find("enclosure")
        audio_url = enc_tag.get("url", "") if enc_tag else ""

        episodes.append(
            {
                "title": title,
                "description": description,
                "air_date": air_date,
                "audio_url": audio_url,
            }
        )

    return episodes


def load_podchaser_ids(podcast_id: str) -> dict:
    """
    Try to load Podchaser episode IDs for this podcast.

    Looks for data/episodes/eps_pod_{podcast_id}.json.
    Returns a dict mapping episode title -> podchaser episode id,
    or an empty dict if the file doesn't exist.
    """
    path = PODCHASER_DIR / f"eps_pod_{podcast_id}.json"
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read Podchaser file %s: %s", path, exc)
        return {}

    # The Podchaser JSON is expected to be a list of dicts with at least
    # "title" and "id" keys.  Build a lookup keyed on title.
    lookup = {}
    for rec in records:
        ep_title = rec.get("title", "")
        ep_id = rec.get("id", "")
        if ep_title:
            lookup[ep_title] = ep_id
    return lookup


def join_podchaser(episodes: list[dict], pc_lookup: dict) -> None:
    """
    Mutate *episodes* in-place, adding a 'podchaser_id' field where a
    matching title is found in *pc_lookup*.
    """
    matched = 0
    for ep in episodes:
        pid = pc_lookup.get(ep["title"], "")
        ep["podchaser_id"] = pid
        if pid:
            matched += 1
    if pc_lookup:
        log.info(
            "  Podchaser join: %d/%d episodes matched", matched, len(episodes)
        )


# ── Main logic ───────────────────────────────────────────────────────────────


def process_feeds(feeds_csv: Path) -> None:
    """
    Read the feeds CSV, fetch each RSS feed, parse episodes, and write JSON.
    """
    # --- Read the CSV of podcast feeds ---
    if not feeds_csv.exists():
        log.error("Feeds CSV not found: %s", feeds_csv)
        sys.exit(1)

    with open(feeds_csv, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        feeds = list(reader)

    log.info("Loaded %d feeds from %s", len(feeds), feeds_csv)

    # --- Ensure output directory exists ---
    JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Counters for the summary ---
    total_feeds = len(feeds)
    success_count = 0
    fail_count = 0
    total_episodes = 0

    # --- Loop over each podcast feed ---
    for i, row in enumerate(feeds, start=1):
        podcast_id = row.get("podcast_id", "")
        title = row.get("title", "unknown")
        slug = row.get("slug", "unknown")
        rss_url = row.get("rss_url", "")

        log.info(
            "[%d/%d] Fetching feed for '%s' (slug=%s)",
            i, total_feeds, title, slug,
        )

        if not rss_url:
            log.warning("  No rss_url for '%s' — skipping", title)
            fail_count += 1
            continue

        # Fetch the RSS XML with retry logic.
        resp = fetch_with_retry(rss_url)
        if resp is None:
            fail_count += 1
            continue

        # Parse episode metadata from the XML.
        episodes = parse_rss_feed(resp.text)
        log.info("  Parsed %d episodes", len(episodes))

        # Optional: join Podchaser episode IDs if file exists.
        pc_lookup = load_podchaser_ids(podcast_id)
        if pc_lookup:
            join_podchaser(episodes, pc_lookup)

        # Build the output record for this podcast.
        output = {
            "podcast_id": podcast_id,
            "title": title,
            "slug": slug,
            "rss_url": rss_url,
            "episode_count": len(episodes),
            "episodes": episodes,
        }

        # Write to json_data/{slug}.json.
        out_path = JSON_OUTPUT_DIR / f"{slug}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2, ensure_ascii=False)

        log.info("  Saved → %s", out_path)
        success_count += 1
        total_episodes += len(episodes)

    # --- Summary ---
    log.info("=" * 60)
    log.info("Done.  %d/%d feeds succeeded, %d failed", success_count, total_feeds, fail_count)
    log.info("Total episodes collected: %d", total_episodes)


# ── CLI entry point ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Fetch podcast RSS feeds and save episode metadata as JSON."
    )
    parser.add_argument(
        "--feeds-csv",
        type=Path,
        default=DEFAULT_FEEDS_CSV,
        help="Path to the CSV of podcast feeds (default: code/podcast_feeds.csv)",
    )
    args = parser.parse_args()

    process_feeds(args.feeds_csv)


if __name__ == "__main__":
    main()
