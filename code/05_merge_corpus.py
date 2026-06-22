"""5c_merge_corpus.py - Streaming merge of corpus_shards/*.parquet into one corpus.parquet (memory-safe via pyarrow ParquetWriter)."""
import argparse, logging
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
    writer = None
    total = 0
    for sh in shards:
        log.info('reading %s', sh)
        t = pq.read_table(sh)
        if writer is None:
            writer = pq.ParquetWriter(a.output, t.schema)
        writer.write_table(t)
        total += t.num_rows
    if writer: writer.close()
    log.info('MERGE_DONE rows=%d -> %s', total, a.output)
if __name__ == '__main__': main()
