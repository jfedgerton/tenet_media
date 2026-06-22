#!/usr/bin/env python3
"""
4_transcribe.py — Transcribe podcast audio with Whisper
========================================================

Reads a CSV (typically missing_files.csv from step 3) and transcribes
each episode using OpenAI's Whisper model.  Designed to work with
Slurm array jobs via --run-one INDEX.

Audio lookup order:
    1. audio_temp/{json_name}/{audio_file}   (show-specific subdirectory)
    2. audio_temp/{audio_file}               (flat layout)

Transcripts are saved to:
    transcript_key/{json_name}/{new_title}

Usage:
    # Transcribe everything in the CSV:
    python 4_transcribe.py --csv missing_files.csv

    # Transcribe a single row (for Slurm array jobs):
    python 4_transcribe.py --csv missing_files.csv --run-one 42

    # Use a larger model:
    python 4_transcribe.py --csv missing_files.csv --model medium

Slurm array example:
    #SBATCH --array=0-999
    python code/4_transcribe.py --csv missing_files.csv --run-one $SLURM_ARRAY_TASK_ID
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import argparse
import csv
import logging
import sys
from pathlib import Path

import whisper

# ── Project paths ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Configuration ────────────────────────────────────────────────────────────

AUDIO_DIR      = PROJECT_ROOT / "audio_temp"
TRANSCRIPT_DIR = PROJECT_ROOT / "transcript_key"

# Set to True to delete the audio file after a successful transcription.
# Saves disk space on shared HPC filesystems.
DELETE_AUDIO = True

# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Helper functions ─────────────────────────────────────────────────────────


def find_audio_file(json_name: str, new_title: str) -> Path | None:
    """
    Locate the MP3 audio file for this episode.

    The transcript filename ends in .txt; the audio filename ends in .mp3.
    We check two possible locations:
        1. audio_temp/{json_name}/{audio_name}   (show subdirectory)
        2. audio_temp/{audio_name}               (flat layout)

    Returns the Path if found, or None.
    """
    audio_name = new_title.replace(".txt", ".mp3")

    # Check show-specific subdirectory first.
    path_nested = AUDIO_DIR / json_name / audio_name
    if path_nested.exists():
        return path_nested

    # Fall back to flat layout.
    path_flat = AUDIO_DIR / audio_name
    if path_flat.exists():
        return path_flat

    return None


def transcribe_episode(
    model,
    json_name: str,
    new_title: str,
) -> bool:
    """
    Transcribe a single episode.

    Returns True on success, False on failure.
    """
    # --- Locate the audio file ---
    audio_path = find_audio_file(json_name, new_title)
    if audio_path is None:
        log.warning("Audio not found for %s/%s — skipping", json_name, new_title)
        return False

    # --- Ensure the output directory exists ---
    out_dir = TRANSCRIPT_DIR / json_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / new_title

    # Skip if transcript already exists.
    if out_path.exists() and out_path.stat().st_size > 0:
        log.info("Transcript already exists: %s — skipping", out_path)
        return True

    # --- Run Whisper ---
    log.info("Transcribing: %s", audio_path)
    try:
        result = model.transcribe(str(audio_path))
    except Exception as exc:
        log.error("Whisper failed on %s: %s", audio_path, exc)
        return False

    text = result.get("text", "")

    # --- Save the transcript ---
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)

    log.info("Saved transcript → %s (%d chars)", out_path, len(text))

    # --- Optionally delete the audio file to free disk space ---
    if DELETE_AUDIO:
        try:
            audio_path.unlink()
            log.info("Deleted audio: %s", audio_path)
        except OSError as exc:
            log.warning("Could not delete %s: %s", audio_path, exc)

    return True


# ── Main logic ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe podcast episodes with Whisper."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="CSV file with columns: json_name, new_title, date_id, episode_number",
    )
    parser.add_argument(
        "--run-one",
        type=int,
        default=None,
        metavar="INDEX",
        help="Process only row INDEX (0-based). For Slurm array jobs: --run-one $SLURM_ARRAY_TASK_ID",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="small",
        help="Whisper model size: tiny, base, small, medium, large (default: small)",
    )
    args = parser.parse_args()

    # --- Read the input CSV ---
    if not args.csv.exists():
        log.error("CSV file not found: %s", args.csv)
        sys.exit(1)

    with open(args.csv, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    log.info("Loaded %d episodes from %s", len(rows), args.csv)

    # --- If --run-one is set, process only that row ---
    if args.run_one is not None:
        if args.run_one < 0 or args.run_one >= len(rows):
            log.error(
                "Index %d out of range (CSV has %d rows, valid range 0-%d)",
                args.run_one, len(rows), len(rows) - 1,
            )
            sys.exit(1)
        rows = [rows[args.run_one]]
        log.info("--run-one %d: processing single episode", args.run_one)

    # --- Load the Whisper model ---
    log.info("Loading Whisper model '%s' ...", args.model)
    model = whisper.load_model(args.model)
    log.info("Model loaded.")

    # --- Transcribe each episode ---
    success = 0
    fail = 0

    for i, row in enumerate(rows):
        json_name = row["json_name"]
        new_title = row["new_title"]

        log.info("[%d/%d] %s / %s", i + 1, len(rows), json_name, new_title)

        ok = transcribe_episode(model, json_name, new_title)
        if ok:
            success += 1
        else:
            fail += 1

    # --- Summary ---
    log.info("=" * 60)
    log.info("Done.  success=%d  failed=%d  total=%d", success, fail, len(rows))

    if fail > 0:
        log.warning("%d episodes failed — check logs above for details", fail)
        sys.exit(1)


if __name__ == "__main__":
    main()
