import pandas as pd, glob
import pyarrow.dataset as ds
P='/storage/group/LiberalArts/default/jfe4_collab/podcast'
W=P+'/data/windows/one_sentence'
O=P+'/data/label_sheets_fixed/one_sentence'
rc=pd.read_parquet(W+'/russia_corpus.parquet')
low=rc['sentence'].astype(str).str.lower()
ru=low.str.contains('russia|putin|kremlin|moscow')
ua=low.str.contains('ukrain|zelensk|kyiv|kiev|donbas')
rc['target']=None
rc.loc[ua,'target']='ukraine'
rc.loc[ru,'target']='russia'
def base(f): return str(f).rsplit('/',1)[-1].replace('.txt','')
rc['uid']=rc['filename'].map(base)+'#'+rc['sentence_id'].astype(int).astype(str)
ex=set()
for f in glob.glob(P+'/data/label_sheets*/one_sentence/label_*.csv')+glob.glob(P+'/**/*freshtest*.csv',recursive=True):
    try:
        d=pd.read_csv(f)
        if 'filename' in d.columns and 'sentence_id' in d.columns:
            ex.update((d['filename'].map(base)+'#'+d['sentence_id'].astype(int).astype(str)).tolist())
    except Exception as e: print('skip',f,e,flush=True)
print('exclusion uids',len(ex),flush=True)
pool=rc[(~rc['uid'].isin(ex))&rc.target.notna()]
out=[]
for t in ['russia','ukraine']:
    g=pool[pool.target==t]
    print(t,'pool',len(g),flush=True)
    out.append(g.sample(100,random_state=123))
s=pd.concat(out).sample(frac=1,random_state=123).reset_index(drop=True)
flist=list(set(s['filename'].astype(str)))
d=ds.dataset(W+'/corpus.parquet')
tb=d.to_table(columns=['filename','sentence_id','sentence'],filter=ds.field('filename').isin(flist)).to_pandas()
print('neighbor rows loaded',len(tb),flush=True)
lut={(f,int(i)):t for f,i,t in zip(tb.filename.astype(str),tb.sentence_id,tb.sentence)}
chk=sum(1 for f,i,t in zip(s.filename.astype(str),s.sentence_id,s.sentence) if lut.get((f,int(i)))!=t)
print('self-lookup mismatches',chk,flush=True)
s['prev_sentence']=[lut.get((f,int(i)-1),'') for f,i in zip(s.filename.astype(str),s.sentence_id)]
s['next_sentence']=[lut.get((f,int(i)+1),'') for f,i in zip(s.filename.astype(str),s.sentence_id)]
s.insert(0,'row_id',['icr_%04d'%i for i in range(len(s))])
for c in ['stance_russia','stance_ukraine','historical','uncodable','confidence','notes']: s[c]=''
keep=['row_id','target','show','date','prev_sentence','sentence','next_sentence','stance_russia','stance_ukraine','historical','uncodable','confidence','notes','filename','sentence_id','uid']
s[keep].to_csv(O+'/icr_batch_200.csv',index=False)
print('WROTE',len(s),'prev filled',(s.prev_sentence!='').sum(),'next filled',(s.next_sentence!='').sum(),flush=True)
