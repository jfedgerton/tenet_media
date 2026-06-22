import pandas as pd, numpy as np
SC="/storage/group/LiberalArts/default/jfe4_collab/podcast/data/sc_results"
d=pd.read_csv(SC+"/master_probshift_coefs.csv")
print("ROWS",len(d),"CELLS",d[['rus_op','ukr_op','shift']].drop_duplicates().shape[0])
order=[("H1_OLS","Russia"),("H1_OLS","Ukraine"),("H1_OLS","Combined"),
       ("H2_TWFE","Russia"),("H2_TWFE","Ukraine"),("H2_TWFE","Combined"),
       ("H1_matched","Russia"),("H1_matched","Ukraine"),("H1_matched","Combined")]
for spec,st in order:
    for met in ["score","pos","net"]:
        s=d[(d.spec==spec)&(d['set']==st)&(d.metric==met)]
        e=s.estimate.dropna()
        if len(e)==0:
            print(f"{spec:11s} {st:8s} {met:5s}  NA"); continue
        npos=int((e>0).sum()); nneg=int((e<0).sum())
        sign="all+" if npos==len(e) else ("all-" if nneg==len(e) else f"mix({npos}+/{nneg}-)")
        sig=int((s.p<0.05).sum())
        print(f"{spec:11s} {st:8s} {met:5s}  {sign:11s} med {e.median():+.3f} rng[{e.min():+.3f},{e.max():+.3f}] sig {sig}/{len(s)}")
