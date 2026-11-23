"""06_merge_windows.py (restored from 05_merge_corpus.py, deleted in 989f0a9 but still called by the corpus chain) - Streaming merge of corpus_shards/*.parquet into one corpus.parquet (memory-safe via pyarrow ParquetWriter)."""
import argparse, logging, os
from pathlib import Path
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)-8s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('merge')
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shards_dir', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    shards = sorted(Path(a.shards_dir).glob('corpus_part_*.parquet'))
    log.info('merging %d shards -> %s', len(shards), a.output)
    if not shards:
        raise SystemExit('no shards')
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    out = Path(a.output)
    tmp = out.with_name(out.name + '.partial')   # write here; replace the real output only after a clean close
    if tmp.exists(): tmp.unlink()
    writer = None
    total = 0
    try:
        for sh in shards:
            log.info('reading %s', sh)
            t = pq.read_table(sh)
            if writer is None:
                writer = pq.ParquetWriter(str(tmp), t.schema)
            writer.write_table(t)
            total += t.num_rows
        writer.close(); writer = None
        os.replace(tmp, out)                     # atomic on the same filesystem; old output kept until here
    except BaseException:
        if writer is not None:
            try: writer.close()
            except Exception: pass
        if tmp.exists(): tmp.unlink()
        log.error('merge failed; %s left unchanged', out)
        raise
    log.info('MERGE_DONE rows=%d -> %s', total, a.output)
if __name__ == '__main__': main()
