"""Merge corpus.parquet with topics.parquet into one parquet that 7_sentiment.py can read directly. Streams corpus, applies same short-sentence filter as 6_topic_model, attaches topic column via positional index."""
import logging
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('merge')
C = '/storage/group/LiberalArts/default/jfe4_collab/podcast'

log.info('loading topics.parquet')
topics = pd.read_parquet(f'{C}/data/topic_model/topics.parquet').sort_values('corpus_index').reset_index(drop=True)
log.info('topics rows: %d', len(topics))
topic_arr = topics['topic'].to_numpy()
prob_arr = topics['probability'].to_numpy()

pf = pq.ParquetFile(f'{C}/data/corpus.parquet')
writer = None
filt_pos = 0
out = f'{C}/data/corpus_with_topics.parquet'
for i, batch in enumerate(pf.iter_batches(batch_size=500_000)):
    df = batch.to_pandas()
    keep_short = df.sentence.astype(str).str.strip().str.len() >= 5
    df_filt = df[keep_short].reset_index(drop=True)
    n = len(df_filt)
    df_filt['topic'] = topic_arr[filt_pos:filt_pos+n]
    df_filt['probability'] = prob_arr[filt_pos:filt_pos+n]
    filt_pos += n
    tbl = pa.Table.from_pandas(df_filt)
    if writer is None:
        writer = pq.ParquetWriter(out, tbl.schema)
    writer.write_table(tbl)
    if i % 20 == 0:
        log.info('batch %d filt_pos=%d', i, filt_pos)
writer.close()
log.info('MERGE_DONE filt_pos=%d -> %s', filt_pos, out)
