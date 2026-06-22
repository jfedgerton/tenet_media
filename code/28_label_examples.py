"""
28_label_examples.py  --  reviewer-facing exhibit of the stance coding scheme.
For each target (Russia, Ukraine) and each stance label (positive / negative /
neutral), pull the highest-confidence example SENTENCES from the labeled corpus
so a reader can see exactly what the classifier calls positive vs. negative.

Reads  data/sc_results/opus_c0_corpus_labeled.parquet  (canonical full_opus_patched
labels + 4-class probabilities). If that file has no sentence-text column, it
joins to data/corpus_with_topics.parquet on a shared sentence id.

Writes data/sc_results/tab_label_examples.{tex,csv}.
Seed 123. PI: Jared Edgerton (PSU).
"""
import pandas as pd, numpy as np, re, sys

CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = CO + "/data/sc_results"
N_EX   = 4          # examples per (target, label)
MAXLEN = 240        # truncate long sentences
RNG = np.random.default_rng(123)

lab = pd.read_parquet(SC + "/opus_c0_corpus_labeled.parquet")
print("labeled cols:", list(lab.columns))

# ---- locate the sentence text -------------------------------------------------
TEXT_CANDS = ["sentence", "text", "sentence_text", "body", "utterance", "clean_text", "sent"]
ID_CANDS   = ["sentence_id", "sent_id", "uid", "id", "idx", "row_id"]
text_col = next((c for c in TEXT_CANDS if c in lab.columns), None)
if text_col is None:
    cw = pd.read_parquet(CO + "/data/corpus_with_topics.parquet")
    cwt = next((c for c in TEXT_CANDS if c in cw.columns), None)
    key = next((c for c in ID_CANDS if c in lab.columns and c in cw.columns), None)
    if cwt is None:
        sys.exit("FATAL: no text column in corpus_with_topics either; columns=%s" % list(cw.columns))
    if key is None:
        # fall back to positional alignment only if row counts match (sharded build keeps order)
        if len(cw) == len(lab):
            lab = lab.reset_index(drop=True); lab["__text"] = cw[cwt].values; text_col = "__text"
            print("joined text by row position (equal length)")
        else:
            sys.exit("FATAL: no shared id and lengths differ (%d vs %d)" % (len(lab), len(cw)))
    else:
        lab = lab.merge(cw[[key, cwt]].rename(columns={cwt: "__text"}), on=key, how="left"); text_col = "__text"
        print("joined text on key:", key)
print("using text column:", text_col)

# ---- probability columns: derive p_neu where possible -------------------------
def prob(target, k):  # returns Series or None
    c = f"{target}_p_{k}"; return lab[c] if c in lab.columns else None

rows = []
for target, T in [("russia", "Russia"), ("ukraine", "Ukraine")]:
    lc = f"{target}_label"
    p_pos, p_neg = prob(target, "pos"), prob(target, "neg")
    p_neu = prob(target, "neu")
    if p_neu is None and p_pos is not None and p_neg is not None:
        p_neu = (1.0 - p_pos - p_neg).clip(lower=0)
    conf = {"positive": p_pos, "negative": p_neg, "neutral": p_neu}
    for label in ["positive", "negative", "neutral"]:
        sub = lab[lab[lc] == label].copy()
        if sub.empty:
            continue
        c = conf[label]
        if c is not None:
            sub = sub.assign(__conf=c.loc[sub.index].values).sort_values("__conf", ascending=False)
        else:
            sub = sub.assign(__conf=np.nan)
        seen = set(); picked = 0
        for _, r in sub.iterrows():
            txt = re.sub(r"\s+", " ", str(r[text_col])).strip()
            if len(txt) < 25 or txt.lower() in seen:    # skip stubs/dups
                continue
            seen.add(txt.lower())
            if len(txt) > MAXLEN: txt = txt[:MAXLEN].rsplit(" ", 1)[0] + "..."
            rows.append(dict(Target=T, Label=label.capitalize(),
                             Confidence=round(float(r["__conf"]), 3) if pd.notna(r["__conf"]) else np.nan,
                             Sentence=txt))
            picked += 1
            if picked >= N_EX: break

EX = pd.DataFrame(rows)
EX.to_csv(SC + "/tab_label_examples.csv", index=False)
print("examples:", len(EX), "\n", EX.groupby(["Target", "Label"]).size())

# ---- LaTeX --------------------------------------------------------------------
def esc(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s

out = [r"% requires \usepackage{booktabs}",
       r"\begin{table}[!ht]\centering",
       r"\caption{Stance coding scheme with highest-confidence example sentences from the labeled corpus (canonical \texttt{full\_opus\_patched} run). `Conf.' is the model's class probability.}",
       r"\label{tab:label_examples}", r"\small",
       r"\begin{tabular}{l l c p{0.62\textwidth}}", r"\toprule",
       r"Target & Stance & Conf. & Example sentence \\", r"\midrule"]
prev_t = None
for _, r in EX.iterrows():
    tgt = r.Target if r.Target != prev_t else ""
    if r.Target != prev_t and prev_t is not None: out.append(r"\midrule")
    prev_t = r.Target
    conf = "" if pd.isna(r.Confidence) else f"{r.Confidence:.2f}"
    out.append(f"{tgt} & {r.Label} & {conf} & {esc(r.Sentence)} \\\\")
out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
open(SC + "/tab_label_examples.tex", "w").write("\n".join(out))
print("WROTE tab_label_examples.{csv,tex}")
