"""
28_label_noise.py  --  label-perturbation robustness grid for H1/H2 (complements the
PROBABILITY mass-transfer grid 19). Two families of perturbation applied to the discrete
stance LABELS of mentioned Russia / Ukraine sentences, then panels are re-aggregated and
H1 (pre-payment level) + H2 (TWFE DiD) re-estimated:

  (A) DETERMINISTIC recodes: neu->pos, pos->neu, neg->neu, neu->neg  (whole-class moves)
  (B) RANDOM flips: reassign 5% / 10% / 20% of mentioned labels to a DIFFERENT class
      (uniform over the other two), repeated over seeds {123,124,125}.

Label-derived outcomes only (pos rate, net ordinal) for Russia and Combined (Russia-Ukraine);
the probability-based `score` is unaffected by label moves and is covered by grid 19. Tim
Pool's three feeds are pooled to tim_pool to match the main analysis. Treatment 2023-10-01.
Output: master_labelnoise_coefs.csv   PI: Jared Edgerton (PSU). Seed 123.
"""
import numpy as np, pandas as pd, re, pyfixest as pf

SEED = 123; rng_global = np.random.default_rng(SEED)
CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = CO + "/data/sc_results"
START, TRUNC, TREAT = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01"), pd.Timestamp("2023-10-01")
TENET = {"the_benny_show","the_rubin_report","timcast_irl","tim_pool_daily_news","the_culture_war_podcast_with_tim_pool"}
TIM = {"timcast_irl","tim_pool_daily_news","the_culture_war_podcast_with_tim_pool"}
ORD = {"positive":1,"neutral":0,"negative":-1}; CLASSES = ["positive","neutral","negative"]
MINMENT = 5
def nrm(x): return re.sub(r"[^a-z0-9]","",str(x).lower())

cols = ["show","date","russia_label","ukraine_label"]
d = pd.read_parquet(SC + "/opus_c0_corpus_labeled.parquet", columns=cols)
d["date"] = pd.to_datetime(d["date"], errors="coerce"); d = d.dropna(subset=["date"])
d = d[(d.date>=START)&(d.date<TRUNC)].copy()
d["month"] = d["date"].values.astype("datetime64[M]")
d["unit"] = np.where(d["show"].isin(TIM), "tim_pool", d["show"])

aud = pd.read_csv(CO + "/data/show_data/treated_terminal_blocks_weightedDecay.csv")
aud["key"] = aud["title"].map(nrm); aud = aud.dropna(subset=["mean_audience"])
amap = dict(zip(aud.key, aud.mean_audience))
def unit_aud(u):
    if u == "tim_pool": return float(np.nansum([amap.get(nrm(s),np.nan) for s in TIM]))
    return amap.get(nrm(u), np.nan)

def recode(s, rule):
    s = s.copy()
    if rule == "neu2pos": s[s=="neutral"]="positive"
    elif rule == "pos2neu": s[s=="positive"]="neutral"
    elif rule == "neg2neu": s[s=="negative"]="neutral"
    elif rule == "neu2neg": s[s=="neutral"]="negative"
    return s
def flip(s, frac, rng):
    s = s.copy(); ment = s[s!="unmentioned"].index.to_numpy()
    k = int(round(frac*len(ment)));
    if k==0: return s
    pick = rng.choice(ment, k, replace=False)
    for i in pick:
        alt = [c for c in CLASSES if c!=s.loc[i]]; s.loc[i]=rng.choice(alt)
    return s

def build_panel(rl, ul):
    t = pd.DataFrame({"unit":d.unit,"month":d.month,"rl":rl,"ul":ul})
    t["rment"]=t.rl!="unmentioned"; t["ument"]=t.ul!="unmentioned"
    rows=[]
    for (u,m),g in t.groupby(["unit","month"]):
        rm=g[g.rment]; um=g[g.ument]
        rows.append(dict(unit=u,month=m,n_ment_r=len(rm),n_ment_u=len(um),
            r_pos=(rm.rl=="positive").mean() if len(rm) else np.nan, r_net=rm.rl.map(ORD).mean() if len(rm) else np.nan,
            u_pos=(um.ul=="positive").mean() if len(um) else np.nan, u_net=um.ul.map(ORD).mean() if len(um) else np.nan))
    p=pd.DataFrame(rows)
    p["c_pos"]=p.r_pos-p.u_pos; p["c_net"]=p.r_net-p.u_net
    minm=p.month.min(); p["t"]=((p.month-minm).dt.days/30.4375).round().astype(int); p["t2"]=p["t"]**2
    p["post"]=(p.month>=TREAT).astype(int); p["tenet"]=p.unit.isin({"tim_pool","the_benny_show","the_rubin_report"}).astype(int)
    p["tp"]=p.tenet*p.post; p["log_aud"]=np.log(p.unit.map(unit_aud)); return p

def estimate(p, tag, out):
    for st,col,wc in [("Russia","r_pos","n_ment_r"),("Russia","r_net","n_ment_r"),("Combined","c_pos","n_ment_r"),("Combined","c_net","n_ment_r")]:
        if st=="Combined": dd=p[(p.n_ment_r>=MINMENT)&(p.n_ment_u>=MINMENT)&p.log_aud.notna()&p[col].notna()].copy()
        else: dd=p[(p.n_ment_r>=MINMENT)&p.log_aud.notna()&p[col].notna()].copy()
        pre=dd[dd.post==0]
        try:
            m=pf.feols(f"{col} ~ tenet + t + t2 + log_aud", data=pre, vcov={"CRV1":"unit"}); b=m.coef()["tenet"]; pv=m.pvalue()["tenet"]
        except Exception: b,pv=np.nan,np.nan
        out.append(dict(scenario=tag,hyp="H1",set=st,metric=col.split("_")[-1],spec="OLS",est=b,p=pv))
        try:
            m=pf.feols(f"{col} ~ tp + post:log_aud | unit + month", data=dd, vcov={"CRV1":"unit"}); b=m.coef()["tp"]; pv=m.pvalue()["tp"]
        except Exception: b,pv=np.nan,np.nan
        out.append(dict(scenario=tag,hyp="H2",set=st,metric=col.split("_")[-1],spec="TWFE",est=b,p=pv))

out=[]
estimate(build_panel(d.russia_label, d.ukraine_label), "baseline", out)
for rule in ["neu2pos","pos2neu","neg2neu","neu2neg"]:
    estimate(build_panel(recode(d.russia_label,rule), recode(d.ukraine_label,rule)), f"recode_{rule}", out)
for frac in [0.05,0.10,0.20]:
    for sd in [123,124,125]:
        rng=np.random.default_rng(sd)
        estimate(build_panel(flip(d.russia_label,frac,rng), flip(d.ukraine_label,frac,rng)), f"flip{int(frac*100)}_s{sd}", out)
fin=pd.DataFrame(out)
fin["sig"]=np.where(fin.p.isna(),"NA",np.where(fin.p<0.01,"***",np.where(fin.p<0.05,"**",np.where(fin.p<0.1,"*","ns"))))
fin.to_csv(SC+"/master_labelnoise_coefs.csv", index=False)
print(fin.to_string()); print("DONE_LABELNOISE", len(fin))
