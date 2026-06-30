#!/usr/bin/env python3
"""After the array finishes: for each cell, merge prediction shards, build
show x month mean-stance panels (per target), and collect gold-kappa table.
Outputs: bert_out/<cell>_panel_month.csv and bert_grid_validation.csv."""
import os, glob
import numpy as np, pandas as pd
import pyarrow.parquet as pq
C=os.environ["COLLAB"]; OUTROOT=os.path.join(C,"data/sc_results/bert_out")
TEN={"tim_pool_daily_news","timcast_irl","the_culture_war_podcast_with_tim_pool","the_rubin_report","the_benny_show","benny_johnson_arena"}
TIMPOOL={"tim_pool_daily_news","timcast_irl","the_culture_war_podcast_with_tim_pool"}
TREAT=pd.Timestamp("2023-10-01")
def host(s): return "tim_pool_network" if s in TIMPOOL else ("the_benny_show" if s=="benny_johnson_arena" else s)

val=[]; cells=sorted([d for d in glob.glob(OUTROOT+"/*") if os.path.isdir(d)])
for d in cells:
    cell=os.path.basename(d)
    vf=os.path.join(d,"val.csv")
    if os.path.exists(vf): val.append(pd.read_csv(vf))
    shards=glob.glob(os.path.join(d,"preds_shard*.parquet"))
    if not shards: print("no preds for",cell); continue
    df=pd.concat([pq.read_table(s).to_pandas() for s in shards],ignore_index=True)
    df=df[df["date"].notna()].copy(); df["date"]=pd.to_datetime(df["date"])
    df["ym"]=df["date"].dt.strftime("%Y-%m-01")
    df["is_tenet"]=df["show"].isin(TEN).astype(int)
    df["host"]=df["show"].apply(host)
    rows=[]
    for tgt in ["russia","ukraine"]:
        sc=f"{tgt}_score"
        # mean stance among MENTIONED (score not nan) per host x month
        g=df.dropna(subset=[sc]).groupby(["host","ym"]).agg(
            mean_stance=(sc,"mean"), n=(sc,"size")).reset_index()
        g["target"]=tgt; rows.append(g)
    panel=pd.concat(rows,ignore_index=True)
    panel["cell"]=cell
    panel["is_tenet"]=panel["host"].isin({"tim_pool_network","the_rubin_report","the_benny_show","benny_johnson_arena"}).astype(int)
    panel["date"]=pd.to_datetime(panel["ym"]); panel["post"]=(panel["date"]>=TREAT).astype(int)
    panel.to_csv(os.path.join(OUTROOT,f"{cell}_panel_month.csv"),index=False)
    print("panel built",cell,len(panel))
if val:
    v=pd.concat(val,ignore_index=True); v.to_csv(os.path.join(OUTROOT,"bert_grid_validation.csv"),index=False)
    print("\n=== GOLD KAPPA BY CELL ==="); print(v.pivot_table(index="cell",columns="target",values="kappa").round(3))
print("DONE_AGG")
