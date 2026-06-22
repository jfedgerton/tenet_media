"""
5_build_corpus.py
Convert raw transcript .txt files into a sentence-level pandas DataFrame.

Walks transcript_key/ directory, parses filenames for metadata, splits text
into sentences via nltk, and writes data/corpus.parquet.
"""

import argparse
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import nltk
import pandas as pd

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BATCH_SIZE = 1000
FILENAME_RE = re.compile(
    r"^(?P<show>.+?)_(?P<ts>\d{14})_(?P<episode>.+)\.txt$"
)


def parse_filename(fpath: Path):
    """Extract show, date, episode_number from transcript path.

    Expected layout:
        transcript_key/{show_name}/{show}_{YYYYMMDDHHMMSS}_{episode}.txt
    """
    show_dir = fpath.parent.name
    m = FILENAME_RE.match(fpath.name)
    if m is None:
        return None
    ts_str = m.group("ts")
    try:
        date = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    episode_number = m.group("episode")
    return {
        "show": show_dir,
        "date": date,
        "episode_number": episode_number,
        "filename": str(fpath),
    }


def sentences_from_file(fpath: Path, meta: dict) -> list[dict]:
    """Read a transcript file and return a list of sentence-level records."""
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        log.warning("Could not read %s: %s", fpath, exc)
        return []

    text = text.strip()
    if not text:
        return []

    sents = nltk.sent_tokenize(text)
    records = []
    for idx, sent in enumerate(sents, start=1):
        rec = meta.copy()
        rec["sentence_id"] = idx
        rec["sentence"] = sent
        records.append(rec)
    return records


def collect_files(transcript_dir: Path) -> list[Path]:
    """Walk transcript_dir and return all .txt file paths."""
    txt_files = []
    for root, _dirs, files in os.walk(transcript_dir):
        for fname in files:
            if fname.endswith(".txt"):
                txt_files.append(Path(root) / fname)
    txt_files.sort()
    log.info("Found %d .txt files in %s", len(txt_files), transcript_dir)
    return txt_files


def process_batch(file_batch: list[Path]) -> pd.DataFrame:
    """Process a batch of files and return a DataFrame of sentences."""
    all_records = []
    skipped = 0
    for fpath in file_batch:
        meta = parse_filename(fpath)
        if meta is None:
            skipped += 1
            continue
        recs = sentences_from_file(fpath, meta)
        all_records.extend(recs)
    if skipped > 0:
        log.debug("Skipped %d files with unparseable names in this batch", skipped)
    if not all_records:
        return pd.DataFrame()
    return pd.DataFrame(all_records)


def main():
    parser = argparse.ArgumentParser(
        description="Build sentence-level corpus from transcript .txt files."
    )
    parser.add_argument(
        "--transcript-dir",
        type=str,
        default=str(PROJECT_ROOT / "transcript_key"),
        help="Root directory containing show subdirectories of .txt transcripts.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "data" / "corpus.parquet"),
        help="Output path for the corpus parquet file.",
    )
    args = parser.parse_args()

    transcript_dir = Path(args.transcript_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Transcript directory: %s", transcript_dir)
    log.info("Output path: %s", output_path)

    txt_files = collect_files(transcript_dir)
    if not txt_files:
        log.error("No .txt files found. Exiting.")
        return

    # ---- Process in batches, appending to a list of DataFrames ----
    chunks = []
    total_files = len(txt_files)
    n_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(n_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total_files)
        batch = txt_files[start:end]
        log.info(
            "Processing batch %d/%d  (files %d–%d)",
            batch_idx + 1,
            n_batches,
            start + 1,
            end,
        )
        df_batch = process_batch(batch)
        if not df_batch.empty:
            chunks.append(df_batch)

    if not chunks:
        log.error("No sentences extracted from any file. Exiting.")
        return

    corpus = pd.concat(chunks, ignore_index=True)

    # ---- Ensure correct dtypes ----
    corpus["date"] = pd.to_datetime(corpus["date"])
    corpus["sentence_id"] = corpus["sentence_id"].astype(int)

    # ---- Save ----
    corpus.to_parquet(output_path, index=False)
    log.info("Saved corpus to %s", output_path)

    # ---- Summary stats ----
    n_shows = corpus["show"].nunique()
    n_episodes = corpus.groupby(["show", "episode_number"]).ngroups
    n_sentences = len(corpus)
    date_min = corpus["date"].min()
    date_max = corpus["date"].max()

    log.info("===== Corpus summary =====")
    log.info("Total shows:      %d", n_shows)
    log.info("Total episodes:   %d", n_episodes)
    log.info("Total sentences:  %d", n_sentences)
    log.info("Date range:       %s  to  %s", date_min.date(), date_max.date())


if __name__ == "__main__":
    main()
