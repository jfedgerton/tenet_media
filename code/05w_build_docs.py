"""
05w_build_docs.py -- Windowed document builder (generalizes 05_build_corpus_shard.py).

Splits each transcript into sentences with nltk, then groups every W consecutive
sentences (non-overlapping) within an episode into ONE document. W=1 reproduces
the original sentence-level corpus exactly.

Output schema is IDENTICAL to 05_build_corpus_shard.py
    (show, date, episode_number, filename, sentence_id, sentence)
so that 06_topic_model.py, 07_identify_russia_topics_windowed.py, the stance
pipeline, and the panels all run UNCHANGED -- the "sentence" column simply holds
a W-sentence document, and "sentence_id" is the document index within the episode.
An extra column n_sent records how many sentences each document contains.

Usage (sharded, memory-safe, like 05):
    python 05w_build_docs.py --window 3 --transcript_dir $C/transcript_key \
        --output $C/data/corpus_shards_w3/corpus_part_0000.parquet --start 0 --end 1000
"""
import argparse, logging, os, re
from datetime import datetime
from pathlib import Path
import nltk, pandas as pd

nltk.data.path.insert(0, "/storage/home/jfe4/nltk_data")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("docs")

FILENAME_RE = re.compile(r"^(?P<show>.+?)_(?P<ts>\d{14})_(?P<episode>.+)\.txt$")


def parse_filename(fpath):
    m = FILENAME_RE.match(fpath.name)
    if m is None:
        return None
    try:
        date = datetime.strptime(m.group("ts"), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return {"show": fpath.parent.name, "date": date,
            "episode_number": m.group("episode"), "filename": str(fpath)}


def docs_from_file(fpath, meta, window):
    """Sentence-split, then group every `window` sentences into one document."""
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        log.warning("read fail %s: %s", fpath, e)
        return []
    if not text:
        return []
    sents = nltk.sent_tokenize(text)
    out = []
    doc_id = 0
    for i in range(0, len(sents), window):        # non-overlapping chunks
        chunk = sents[i:i + window]
        doc_id += 1
        r = meta.copy()
        r["sentence_id"] = doc_id
        r["sentence"] = " ".join(chunk)
        r["n_sent"] = len(chunk)
        out.append(r)
    return out


def collect_files(d):
    out = []
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".txt"):
                out.append(Path(root) / f)
    out.sort()
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--window", type=int, required=True, choices=[1, 3, 5],
                   help="Sentences per document (1, 3, or 5).")
    p.add_argument("--transcript_dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
    a = p.parse_args()

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files(Path(a.transcript_dir))
    log.info("total files: %d  (window=%d)", len(files), a.window)
    s, e = max(0, a.start), min(len(files), a.end)
    shard = files[s:e]
    log.info("shard [%d:%d) = %d files -> %s", s, e, len(shard), out)

    recs, ndone, nskip = [], 0, 0
    for fp in shard:
        meta = parse_filename(fp)
        if meta is None:
            nskip += 1
            continue
        recs.extend(docs_from_file(fp, meta, a.window))
        ndone += 1
        if ndone % 500 == 0:
            log.info("processed %d/%d (skipped %d, docs so far %d)",
                     ndone, len(shard), nskip, len(recs))

    cols = ["show", "date", "episode_number", "filename", "sentence_id", "sentence", "n_sent"]
    if not recs:
        df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(recs)
        df["date"] = pd.to_datetime(df["date"])
        df["sentence_id"] = df["sentence_id"].astype("int32")
        df["n_sent"] = df["n_sent"].astype("int16")
    df.to_parquet(out, index=False)
    log.info("DOCS_DONE window=%d files=%d skipped=%d docs=%d -> %s",
             a.window, ndone, nskip, len(df), out)


if __name__ == "__main__":
    main()
