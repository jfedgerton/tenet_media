import logging
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("wb")
BASE=Path("/storage/group/LiberalArts/default/jfe4_collab/podcast/data/label_sheets_fixed")
OUT=BASE/"workbooks"; OUT.mkdir(parents=True,exist_ok=True)

ru1=pd.concat([pd.read_csv(BASE/"one_sentence/label_russia.csv"),
               pd.read_csv(BASE/"one_sentence/label_ukraine.csv")], ignore_index=True)
ru1["source_topic"]=ru1["target"]; ru1["target"]="russia_ukraine"
ru1=ru1.sample(frac=1,random_state=123).reset_index(drop=True)
ru1["row_id"]=[f"ru1_{i:04d}" for i in range(len(ru1))]

TARGETS = [
 ("russia_ukraine",       ru1,                                          ["stance_russia","stance_ukraine"]),
 ("supreme_court",        BASE/"one_sentence/label_supreme_court.csv",  ["stance"]),
 ("china",                BASE/"one_sentence/label_china.csv",          ["stance"]),
 ("big_tech",             BASE/"one_sentence/label_big_tech.csv",       ["stance"]),
 ("russia_ukraine_3sent", BASE/"three_sentence/label_russia_ukraine.csv",["stance_russia","stance_ukraine"]),
]
STANCE_OPTS='"positive,neutral,negative,unmentioned"'; UNC_OPTS='"0,1"'; CONF_OPTS='"high,med,low"'
HDR=Font(bold=True,color="FFFFFF"); HDRFILL=PatternFill("solid",fgColor="365F91")
WRAP=Alignment(wrap_text=True,vertical="top")

def split(df):
    n=len(df); k=int(round(n*0.2)); ov=df.iloc[:k]; rest=df.iloc[k:]; half=len(rest)//2
    a=pd.concat([ov, rest.iloc[:half]]).sample(frac=1,random_state=123).reset_index(drop=True)
    b=pd.concat([ov, rest.iloc[half:]]).sample(frac=1,random_state=123).reset_index(drop=True)
    return a,b

def add_sheet(wb, name, df, stance_cols):
    ws=wb.create_sheet(name[:31])
    has_src = "source_topic" in df.columns
    disp=["row_id"]+(["source_topic"] if has_src else [])+["show","date","prev_sentence","sentence","next_sentence"]+stance_cols+["uncodable","confidence","notes","filename","sentence_id"]
    ws.append(disp)
    for j in range(1,len(disp)+1):
        ws.cell(1,j).font=HDR; ws.cell(1,j).fill=HDRFILL
    for _,r in df.iterrows():
        row=[]
        for c in disp:
            if c in stance_cols or c in ("uncodable","confidence","notes"): row.append("")
            elif c=="date": row.append(str(r.get("date","")))
            else: row.append(r.get(c,""))
        ws.append(row)
    nrow=ws.max_row
    W={"row_id":14,"source_topic":12,"show":18,"date":12,"prev_sentence":40,"sentence":55,"next_sentence":40,"uncodable":10,"confidence":11,"notes":22,"filename":22,"sentence_id":10}
    for j,c in enumerate(disp,1): ws.column_dimensions[get_column_letter(j)].width=W.get(c,13)
    for c in ["prev_sentence","sentence","next_sentence"]:
        col=get_column_letter(disp.index(c)+1)
        for row in range(2,nrow+1): ws[f"{col}{row}"].alignment=WRAP
    dv_s=DataValidation(type="list",formula1=STANCE_OPTS,allow_blank=True)
    dv_u=DataValidation(type="list",formula1=UNC_OPTS,allow_blank=True)
    dv_c=DataValidation(type="list",formula1=CONF_OPTS,allow_blank=True)
    ws.add_data_validation(dv_s); ws.add_data_validation(dv_u); ws.add_data_validation(dv_c)
    for sc in stance_cols:
        col=get_column_letter(disp.index(sc)+1); dv_s.add(f"{col}2:{col}{nrow}")
    uc=get_column_letter(disp.index("uncodable")+1); dv_u.add(f"{uc}2:{uc}{nrow}")
    cc=get_column_letter(disp.index("confidence")+1); dv_c.add(f"{cc}2:{cc}{nrow}")
    ws.freeze_panes="A2"

def readme(wb,coder):
    ws=wb.create_sheet("README",0)
    lines=[
     [f"Stance labeling workbook - Coder {coder}"],
     ["Tenet Media / foreign-influence podcast project (PI: Jared Edgerton)"],
     [""],
     ["Code the SENTENCE column's stance toward the sheet's target. Use prev/next only for context."],
     ["stance = positive | neutral | negative | unmentioned (dropdown). Code POSITION, not tone."],
     ["  positive = supportive/defending/favorable ; negative = critical/hostile/blaming"],
     ["  neutral = target is mentioned/relevant but the sentence takes no side ; unmentioned = target not referenced in the sentence"],
     ["uncodable = 1 only for non-English or transcription garbage. confidence = high|med|low."],
     [""],
     ["russia_ukraine (one-sentence) and russia_ukraine_3sent: code BOTH stance_russia AND stance_ukraine on every row (the other is often unmentioned)."],
     ["Placebos (supreme_court, china, big_tech): NO expected direction - code what the sentence says."],
     ["Codebooks: stance_codebook.md (Russia/Ukraine) and stance_codebook_placebo_entities.md (placebos)."],
     ["Do not compare specific items with the other coder until the reliability pilot is reconciled."],
    ]
    for ln in lines: ws.append(ln)
    ws["A1"].font=Font(bold=True,size=14); ws.column_dimensions["A"].width=120

for coder in ["A","B"]:
    wb=Workbook(); wb.remove(wb.active)
    for name,src,scols in TARGETS:
        df = src if isinstance(src,pd.DataFrame) else (pd.read_csv(src) if src.exists() else None)
        if df is None: log.warning("missing %s", src); continue
        a,b=split(df); add_sheet(wb, name, a if coder=="A" else b, scols)
    readme(wb,coder)
    fn=OUT/f"stance_labeling_coder_{coder}.xlsx"; wb.save(fn); log.info("wrote %s", fn)
log.info("DONE")

