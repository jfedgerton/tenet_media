"""11_draw_nonunion_sample.py -- two-stage (gate+stance) design: draw non-union coding strata.

Outputs to data/label_sheets_fixed/one_sentence/:
  nonunion_random_5000.csv   2,500 pre / 2,500 post Oct 2023, random non-union
  hard_negatives_1000.csv    500 pre / 500 post, near-miss lexicon matches outside the union corpus
  practice_gold_100.csv      60 union / 25 random non-union / 15 hard; disjoint from all other sheets

Seed 123. Excludes union-corpus uids and every uid in any existing label sheet.
Window 2018-01-01 to 2024-09-01, sentences >= 5 chars (same as corpus filter).
"""
import glob, re
import numpy as np, pandas as pd
import pyarrow.parquet as pq
P = '/storage/group/LiberalArts/default/jfe4_collab/podcast'
W = P + '/data/windows/one_sentence'
O = P + '/data/label_sheets_fixed/one_sentence'
SEED = 123
rng = np.random.default_rng(SEED)
HARD_RE = re.compile(r'\b(nato|wagner|lavrov|prigozhin|medvedev|bakhmut|mariupol|oligarch\w*|special military operation|minsk|belarus\w*|chernobyl|donetsk|luhansk|azov)\b', re.I)
POST = pd.Timestamp('2023-10-01')
def base(f): return str(f).rsplit('/', 1)[-1].replace('.txt', '')
def uidcol(df): return df['filename'].map(base) + '#' + df['sentence_id'].astype(int).astype(str)

rc = pd.read_parquet(W + '/russia_corpus.parquet')
union_uid = set(uidcol(rc))
ex = set()
for f in glob.glob(P + '/data/label_sheets*/one_sentence/*.csv') + glob.glob(P + '/data/label_sheets_fixed/archive_pre_twostage/*.csv'):
    try:
        d = pd.read_csv(f, low_memory=False)
    except Exception:
        continue
    if 'filename' in d.columns and 'sentence_id' in d.columns:
        ex.update(uidcol(d).tolist())
print('union uids', len(union_uid), 'prior sheet uids', len(ex), flush=True)

cols = ['show', 'date', 'episode_number', 'filename', 'sentence_id', 'sentence']
pf = pq.ParquetFile(W + '/corpus.parquet')
rand_cand, hard_cand, total = [], [], 0
KEEP_P = 0.0015
for bi, b in enumerate(pf.iter_batches(batch_size=1000000, columns=cols)):
    df = b.to_pandas(); total += len(df)
    s = df['sentence'].fillna('').astype(str)
    dt = pd.to_datetime(df['date'], errors='coerce')
    uid = uidcol(df)
    elig = (s.str.strip().str.len() >= 5) & (dt >= pd.Timestamp('2018-01-01')) & (dt < pd.Timestamp('2024-09-01')) & (~uid.isin(union_uid)) & (~uid.isin(ex))
    ish = elig & s.str.contains(HARD_RE, regex=True, na=False)
    if ish.any(): hard_cand.append(df[ish])
    r = rng.random(len(df))
    isr = elig.values & (~ish.values) & (r < KEEP_P)
    if isr.any(): rand_cand.append(df[isr])
    if bi % 20 == 0: print('batch', bi, 'total', total, flush=True)
rand = pd.concat(rand_cand, ignore_index=True).drop_duplicates(subset=['filename', 'sentence_id'])
hard = pd.concat(hard_cand, ignore_index=True).drop_duplicates(subset=['filename', 'sentence_id'])
print('candidates: random', len(rand), 'hard', len(hard), flush=True)

def strat_sample(df, n_pre, n_post):
    dt = pd.to_datetime(df['date'], errors='coerce')
    pre = df[dt < POST]; post = df[dt >= POST]
    a = pre.sample(min(n_pre, len(pre)), random_state=SEED)
    b = post.sample(min(n_post, len(post)), random_state=SEED)
    return pd.concat([a, b], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)

rand_s = strat_sample(rand, 2513, 2512)
hard_s = strat_sample(hard, 508, 507)
rand_prac = rand_s.iloc[:25]; rand_main = rand_s.iloc[25:].reset_index(drop=True)
hard_prac = hard_s.iloc[:15]; hard_main = hard_s.iloc[15:].reset_index(drop=True)

udt = pd.to_datetime(rc['date'], errors='coerce')
uelig = rc[(udt >= pd.Timestamp('2018-01-01')) & (udt < pd.Timestamp('2024-09-01')) & (~uidcol(rc).isin(ex))]
union_prac = strat_sample(uelig, 30, 30).iloc[:60]
print('drawn: rand_main', len(rand_main), 'hard_main', len(hard_main), 'practice', len(rand_prac) + len(hard_prac) + len(union_prac), flush=True)

need = pd.concat([rand_main, hard_main, rand_prac, hard_prac, union_prac], ignore_index=True)
flist = list(set(need['filename'].astype(str)))
import pyarrow.dataset as ds
tb = ds.dataset(W + '/corpus.parquet').to_table(columns=['filename', 'sentence_id', 'sentence'], filter=ds.field('filename').isin(flist)).to_pandas()
lut = {(f, int(i)): t for f, i, t in zip(tb.filename.astype(str), tb.sentence_id, tb.sentence)}
print('neighbor rows', len(tb), flush=True)

def finalize(df, prefix, stratum):
    df = df.copy().reset_index(drop=True)
    low = df['sentence'].astype(str).str.lower()
    df['kw_russia'] = low.str.contains('russia|putin|kremlin|moscow').astype(int)
    df['kw_ukraine'] = low.str.contains('ukrain|zelensk|kyiv|kiev|donbas').astype(int)
    df['prev_sentence'] = [lut.get((f, int(i) - 1), '') for f, i in zip(df.filename.astype(str), df.sentence_id)]
    df['next_sentence'] = [lut.get((f, int(i) + 1), '') for f, i in zip(df.filename.astype(str), df.sentence_id)]
    df['uid'] = uidcol(df)
    df['stratum'] = stratum
    df.insert(0, 'row_id', ['%s_%04d' % (prefix, i) for i in range(len(df))])
    for c in ['stance_russia', 'stance_ukraine', 'historical', 'uncodable', 'confidence', 'notes']: df[c] = ''
    keep = ['row_id', 'stratum', 'show', 'date', 'prev_sentence', 'sentence', 'next_sentence', 'stance_russia', 'stance_ukraine', 'historical', 'uncodable', 'confidence', 'notes', 'kw_russia', 'kw_ukraine', 'filename', 'sentence_id', 'uid']
    return df[[c for c in keep if c in df.columns]]

finalize(rand_main, 'nr', 'nonunion_random').to_csv(O + '/nonunion_random_5000.csv', index=False)
finalize(hard_main, 'hn', 'hard_negative').to_csv(O + '/hard_negatives_1000.csv', index=False)
prac = pd.concat([finalize(union_prac, 'pg_u', 'union'), finalize(rand_prac, 'pg_r', 'nonunion_random'), finalize(hard_prac, 'pg_h', 'hard_negative')], ignore_index=True)
prac = prac.sample(frac=1, random_state=SEED).reset_index(drop=True)
prac['row_id'] = ['gold_%03d' % i for i in range(len(prac))]
prac.to_csv(O + '/practice_gold_100.csv', index=False)
print('WROTE nonunion_random', len(rand_main), 'hard', len(hard_main), 'practice', len(prac), 'DONE_09W', flush=True)
