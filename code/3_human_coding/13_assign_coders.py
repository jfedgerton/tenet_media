"""13_assign_coders.py -- combine union (4,000) + nonunion random (5,000) + hard negatives
(1,000), split into three pair-parts (A-B, B-C, A-C) balanced within stratum, so every
sentence is coded by exactly two of three coders. Writes:
  assignments/assignment_master.csv   (uid -> part, pair)
  assignments/coder_A.csv / coder_B.csv / coder_C.csv  (each coder's full workload, shuffled)
  assignments/practice_gold_coder_X.csv is NOT needed: all three coders use practice_gold_100.csv as-is.
Seed 123.
"""
import numpy as np, pandas as pd
from pathlib import Path
P = '/storage/group/LiberalArts/default/jfe4_collab/podcast'
O = P + '/data/label_sheets_fixed/one_sentence'
A = Path(P + '/data/label_sheets_fixed/assignments'); A.mkdir(parents=True, exist_ok=True)
SEED = 123
rng = np.random.default_rng(SEED)

u = pd.read_csv(O + '/recode_4000.csv', low_memory=False)
if 'stratum' not in u.columns: u['stratum'] = 'union'
r = pd.read_csv(O + '/nonunion_random_5000.csv', low_memory=False)
h = pd.read_csv(O + '/hard_negatives_1000.csv', low_memory=False)
alld = pd.concat([u, r, h], ignore_index=True, sort=False)
assert alld['uid'].is_unique, 'duplicate uids across sheets'
print('combined', len(alld), alld['stratum'].value_counts().to_dict(), flush=True)

part = pd.Series(0, index=alld.index)
for st, g in alld.groupby('stratum'):
    idx = g.index.to_numpy(); rng.shuffle(idx)
    lab = np.tile([1, 2, 3], len(idx) // 3 + 1)[:len(idx)]
    part.loc[idx] = lab
alld['part'] = part
PAIRS = {1: 'A+B', 2: 'B+C', 3: 'A+C'}
alld['pair'] = alld['part'].map(PAIRS)
alld[['uid', 'row_id', 'stratum', 'part', 'pair']].to_csv(A / 'assignment_master.csv', index=False)

codecols = ['stance_russia', 'stance_ukraine', 'historical', 'uncodable', 'confidence', 'notes']
keep = ['row_id', 'stratum', 'show', 'date', 'prev_sentence', 'sentence', 'next_sentence'] + codecols + ['kw_russia', 'kw_ukraine', 'filename', 'sentence_id', 'uid']
for coder in 'ABC':
    sub = alld[alld['pair'].str.contains(coder)].copy()
    for c in codecols: sub[c] = ''
    sub = sub[[c for c in keep if c in sub.columns]].sample(frac=1, random_state=SEED + ord(coder)).reset_index(drop=True)
    sub.insert(0, 'coder', coder)
    sub.to_csv(A / ('coder_%s.csv' % coder), index=False)
    print('coder', coder, len(sub), sub['stratum'].value_counts().to_dict(), flush=True)
print('parts', alld['part'].value_counts().to_dict(), 'DONE_10W', flush=True)
