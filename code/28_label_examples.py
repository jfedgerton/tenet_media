"""
28_label_examples.py  --  reviewer-facing exhibit of the stance coding scheme.
For each target (Russia, Ukraine) and stance label (positive/negative/neutral),
pull the highest-confidence example SENTENCES from the labeled corpus so a reader
can see what the classifier calls positive vs. negative.

Memory-safe: the labeled parquet (opus_c0_corpus_labeled.parquet) carries
sentence_id + 4-class probs but NOT the text. We (1) pick the example sentence_ids
from the small labeled table, then (2) read ONLY those rows' text from the big
corpus_with_topics.parquet via a pyarrow pushdown filter -- never loading the full
corpus (which OOMs a login node).

Writes data/sc_results/tab_label_examples.{tex,csv}. Seed 123. PI: Jared Edgerton.
"""
import pandas as pd, numpy as np, re
import pyarrow.dataset as ds, pyarrow.compute as pc

CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = CO + "/data/sc_results"
CORPUS = CO + "/data/corpus_with_topics.parquet"
N_EX, MAXLEN, CAND = 4, 240, 60          # examples per cell; truncation; candidates to fetch per cell
np.random.seed(123)

lab = pd.read_parquet(SC + "/opus_c0_corpus_labeled.parquet",
                      columns=["sentence_id", "topic", "russia_label", "russia_p_pos", "russia_p_neg",
                               "ukraine_label", "ukraine_p_pos", "ukraine_p_neg"])
print("labeled rows", len(lab))

# ---- pick candidate sentence_ids per (target, label), ranked by confidence ----
picks = []   # (Target, Label, sentence_id, conf)
for target, T in [("russia", "Russia"), ("ukraine", "Ukraine")]:
    p_pos, p_neg = lab[f"{target}_p_pos"], lab[f"{target}_p_neg"]
    p_neu = (1.0 - p_pos - p_neg).clip(lower=0)
    conf = {"positive": p_pos, "negative": p_neg, "neutral": p_neu}
    lc = f"{target}_label"
    for label in ["positive", "negative", "neutral"]:
        sub = lab[lab[lc] == label]
        if sub.empty:
            continue
        top = sub.assign(__c=conf[label].loc[sub.index]).nlargest(CAND, "__c")
        for sid, c in zip(top["sentence_id"], top["__c"]):
            picks.append((T, label, sid, float(c)))
P = pd.DataFrame(picks, columns=["Target", "Label", "sentence_id", "conf"])
want_ids = P["sentence_id"].unique().tolist()
print("candidate sentence_ids", len(want_ids))

# ---- fetch ONLY those sentences' text (pushdown filter; memory-light) ----------
dset = ds.dataset(CORPUS, format="parquet")
tbl = dset.to_table(columns=["sentence_id", "sentence"],
                    filter=pc.is_in(ds.field("sentence_id"), value_set=__import__("pyarrow").array(want_ids)))
txt = tbl.to_pandas().drop_duplicates("sentence_id").set_index("sentence_id")["sentence"]
print("fetched texts", len(txt))
P["Sentence"] = P["sentence_id"].map(txt)

# ---- assemble: clean, dedup, keep top N per cell --------------------------------
rows = []
for (T, label), g in P.dropna(subset=["Sentence"]).groupby(["Target", "Label"], sort=False):
    seen, kept = set(), 0
    for _, r in g.sort_values("conf", ascending=False).iterrows():
        s = re.sub(r"\s+", " ", str(r.Sentence)).strip()
        if len(s) < 25 or s.lower() in seen:
            continue
        seen.add(s.lower())
        if len(s) > MAXLEN:
            s = s[:MAXLEN].rsplit(" ", 1)[0] + "..."
        rows.append(dict(Target=T, Label=label.capitalize(), Confidence=round(r.conf, 3), Sentence=s))
        kept += 1
        if kept >= N_EX:
            break
EX = pd.DataFrame(rows)
EX.to_csv(SC + "/tab_label_examples.csv", index=False)
print("examples:", len(EX), "\n", EX.groupby(["Target", "Label"]).size())

# ---- LaTeX --------------------------------------------------------------------
def esc(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s
out = [r"% requires \usepackage{booktabs}", r"\begin{table}[!ht]\centering",
       r"\caption{Stance coding scheme with highest-confidence example sentences (canonical \texttt{full\_opus\_patched} run). `Conf.' is the model's class probability.}",
       r"\label{tab:label_examples}", r"\small", r"\begin{tabular}{l l c p{0.60\textwidth}}", r"\toprule",
       r"Target & Stance & Conf. & Example sentence \\", r"\midrule"]
prev = None
for _, r in EX.iterrows():
    if r.Target != prev and prev is not None: out.append(r"\midrule")
    tgt = r.Target if r.Target != prev else ""; prev = r.Target
    out.append(f"{tgt} & {r.Label} & {r.Confidence:.2f} & {esc(r.Sentence)} \\\\")
out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
open(SC + "/tab_label_examples.tex", "w").write("\n".join(out))
print("WROTE tab_label_examples.{csv,tex}")
