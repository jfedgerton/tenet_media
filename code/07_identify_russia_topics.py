"""Build a Russia/Ukraine class: union of (a) sentences in Topics 78, 79 and (b) sentences matching Russia keyword regex. Writes data/russia_corpus.parquet."""
import re, logging
import pyarrow.parquet as pq
import pandas as pd
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('russia')
C = '/storage/group/LiberalArts/default/jfe4_collab/podcast'
RUSSIA_TOPICS = {78, 79}
KW_RE = re.compile(r'\b(russia|russian|russians|ukrain\w*|putin|kyiv|kiev|donbas|crimea|zelensky|moscow|kremlin|soviet)\b', re.IGNORECASE)

log.info('loading topics.parquet')
topics = pd.read_parquet(f'{C}/data/topic_model/topics.parquet')
topic_idx = set(topics[topics.topic.isin(RUSSIA_TOPICS)].corpus_index.tolist())
log.info('topic 78/79 corpus_indexes: %d', len(topic_idx))

pf = pq.ParquetFile(f'{C}/data/corpus.parquet')
kw_chunks = []
filt_pos = 0
topic_hits = []
for i, batch in enumerate(pf.iter_batches(batch_size=500_000)):
    df = batch.to_pandas()
    keep_short = df.sentence.astype(str).str.strip().str.len() >= 5
    df_filt = df[keep_short].reset_index(drop=True)
    df_filt['corpus_index'] = range(filt_pos, filt_pos + len(df_filt))
    filt_pos += len(df_filt)
    in_kw = df_filt.sentence.astype(str).str.contains(KW_RE, regex=True, na=False)
    in_topic = df_filt.corpus_index.isin(topic_idx)
    keep = in_kw | in_topic
    if keep.any():
        sub = df_filt[keep].copy()
        sub['from_topic_78_79'] = in_topic[keep].values
        sub['from_keyword'] = in_kw[keep].values
        kw_chunks.append(sub)
    if i % 20 == 0:
        kept = sum(len(c) for c in kw_chunks)
        log.info('batch %d (filt_pos=%d) kept_so_far=%d', i, filt_pos, kept)

result = pd.concat(kw_chunks, ignore_index=True)
log.info('Russia class total: %d sentences', len(result))
log.info('  topic-only: %d', ((result.from_topic_78_79) & (~result.from_keyword)).sum())
log.info('  keyword-only: %d', ((~result.from_topic_78_79) & (result.from_keyword)).sum())
log.info('  both: %d', ((result.from_topic_78_79) & (result.from_keyword)).sum())
result.to_parquet(f'{C}/data/russia_corpus.parquet', index=False)
log.info('wrote %s/data/russia_corpus.parquet', C)
