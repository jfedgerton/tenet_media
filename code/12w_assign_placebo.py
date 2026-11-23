"""12w_assign_placebo.py -- split the four placebo label pools (big_tech, china,
supreme_court, disney; 500 each) into the same three coder pair-parts (A-B, B-C, A-C),
balanced within target, every sentence coded twice. Separate files from the main split
because the placebo codebook has a single stance column.
Writes assignments/placebo_assignment_master.csv and placebo_coder_A/B/C.csv. Seed 123.
"""
import numpy as np, pandas as pd
from pathlib import Path
P = '/storage/group/LiberalArts/default/jfe4_collab/podcast'
O = P + '/data/label_sheets_fixed/one_sentence'
A = Path(P + '/data/label_sheets_fixed/assignments'); A.mkdir(parents=True, exist_ok=True)
SEED = 123
rng = np.random.default_rng(SEED)
TARGETS = ['big_tech', 'china', 'supreme_court', 'disney']
frames = []
for t in TARGETS:
    d = pd.read_csv(O + '/label_%s.csv' % t, low_memory=False)
    d['target'] = t
    frames.append(d)
alld = pd.concat(frames, ignore_index=True, sort=False)
alld['uid'] = alld['filename'].astype(str).str.rsplit('/', n=1).str[-1].str.replace('.txt', '', regex=False) + '#' + alld['sentence_id'].astype(int).astype(str) + '@' + alld['target']
assert alld['uid'].is_unique, 'duplicate uid within a target'
print('combined', len(alld), alld['target'].value_counts().to_dict(), flush=True)
part = pd.Series(0, index=alld.index)
for t, g in alld.groupby('target'):
    idx = g.index.to_numpy(); rng.shuffle(idx)
    lab = np.tile([1, 2, 3], len(idx) // 3 + 1)[:len(idx)]
    part.loc[idx] = lab
alld['part'] = part
PAIRS = {1: 'A+B', 2: 'B+C', 3: 'A+C'}
alld['pair'] = alld['part'].map(PAIRS)
alld[['uid', 'row_id', 'target', 'part', 'pair']].to_csv(A / 'placebo_assignment_master.csv', index=False)
codecols = ['stance', 'uncodable', 'confidence', 'notes']
keep = ['row_id', 'target', 'show', 'date', 'prev_sentence', 'sentence', 'next_sentence'] + codecols + ['filename', 'sentence_id', 'uid']
for coder in 'ABC':
    sub = alld[alld['pair'].str.contains(coder)].copy()
    for c in codecols: sub[c] = ''
    sub = sub[[c for c in keep if c in sub.columns]].sample(frac=1, random_state=SEED + ord(coder)).reset_index(drop=True)
    sub.insert(0, 'coder', coder)
    sub.to_csv(A / ('placebo_coder_%s.csv' % coder), index=False)
    print('coder', coder, len(sub), sub['target'].value_counts().to_dict(), flush=True)
print('parts', alld['part'].value_counts().to_dict(), 'DONE_12W', flush=True)
