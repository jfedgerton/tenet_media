"""5b_build_corpus_shard.py - Sharded sentence-level corpus build. Processes files [start:end) from sorted transcript_key listing and writes one parquet shard. Reuses the parse/sentence-split logic of 5_build_corpus.py."""
import argparse, logging, os, re
from datetime import datetime
from pathlib import Path
import nltk, pandas as pd
nltk.data.path.insert(0, '/storage/home/jfe4/nltk_data')
logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)-8s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('shard')
FILENAME_RE = re.compile(r'^(?P<show>.+?)_(?P<ts>\d{14})_(?P<episode>.+)\.txt$')
def parse_filename(fpath):
    m = FILENAME_RE.match(fpath.name)
    if m is None: return None
    try: date = datetime.strptime(m.group('ts'), '%Y%m%d%H%M%S')
    except ValueError: return None
    return {'show': fpath.parent.name, 'date': date, 'episode_number': m.group('episode'), 'filename': str(fpath)}
def sentences_from_file(fpath, meta):
    try: text = fpath.read_text(encoding='utf-8', errors='replace').strip()
    except Exception as e:
        log.warning('read fail %s: %s', fpath, e); return []
    if not text: return []
    out = []
    for i, s in enumerate(nltk.sent_tokenize(text), start=1):
        r = meta.copy(); r['sentence_id'] = i; r['sentence'] = s; out.append(r)
    return out
def collect_files(d):
    out = []
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith('.txt'): out.append(Path(root)/f)
    out.sort()
    return out
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--transcript_dir', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--start', type=int, required=True)
    p.add_argument('--end', type=int, required=True)
    a = p.parse_args()
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    log.info('collecting files in %s', a.transcript_dir)
    files = collect_files(Path(a.transcript_dir))
    log.info('total files: %d', len(files))
    s, e = max(0, a.start), min(len(files), a.end)
    shard = files[s:e]
    log.info('shard [%d:%d) = %d files -> %s', s, e, len(shard), out)
    recs, ndone, nskip = [], 0, 0
    for fp in shard:
        meta = parse_filename(fp)
        if meta is None:
            nskip += 1; continue
        recs.extend(sentences_from_file(fp, meta))
        ndone += 1
        if ndone % 500 == 0:
            log.info('processed %d/%d (skipped %d, sentences so far %d)', ndone, len(shard), nskip, len(recs))
    if not recs:
        df = pd.DataFrame(columns=['show','date','episode_number','filename','sentence_id','sentence'])
    else:
        df = pd.DataFrame(recs)
        df['date'] = pd.to_datetime(df['date'])
        df['sentence_id'] = df['sentence_id'].astype('int32')
    df.to_parquet(out, index=False)
    log.info('SHARD_DONE files=%d skipped=%d sentences=%d -> %s', ndone, nskip, len(df), out)
if __name__ == '__main__': main()
