import pandas as pd, glob
import pyarrow.dataset as ds
P='/storage/group/LiberalArts/default/jfe4_collab/podcast'
W=P+'/data/windows/one_sentence'
O=P+'/data/label_sheets_fixed/one_sentence'
rc=pd.read_parquet(W+'/russia_corpus.parquet')
def base(f): return str(f).rsplit('/',1)[-1].replace('.txt','')
rc['uid']=rc['filename'].map(base)+'#'+rc['sentence_id'].astype(int).astype(str)
dt=pd.to_datetime(rc['date'],errors='coerce')
inwin=(dt>=pd.Timestamp('2018-01-01'))&(dt<pd.Timestamp('2024-09-01'))
print('corpus',len(rc),'in-window',inwin.sum(),'bad dates',dt.isna().sum(),flush=True)
ex=set()
for f in glob.glob(P+'/data/label_sheets*/one_sentence/label_*.csv')+[O+'/icr_batch_200.csv',O+'/icr_supplement_200.csv']:
    d=pd.read_csv(f)
    if 'filename' in d.columns and 'sentence_id' in d.columns:
        ex.update((d['filename'].map(base)+'#'+d['sentence_id'].astype(int).astype(str)).tolist())
print('exclusion uids',len(ex),flush=True)
pool=rc[inwin&(~rc['uid'].isin(ex))]
print('pool',len(pool),flush=True)
s=pool.sample(4000,random_state=123).reset_index(drop=True)
low=s['sentence'].astype(str).str.lower()
s['kw_russia']=low.str.contains('russia|putin|kremlin|moscow').astype(int)
s['kw_ukraine']=low.str.contains('ukrain|zelensk|kyiv|kiev|donbas').astype(int)
flist=list(set(s['filename'].astype(str)))
d2=ds.dataset(W+'/corpus.parquet')
tb=d2.to_table(columns=['filename','sentence_id','sentence'],filter=ds.field('filename').isin(flist)).to_pandas()
print('neighbor rows',len(tb),flush=True)
lut={(f,int(i)):t for f,i,t in zip(tb.filename.astype(str),tb.sentence_id,tb.sentence)}
chk=sum(1 for f,i,t in zip(s.filename.astype(str),s.sentence_id,s.sentence) if lut.get((f,int(i)))!=t)
print('self-lookup mismatches',chk,flush=True)
s['prev_sentence']=[lut.get((f,int(i)-1),'') for f,i in zip(s.filename.astype(str),s.sentence_id)]
s['next_sentence']=[lut.get((f,int(i)+1),'') for f,i in zip(s.filename.astype(str),s.sentence_id)]
s.insert(0,'row_id',['rc_%04d'%i for i in range(len(s))])
for c in ['stance_russia','stance_ukraine','historical','uncodable','confidence','notes']: s[c]=''
keep=['row_id','show','date','prev_sentence','sentence','next_sentence','stance_russia','stance_ukraine','historical','uncodable','confidence','notes','kw_russia','kw_ukraine','filename','sentence_id','uid']
keep=[c for c in keep if c in s.columns]
s[keep].to_csv(O+'/recode_4000.csv',index=False)
blob=(s['sentence'].astype(str).str.len()>5000).sum()
print('WROTE',len(s),'prev filled',(s.prev_sentence!='').sum(),'next filled',(s.next_sentence!='').sum(),'blob sentences',blob,flush=True)
