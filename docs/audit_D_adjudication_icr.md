# GPT audit D: adjudication (step 17) and inter-coder agreement (step 18), commit 8f1b556

Everything you need is in this file. The code is pasted at the bottom.

## Context
This is a human stance-coding project (Russia/Ukraine stance in podcast sentences; plus 1,000 placebo sentences, each about one entity). There are 8,000 sentences. Each is coded by exactly two coders, listed in `coder_review/_admin/assignment_master_v2.csv` (columns row_id, block = main/placebo, grp = stratum or placebo entity, coder1, coder2, status). Usually that is the PI (Jared) plus one of three students. 94 sentences were coded by two students in Week 1. Main rows have two targets (stance_russia, stance_ukraine); placebo rows have one (stance). Codes are positive / neutral / negative / unmentioned, and a separate uncodable=1 column. Coded files are Excel workbooks in fixed locations (listed in 17's SOURCES).

## Decisions the code must implement
1. Unit = (row_id, target). A coder's code is uncodable if uncodable=1, else the normalized stance; blank means not yet coded.
2. Disagreement = the two assigned coders' codes differ. Confidence and historical are not adjudicated.
3. A coder may hold a row in two files only as Week-1 plus week_02 (Week-1 blanks re-sent; five Week-1 uncodable rows re-sent). The Week-1 code wins when filled.
4. A coder who is not assigned to a row may hold it only as a blank (a Week-1 blank the other student coded). That row is ignored. A filled code from an unassigned coder is an error.
5. The adjudication sheet is blind. Code A / Code B order is fixed per unit by a hash with seed 123, and the key goes only to _admin.
6. Decisions entered in the sheet are kept on re-run. Each decision is stamped with the two codes it was made on. If either raw code later changes, the decision is cleared and kept as previous_final_code, and the row is pending again. A decision counts only when a rule is cited.
7. Jon's audit sample has 200 adjudicated units, allocated in proportion across Russia / Ukraine / placebo (largest remainder), seed 123. It is drawn once, only when nothing is pending or incomplete, and never redrawn.
8. Step 18 computes nominal Krippendorff's alpha on raw codes (two coders, no missing within a unit), a 95% CI from 1,000 bootstrap resamples of units (seed 123, percentile), percent agreement and per-class specific agreement. The gate is mentioned vs unmentioned per main sentence (uncodable sentences excluded). Breakdowns are by target, placebo entity, stratum and coder pair.

## Already verified
- The end-to-end test passes on a full-size fake tree (15,000 units, synthetic coders right 85% of the time). It checks disagreement counts against the files, the Week-1-first rule, the blind sheet and key, A/B stability across runs, decisions kept on re-run, the raw-code-change rule, the rule requirement, and Jon's sample (drawn once, proportional). Alpha for Russia, Ukraine, placebo and the gate equals the `krippendorff` package to 1e-9. Negative tests: an unassigned coder's filled code, and a missing file, both fail.
- On the real data (only Week-1 is coded so far) it found 188 complete units from the 94 student-student sentences, with 38 disagreements. Russia alpha 0.54 (CI 0.41–0.68), Ukraine 0.52, gate 0.82. It ignored the 2 known unassigned blank rows.

## Please check
- Does 17 implement 1–7 exactly? Can any unit be counted as agreed, adjudicated or pending wrongly? Can a decision survive a raw-code change, or be lost when nothing changed?
- Edge cases: an empty disagreement set; a sheet edited by hand (rows deleted, reordered or added); a rule typed instead of picked; final_code in different case; a coder filling only one target; uncodable=1 together with a filled stance.
- Is the A/B order truly independent of who coded what, and stable? Could anything else in the sheet reveal coder identity (row order, formatting)?
- Jon's sample: is the allocation correct and the draw reproducible? Is the never-redraw rule safe if the file is deleted by mistake?
- 18: is the alpha formula correct for two coders, and the bootstrap reasonable (degenerate resamples, small n)? Is the per-class agreement formula right? Is the gate construction right?
- The test: is it independent of the code it tests? Name a concrete mutation of 17 or 18 it would miss.
- Anything that could write outside coder_review, or into coder_materials.

Report concrete bugs with file and line references first. List lower-priority suggestions separately. Do not propose new features or methods beyond what is needed to fix a bug.

## Code

### `code/3_human_coding/17_build_adjudication.py`
```python
###############################################################################
# 17_build_adjudication.py -- collect every coder's raw codes, auto-accept agreements,
# and build a BLIND A/B adjudication sheet for the PI. Seed 123. Safe to re-run any time.
#
# Unit of comparison: one (row_id, target). Main rows have two targets (russia, ukraine);
# placebo rows have one (the row's entity). A coder's code for a target is one of
#   positive | neutral | negative | unmentioned | uncodable
# where uncodable=1 overrides the stance columns. Disagreement = the two coders' codes differ
# (stance + uncodable). Confidence and historical are recorded in the raw file, not adjudicated.
#
# Rules decided Nov 23, 2026
#   - If a coder has the same row in two files (Week-1 blank re-sent in week_02, or the five
#     Week-1 uncodable rows), the Week-1 code wins when it is filled; otherwise the later one.
#   - A blank row held by a coder who is no longer assigned to it (a Week-1 blank the other student
#     coded; Emily hn_0013, rc_3195) is ignored. A filled code from an unassigned coder is an error.
#   - Coder identities are hidden. Code A / Code B order is fixed per (row_id, target) by a hash
#     with seed 123, so it never changes between runs. The key is written to _admin only.
#   - Decisions already entered in the sheet are kept on re-run. If a coder later edits a raw
#     code behind an adjudicated row, the decision is cleared (kept in previous_final_code), the row
#     turns red (changed_since_adjudicated = 1) and is pending again. A decision needs a cited rule.
#   - Jon Green's audit sample (200 adjudicated rows, spread across Russia / Ukraine / placebo in
#     proportion) is drawn once, only when nothing is pending, and is never redrawn.
#
# Usage: python3 17_build_adjudication.py <podcast_analysis_root>
# Reads  coder_materials/<student>/... , coder_review/Jared/... , coder_review/_admin/assignment_master_v2.csv
# Writes coder_review/adjudication/{adjudication_sheet.xlsx, adjudicated_final.csv, codes_raw_long.csv,
#        problems.csv, jon_audit_sample.xlsx (when complete), build_log.txt}
#        coder_review/_admin/adjudication_key.csv
# Never writes inside coder_materials.
# Test: tests/test_17_18_adjudication_icr.py
###############################################################################
import sys, os, hashlib
import numpy as np, pandas as pd, openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = sys.argv[1]
SEED = 123
CM = os.path.join(ROOT, "coder_materials")
CR = os.path.join(ROOT, "coder_review")
OUT = os.path.join(CR, "adjudication")
MASTER = os.path.join(CR, "_admin", "assignment_master_v2.csv")
KEY = os.path.join(CR, "_admin", "adjudication_key.csv")
SHEET = os.path.join(OUT, "adjudication_sheet.xlsx")
JON = os.path.join(OUT, "jon_audit_sample.xlsx")
JON_N = 200
CODES = ["positive", "neutral", "negative", "unmentioned", "uncodable"]
STANCES = CODES[:4]

# Every coded file, in priority order per coder (Week-1 first). (coder, path, sheet)
SOURCES = [
    ("Emily", "coder_materials/Emily/week_01_SUBMITTED_by_Emily (1).xlsx", "main"),
    ("Josh",  "coder_materials/Josh/week_01_due_2026-10-02-2.xlsx", "main"),
    ("Pam",   "coder_materials/Pam/week_01_due_2026-10-02.xlsx", "main"),
]
for s in ["Emily", "Josh", "Pam"]:
    SOURCES += [(s, f"coder_materials/{s}/week_02_due_2026-12-04.xlsx", "main"),
                (s, f"coder_materials/{s}/week_03_due_2026-12-11.xlsx", "main"),
                (s, f"coder_materials/{s}/week_04_due_2026-12-18.xlsx", "main"),
                (s, f"coder_materials/{s}/week_05_due_2027-01-08.xlsx", "placebo")]
SOURCES += [("Jared", "coder_review/Jared/jared_TG_A_complete_week1_pairs.xlsx", "main"),
            ("Jared", "coder_review/Jared/jared_TG_B_union_new.xlsx", "main"),
            ("Jared", "coder_review/Jared/jared_WB_C1_main.xlsx", "main"),
            ("Jared", "coder_review/Jared/jared_WB_C2_main.xlsx", "main"),
            ("Jared", "coder_review/Jared/jared_WB_D_placebo.xlsx", "placebo")]
RULES_MAIN = ["Plain reading (no special rule)", "Decision procedure (s.1)", "Tie-breakers (s.1)",
              "Rule A: target named or heavily implied", "Rule B: battlefield events neutral",
              "Rule C: territory disputes neutral", "Rule D: questions default neutral",
              "1b: framing devices = stance", "1c: referent test / reported speech",
              "1d: collusion / Russiagate", "Uncodable (s.2)", "Other (see notes)"]
RULES_PLAC = ["Placebo: plain reading", "Placebo: stance label (s.1)", "Placebo: tie-breakers",
              "Placebo: worked example (s.3)", "Placebo: uncodable (s.2)", "Other (see notes)"]

_cm = os.path.realpath(CM)
def assert_outside_cm(path):
    rp = os.path.realpath(path)
    assert rp != _cm and not rp.startswith(_cm + os.sep), f"refusing to write inside coder_materials: {path}"
log, problems = [], []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)

def is_one(v):
    return str(v).strip() in ("1", "1.0", "True", "true")

def norm(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    s = str(v).strip().lower()
    return s if s else None

# ---- 1. assignment master ------------------------------------------------------
M = pd.read_csv(MASTER)
assert len(M) == 8000 and M.row_id.is_unique, (len(M), M.row_id.is_unique)
assert set(M.block) == {"main", "placebo"} and M[["coder1", "coder2"]].notna().all().all()
assert (M.coder1 != M.coder2).all()
MI = M.set_index("row_id")
say(f"[1] master: {len(M)} rows; status {M.status.value_counts().to_dict()}")

# ---- 2. raw codes from every file ---------------------------------------------
raw = []                      # one record per (coder, file, row_id, target)
ctx = {}                      # row_id -> context for the sheet
for prio, (coder, rel, sheet) in enumerate(SOURCES):
    p = os.path.join(ROOT, rel)
    assert os.path.exists(p), f"missing coded file {rel}"
    d = pd.read_excel(p, sheet_name=sheet)
    assert d.row_id.is_unique, f"duplicate row_id inside {rel}"
    unknown = set(d.row_id) - set(MI.index)
    assert not unknown, f"{rel} has {len(unknown)} rows not in the assignment master, e.g. {sorted(unknown)[:3]}"
    for t in d.itertuples(index=False):
        r = t.row_id
        if coder not in (MI.at[r, "coder1"], MI.at[r, "coder2"]):
            # Allowed only for an untouched row: a Week-1 blank the other student coded (step 15, A2 case).
            vals = [getattr(t, c) for c in ("stance_russia", "stance_ukraine", "stance") if hasattr(t, c)]
            assert all(norm(v) is None for v in vals) and not is_one(getattr(t, "uncodable")), \
                f"{coder} has {r} in {rel} but is not assigned to it"
            problems.append(dict(kind="unassigned_blank_row_ignored", coder=coder, file=rel, row_id=r, target="", value=""))
            continue
        if r not in ctx:
            ctx[r] = dict(show=t.show, date=str(t.date)[:10], prev_sentence=t.prev_sentence, sentence=t.sentence,
                          next_sentence=t.next_sentence)
        unc = is_one(getattr(t, "uncodable"))
        targets = [("russia", "stance_russia"), ("ukraine", "stance_ukraine")] if sheet == "main" \
            else [(MI.at[r, "grp"], "stance")]
        for tgt, col in targets:
            v = norm(getattr(t, col))
            if unc:
                code = "uncodable"
            elif v is None:
                code = None
            elif v in STANCES:
                code = v
            else:
                code = None; problems.append(dict(kind="invalid_code", coder=coder, file=rel, row_id=r, target=tgt, value=v))
            raw.append(dict(coder=coder, file=rel, prio=prio, row_id=r, target=tgt, code=code,
                            confidence=norm(getattr(t, "confidence")),
                            historical=(norm(getattr(t, "historical")) if sheet == "main" else None)))
R = pd.DataFrame(raw)
# a coder may hold a row in at most two files, and only Week-1 + week_02 (re-sent blanks / uncodables)
dup = R.drop_duplicates(["coder", "file", "row_id"]).groupby(["coder", "row_id"]).file.apply(list)
multi = dup[dup.apply(len) > 1]
assert (multi.apply(len) == 2).all(), "a coder holds a row in more than two files"
assert multi.apply(lambda fs: "week_01" in fs[0] and "week_02" in fs[1]).all(), "unexpected duplicate row across files"
say(f"[2] raw codes: {len(SOURCES)} files, {R.row_id.nunique()} rows seen; {len(multi)} coder-rows in two files (Week-1 + week_02)")

# one code per (coder, row_id, target): first filled code in priority order (Week-1 first)
R = R.sort_values("prio", kind="stable")
filled = R[R.code.notna()].drop_duplicates(["coder", "row_id", "target"], keep="first")
assert_outside_cm(OUT); os.makedirs(OUT, exist_ok=True)
R.drop(columns="prio").to_csv(os.path.join(OUT, "codes_raw_long.csv"), index=False)
code_of = {(c, r, t): v for c, r, t, v in zip(filled.coder, filled.row_id, filled.target, filled.code)}

# ---- 3. compare per (row_id, target) ------------------------------------------
units = []
for r in M.row_id:
    tg = ["russia", "ukraine"] if MI.at[r, "block"] == "main" else [MI.at[r, "grp"]]
    c1, c2 = MI.at[r, "coder1"], MI.at[r, "coder2"]
    for t in tg:
        a, b = code_of.get((c1, r, t)), code_of.get((c2, r, t))
        status = "incomplete" if (a is None or b is None) else ("agreed" if a == b else "disagree")
        units.append(dict(row_id=r, block=MI.at[r, "block"], grp=MI.at[r, "grp"], target=t, coder1=c1, coder2=c2,
                          code_1=a, code_2=b, status=status))
U = pd.DataFrame(units)
assert len(U) == 2 * (M.block == "main").sum() + (M.block == "placebo").sum()
say(f"[3] units: {len(U)}; {U.status.value_counts().to_dict()}")

# ---- 4. blind A/B order (stable hash, seed 123) and key ---------------------------
def a_is_coder1(r, t):
    return int(hashlib.sha256(f"{SEED}|{r}|{t}".encode()).hexdigest(), 16) % 2 == 0
D = U[U.status == "disagree"].copy()
first = [a_is_coder1(r, t) for r, t in zip(D.row_id, D.target)]
D["code_A"] = np.where(first, D.code_1, D.code_2); D["code_B"] = np.where(first, D.code_2, D.code_1)
D["coder_A"] = np.where(first, D.coder1, D.coder2); D["coder_B"] = np.where(first, D.coder2, D.coder1)
assert (D.code_A != D.code_B).all()
assert_outside_cm(KEY)
D[["row_id", "target", "coder_A", "coder_B"]].to_csv(KEY, index=False)

# ---- 5. carry over decisions already in the sheet --------------------------------
# A decision is stamped with the two codes it was made on (stamp_A, stamp_B). If either raw code
# later changes, the decision is cleared (kept as previous_final_code) and the row is pending again.
def txt(v):
    return v if isinstance(v, str) and v.strip() else None
prev = {}
if os.path.exists(SHEET):
    for sh in ("main", "placebo"):
        x = pd.read_excel(SHEET, sheet_name=sh)
        for t in x.to_dict("records"):
            prev[(t["row_id"], t["target"])] = dict(final_code=norm(t.get("final_code")), rule=txt(t.get("rule")),
                notes=txt(t.get("notes")), code_A=t.get("code_A"), code_B=t.get("code_B"),
                stamp_A=txt(t.get("stamp_A")), stamp_B=txt(t.get("stamp_B")),
                previous_final_code=txt(t.get("previous_final_code")))
cur_keys = set(zip(D.row_id, D.target))
for k, v in prev.items():
    if k not in cur_keys and v["final_code"] is not None:
        problems.append(dict(kind="adjudicated_row_no_longer_a_disagreement", coder="", file="adjudication_sheet.xlsx",
                             row_id=k[0], target=k[1], value=v["final_code"]))
fin, rule, notes, prevfin, stA, stB = [], [], [], [], [], []
for r, t, a, b in zip(D.row_id, D.target, D.code_A, D.code_B):
    p = prev.get((r, t))
    if p is None:
        fin.append(None); rule.append(None); notes.append(None); prevfin.append(None); stA.append(None); stB.append(None); continue
    notes.append(p["notes"])
    fc = p["final_code"]
    if fc is None:
        fin.append(None); rule.append(p["rule"]); prevfin.append(p["previous_final_code"]); stA.append(None); stB.append(None); continue
    stamp = (p["stamp_A"], p["stamp_B"]) if p["stamp_A"] else (p["code_A"], p["code_B"])
    if stamp != (a, b):                                   # raw codes changed after the decision
        fin.append(None); rule.append(None); prevfin.append(fc); stA.append(None); stB.append(None)
        problems.append(dict(kind="raw_code_changed_after_adjudication", coder="", file="adjudication_sheet.xlsx",
                             row_id=r, target=t, value=f"{stamp} -> {(a, b)}; previous decision {fc}"))
        continue
    if fc not in CODES:
        problems.append(dict(kind="invalid_final_code", coder="Jared", file="adjudication_sheet.xlsx", row_id=r, target=t, value=fc))
    elif p["rule"] is None:
        problems.append(dict(kind="final_code_without_rule", coder="Jared", file="adjudication_sheet.xlsx", row_id=r, target=t, value=fc))
    fin.append(fc); rule.append(p["rule"]); prevfin.append(p["previous_final_code"]); stA.append(stamp[0]); stB.append(stamp[1])
D["final_code"], D["rule"], D["notes"] = fin, rule, notes
D["previous_final_code"], D["stamp_A"], D["stamp_B"] = prevfin, stA, stB
D["changed_since_adjudicated"] = (D.previous_final_code.notna() & D.final_code.isna()).astype(int)
done = D.final_code.isin(CODES) & D.rule.notna()
say(f"[5] disagreements {len(D)}: adjudicated {int(done.sum())}, pending {int((~done).sum())}, "
    f"re-check after raw-code change {int(D.changed_since_adjudicated.sum())}")

# ---- 6. write the blind sheet -------------------------------------------------------
cols = ["row_id", "target", "show", "date", "prev_sentence", "sentence", "next_sentence",
        "code_A", "code_B", "final_code", "rule", "notes", "changed_since_adjudicated",
        "previous_final_code", "stamp_A", "stamp_B"]
for k in ["show", "date", "prev_sentence", "sentence", "next_sentence"]:
    D[k] = [ctx[r][k] for r in D.row_id]
wb = openpyxl.Workbook(); wb.remove(wb.active)
wr = wb.create_sheet("rules")
for i, v in enumerate(RULES_MAIN): wr.cell(row=i + 1, column=1, value=v)
for i, v in enumerate(RULES_PLAC): wr.cell(row=i + 1, column=2, value=v)
for i, v in enumerate(CODES): wr.cell(row=i + 1, column=3, value=v)
for sh, rule_rng in (("main", f"rules!$A$1:$A${len(RULES_MAIN)}"), ("placebo", f"rules!$B$1:$B${len(RULES_PLAC)}")):
    x = D[D.block == sh].sort_values(["row_id", "target"])[cols]
    ws = wb.create_sheet(sh, 0 if sh == "main" else 1)
    ws.append(cols)
    for t in x.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and np.isnan(v)) else v for v in t])
    n = len(x) + 1
    hdr = PatternFill("solid", fgColor="404040"); yel = PatternFill("solid", fgColor="FFF2CC"); red = PatternFill("solid", fgColor="F4CCCC")
    for c in ws[1]: c.fill = hdr; c.font = Font(bold=True, color="FFFFFF")
    for row in ws.iter_rows(min_row=2, max_row=n):
        for c in row[9:12]: c.fill = yel
        if row[12].value == 1:
            for c in row: c.fill = red
        row[5].font = Font(bold=True); row[5].alignment = Alignment(wrap_text=True)
    for i, w in enumerate([10, 12, 16, 11, 40, 48, 40, 12, 12, 13, 30, 26, 10, 12, 10, 10]):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
    for L in ("O", "P"): ws.column_dimensions[L].hidden = True       # stamps: codes the decision was made on
    ws.freeze_panes = "H2"
    if n > 1:
        dv = DataValidation(type="list", formula1=f"rules!$C$1:$C${len(CODES)}", allow_blank=True); dv.add(f"J2:J{n}"); ws.add_data_validation(dv)
        dv = DataValidation(type="list", formula1=rule_rng, allow_blank=True); dv.add(f"K2:K{n}"); ws.add_data_validation(dv)
wi = wb.create_sheet("info")
for line in ["Blind adjudication sheet. Code A and Code B are the two coders' codes; identities are hidden.",
             "Fill final_code and rule (dropdowns) and notes if useful. Save in place; re-running 17 keeps your entries.",
             "Red rows: a coder changed a raw code after you adjudicated it. Your old decision is in previous_final_code; re-enter final_code and rule.",
             "A decision counts only when both final_code and rule are filled.",
             "Codes: positive, neutral, negative, unmentioned, uncodable. Codebook v2.6 (main), placebo v1.3."]:
    wi.append([line])
wr.sheet_state = "hidden"
assert_outside_cm(SHEET); wb.save(SHEET)

# ---- 7. final labels for every unit ---------------------------------------------------
dec = {(r, t): (fc, ru) for r, t, fc, ru, ok in zip(D.row_id, D.target, D.final_code, D.rule, done) if ok}
fc, ru, st = [], [], []
for r, t, s, a in zip(U.row_id, U.target, U.status, U.code_1):
    if s == "agreed": fc.append(a); ru.append(None); st.append("agreed")
    elif s == "disagree" and (r, t) in dec: fc.append(dec[(r, t)][0]); ru.append(dec[(r, t)][1]); st.append("adjudicated")
    elif s == "disagree": fc.append(None); ru.append(None); st.append("pending")
    else: fc.append(None); ru.append(None); st.append("incomplete")
U["final_code"], U["rule"], U["final_status"] = fc, ru, st
assert U.loc[U.final_status.isin(["agreed", "adjudicated"]), "final_code"].isin(CODES).all()
U.to_csv(os.path.join(OUT, "adjudicated_final.csv"), index=False)
say(f"[7] final status: {U.final_status.value_counts().to_dict()}")

# ---- 8. Jon's audit sample (once, when nothing is pending or incomplete) ---------------------
if os.path.exists(JON):
    say("[8] Jon audit sample already drawn; not redrawn")
elif (U.final_status.isin(["pending", "incomplete"])).any():
    say(f"[8] Jon audit sample waits until everything is coded and adjudicated "
        f"({int((U.final_status == 'pending').sum())} pending, {int((U.final_status == 'incomplete').sum())} incomplete)")
else:
    A = D[done].copy()
    A["family"] = np.where(A.block == "placebo", "placebo", A.target)
    k = min(JON_N, len(A))
    share = A.family.value_counts().sort_index() * k / len(A)
    alloc = np.floor(share).astype(int)
    for f in (share - alloc).sort_values(ascending=False).index[: k - alloc.sum()]: alloc[f] += 1
    rng = np.random.default_rng(SEED); pick = []
    for f in sorted(alloc.index):
        keys = sorted(zip(A.row_id[A.family == f], A.target[A.family == f]))
        idx = rng.choice(len(keys), alloc[f], replace=False)
        pick += [keys[i] for i in sorted(idx)]
    S = A.set_index(["row_id", "target"]).loc[pick].reset_index()
    S = S[["row_id", "target", "show", "date", "prev_sentence", "sentence", "next_sentence", "code_A", "code_B", "final_code", "rule", "notes"]]
    S["jon_agrees"] = None; S["jon_code"] = None; S["jon_notes"] = None
    assert len(S) == k and S.set_index(["row_id", "target"]).index.is_unique
    assert_outside_cm(JON); S.to_excel(JON, index=False)
    say(f"[8] Jon audit sample drawn: {k} rows {alloc.to_dict()}")

pd.DataFrame(problems, columns=["kind", "coder", "file", "row_id", "target", "value"]).to_csv(os.path.join(OUT, "problems.csv"), index=False)
if problems:
    say(f"WARNING: {len(problems)} problems written to adjudication/problems.csv "
        f"{pd.Series([p['kind'] for p in problems]).value_counts().to_dict()}")
open(os.path.join(OUT, "build_log.txt"), "w").write("\n".join(log) + "\n")
```

### `code/3_human_coding/18_icr_report.py`
```python
###############################################################################
# 18_icr_report.py -- inter-coder agreement from RAW (pre-adjudication) codes. Seed 123.
#
# Input: coder_review/adjudication/adjudicated_final.csv from step 17 (code_1, code_2 per
# (row_id, target) for the two assigned coders). Only complete pairs are used.
#
# Statistics
#   - Krippendorff's alpha, nominal, two coders per unit, no missing values within a unit:
#       coincidence matrix o_ck (each unit adds (a,b) and (b,a)); n_c = row sums; n = 2 * units
#       alpha = 1 - D_o / D_e,  D_o = sum_{c!=k} o_ck / n,  D_e = sum_{c!=k} n_c n_k / (n (n - 1))
#     Categories: positive, neutral, negative, unmentioned, uncodable. alpha is NaN when D_e = 0.
#   - 95% CI: nonparametric bootstrap over units (sentences for the gate, (row, target) otherwise),
#     1,000 resamples, seed 123, percentile interval.
#   - Percent agreement, and per-class specific agreement p_c = o_cc / n_c (share of a coder's
#     uses of class c that the other coder matched).
#   - Gate (mentioned vs unmentioned), per main sentence: "mentioned" if either target is
#     positive/neutral/negative for that coder, "unmentioned" if both targets are unmentioned;
#     sentences either coder marked uncodable are left out of the gate.
# Breakdowns: target (russia, ukraine, all placebo, each placebo entity), stratum x target,
# coder pair x target, and the gate overall / by stratum / by pair.
#
# Usage: python3 18_icr_report.py <podcast_analysis_root>
# Writes coder_review/icr/{icr_report.csv, icr_summary.md}
# Test: tests/test_17_18_adjudication_icr.py
###############################################################################
import sys, os
import numpy as np, pandas as pd

ROOT = sys.argv[1]
SEED = 123
B = 1000
IN = os.path.join(ROOT, "coder_review", "adjudication", "adjudicated_final.csv")
OUT = os.path.join(ROOT, "coder_review", "icr")
CODES = ["positive", "neutral", "negative", "unmentioned", "uncodable"]
GATE = ["mentioned", "unmentioned"]
cm = os.path.realpath(os.path.join(ROOT, "coder_materials")); ro = os.path.realpath(OUT)
assert not (ro == cm or ro.startswith(cm + os.sep)), "refusing to write inside coder_materials"
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)

def coincidence(a, b, cats):
    ix = {c: i for i, c in enumerate(cats)}
    o = np.zeros((len(cats), len(cats)))
    np.add.at(o, ([ix[x] for x in a], [ix[y] for y in b]), 1)
    return o + o.T

def alpha_from(o):
    n_c = o.sum(axis=1); n = n_c.sum()
    if n < 2: return np.nan
    d_o = (o.sum() - np.trace(o)) / n
    d_e = (n_c.sum() ** 2 - (n_c ** 2).sum()) / (n * (n - 1))
    return np.nan if d_e == 0 else 1 - d_o / d_e

def stats(a, b, cats, rng):
    a, b = np.asarray(a), np.asarray(b); N = len(a)
    row = dict(n_units=N)
    if N == 0:
        return {**row, "alpha": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "pct_agree": np.nan}
    o = coincidence(a, b, cats)
    row["alpha"] = alpha_from(o)
    boots = []
    for _ in range(B):
        i = rng.integers(0, N, N)
        boots.append(alpha_from(coincidence(a[i], b[i], cats)))
    boots = np.array(boots, dtype=float); boots = boots[~np.isnan(boots)]
    row["ci_lo"], row["ci_hi"] = (np.percentile(boots, [2.5, 97.5]) if len(boots) else (np.nan, np.nan))
    row["pct_agree"] = float((a == b).mean())
    n_c = o.sum(axis=1)
    for j, c in enumerate(cats):
        row[f"n_{c}"] = int(n_c[j])
        row[f"agree_{c}"] = (o[j, j] / n_c[j]) if n_c[j] else np.nan
    return row

# ---- 1. load complete pairs -----------------------------------------------------
U = pd.read_csv(IN)
need = {"row_id", "block", "grp", "target", "coder1", "coder2", "code_1", "code_2", "status"}
assert need <= set(U.columns), need - set(U.columns)
C = U[U.status.isin(["agreed", "disagree"])].copy()
assert C.code_1.isin(CODES).all() and C.code_2.isin(CODES).all(), "unexpected code values"
C["pair"] = [" + ".join(sorted(p)) for p in zip(C.coder1, C.coder2)]
C["family"] = np.where(C.block == "placebo", "placebo", C.target)
say(f"[1] complete pairs: {len(C)} of {len(U)} units; by family {C.family.value_counts().to_dict()}")

# ---- 2. target-level breakdowns -------------------------------------------------------
rng = np.random.default_rng(SEED)
rows = []
def add(scope, group, target, sub):
    rows.append(dict(scope=scope, group=group, target=target, **stats(sub.code_1, sub.code_2, CODES, rng)))
for fam in ["russia", "ukraine", "placebo"]:
    add("overall", "all", fam, C[C.family == fam])
for ent in sorted(C.loc[C.block == "placebo", "target"].unique()):
    add("placebo_entity", ent, ent, C[(C.block == "placebo") & (C.target == ent)])
for strat in sorted(C.loc[C.block == "main", "grp"].unique()):
    for fam in ["russia", "ukraine"]:
        add("stratum", strat, fam, C[(C.grp == strat) & (C.family == fam)])
for pair in sorted(C.pair.unique()):
    for fam in ["russia", "ukraine", "placebo"]:
        sub = C[(C.pair == pair) & (C.family == fam)]
        if len(sub): add("pair", pair, fam, sub)

# ---- 3. gate (mentioned vs unmentioned) per main sentence ---------------------------------
mm = C[C.block == "main"].pivot_table(index=["row_id", "grp", "pair"], columns="target",
                                      values=["code_1", "code_2"], aggfunc="first")
mm = mm.dropna()                                   # both targets complete for both coders
def gate(r, u):
    if "uncodable" in (r, u): return None
    return "mentioned" if (r in CODES[:3] or u in CODES[:3]) else "unmentioned"
G = pd.DataFrame({"g1": [gate(r, u) for r, u in zip(mm[("code_1", "russia")], mm[("code_1", "ukraine")])],
                  "g2": [gate(r, u) for r, u in zip(mm[("code_2", "russia")], mm[("code_2", "ukraine")])]},
                 index=mm.index).reset_index()
G = G.dropna(subset=["g1", "g2"])
def addg(scope, group, sub):
    rows.append(dict(scope=scope, group=group, target="gate", **stats(sub.g1, sub.g2, GATE, rng)))
addg("gate", "all", G)
for strat in sorted(G.grp.unique()): addg("gate_stratum", strat, G[G.grp == strat])
for pair in sorted(G.pair.unique()): addg("gate_pair", pair, G[G.pair == pair])

# ---- 4. write -------------------------------------------------------------------------
Rp = pd.DataFrame(rows)
os.makedirs(OUT, exist_ok=True)
Rp.to_csv(os.path.join(OUT, "icr_report.csv"), index=False)
def fmt(v): return "" if pd.isna(v) else f"{v:.2f}"
head = Rp[Rp.scope.isin(["overall", "gate"])]
md = ["# Inter-coder agreement (raw codes, before adjudication)", "",
      f"Complete pairs: {len(C)} (row, target) units; gate: {len(G)} sentences. Nominal Krippendorff's alpha; "
      f"95% CI from {B} bootstrap resamples of units (seed 123). Full breakdowns in icr_report.csv.", "",
      "| Target | Units | alpha | 95% CI | % agree |", "|---|---|---|---|---|"]
for t in head.itertuples():
    md.append(f"| {t.target} | {t.n_units} | {fmt(t.alpha)} | {fmt(t.ci_lo)}–{fmt(t.ci_hi)} | {fmt(t.pct_agree)} |")
md += ["", "| Pair | Target | Units | alpha | 95% CI |", "|---|---|---|---|---|"]
for t in Rp[Rp.scope == "pair"].itertuples():
    md.append(f"| {t.group} | {t.target} | {t.n_units} | {fmt(t.alpha)} | {fmt(t.ci_lo)}–{fmt(t.ci_hi)} |")
open(os.path.join(OUT, "icr_summary.md"), "w").write("\n".join(md) + "\n")
for t in head.itertuples():
    say(f"[4] {t.target:8s} units {t.n_units:5d}  alpha {fmt(t.alpha)}  CI {fmt(t.ci_lo)}-{fmt(t.ci_hi)}  agree {fmt(t.pct_agree)}")
```

### `tests/test_17_18_adjudication_icr.py`
```python
# test_17_18_adjudication_icr.py -- end-to-end test of 17_build_adjudication.py and
# 18_icr_report.py on a full-size FAKE tree.        python3 tests/test_17_18_adjudication_icr.py [parent_dir]
#
# 1. Build the fake tree with tests/test_15 (fresh, test-owned folder), then "release" step 15's
#    output the way step 16 did (student weeks into coder_materials, Jared batches and the
#    assignment master into coder_review).
# 2. Fill every coded file with synthetic codes: a hidden true label per (row, target), each coder
#    reports it with probability 0.85, otherwise a different random stance. Week-1 blanks stay blank
#    and come back filled in week_02; the A1 row (uncodable in Week-1) gets a different code in week_02.
# 3. Check 17 independently: unit counts, disagreements, Week-1-first rule, blind sheet and key,
#    decisions kept on re-run, raw-code change clears a decision, rule required, Jon sample drawn once.
# 4. Check 18: alpha for every family and the gate equals the published `krippendorff` package
#    computed straight from the coded files; CI brackets alpha.
# 5. Negative tests: a code from an unassigned coder and a missing file must make 17 fail.
import sys, os, subprocess, tempfile, glob, shutil, hashlib
import numpy as np, pandas as pd, openpyxl, krippendorff

HERE = os.path.dirname(os.path.abspath(__file__))
S17 = os.path.join(HERE, "..", "code", "3_human_coding", "17_build_adjudication.py")
S18 = os.path.join(HERE, "..", "code", "3_human_coding", "18_icr_report.py")
PARENT = sys.argv[1] if len(sys.argv) > 1 else None
if PARENT: os.makedirs(PARENT, exist_ok=True)
W = tempfile.mkdtemp(prefix="test1718_", dir=PARENT)
print("workdir", W)

# ---- 1. fake tree + release --------------------------------------------------------
p = subprocess.run([sys.executable, os.path.join(HERE, "test_15_rebuild_reduced_design.py"), W], capture_output=True, text=True)
assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
T15 = glob.glob(os.path.join(W, "test15_*"))[0]
R, O = os.path.join(T15, "fake"), os.path.join(T15, "out1")
DONE = {"Emily": "week_01_SUBMITTED_by_Emily (1).xlsx", "Josh": "week_01_due_2026-10-02-2.xlsx", "Pam": "week_01_due_2026-10-02.xlsx"}
for s in ["Emily", "Josh", "Pam"]:                      # as step 16: originals out, staged weeks in
    sup = f"{R}/coder_materials/_superseded/old_schedule_nov30/{s}"; os.makedirs(sup)
    for f in glob.glob(f"{R}/coder_materials/{s}/week_*.xlsx"):
        if os.path.basename(f) != DONE[s]: shutil.move(f, sup)
    for f in glob.glob(f"{O}/{s}/*.xlsx"): shutil.copy(f, f"{R}/coder_materials/{s}/")
for f in glob.glob(f"{O}/Jared/*.xlsx"): shutil.copy(f, f"{R}/coder_review/Jared/")
os.makedirs(f"{R}/coder_review/_admin", exist_ok=True)
shutil.copy(f"{O}/_admin/assignment_master_v2.csv", f"{R}/coder_review/_admin/")
M = pd.read_csv(f"{R}/coder_review/_admin/assignment_master_v2.csv").set_index("row_id")
print("[1] fake tree released")

# ---- 2. synthetic codes ----------------------------------------------------------------
rng = np.random.default_rng(123)
ST = ["positive", "neutral", "negative", "unmentioned"]
truth = {}
for r, blk, grp in zip(M.index, M.block, M.grp):
    for t in (["russia", "ukraine"] if blk == "main" else [grp]):
        truth[(r, t)] = ST[rng.choice(4, p=[.15, .15, .1, .6])]
def report(r, t):
    v = truth[(r, t)]
    return v if rng.random() < .85 else rng.choice([x for x in ST if x != v])
W1 = {"Emily": "Emily/week_01_SUBMITTED_by_Emily (1).xlsx", "Josh": "Josh/week_01_due_2026-10-02-2.xlsx", "Pam": "Pam/week_01_due_2026-10-02.xlsx"}
files = [(s, f"coder_materials/{W1[s]}", "main") for s in W1]
for s in ["Emily", "Josh", "Pam"]:
    files += [(s, f, "placebo" if "week_05" in f else "main") for f in
              sorted(os.path.relpath(x, R) for x in glob.glob(f"{R}/coder_materials/{s}/week_0[2-5]_*.xlsx"))]
files += [("Jared", os.path.relpath(x, R), "placebo" if "_D_" in x else "main") for x in sorted(glob.glob(f"{R}/coder_review/Jared/*.xlsx"))]
expected = {}                               # (coder, row, target) -> code that 17 must use
a1_row = None
for coder, rel, sheet in files:
    d = pd.read_excel(f"{R}/{rel}", sheet_name=sheet)
    for c in ("stance_russia", "stance_ukraine", "stance"):
        if c in d.columns: d[c] = d[c].astype(object)
    for i, r in enumerate(d.row_id):
        if sheet == "main":
            if "week_01" in rel:
                if pd.isna(d.at[i, "stance_russia"]):
                    if str(d.at[i, "uncodable"]).strip() in ("1", "1.0"):   # A1 row: Week-1 uncodable wins
                        a1_row = r
                        for t in ("russia", "ukraine"): expected[(coder, r, t)] = "uncodable"
                    continue                                                # blank: filled later in week_02
            for t, col in (("russia", "stance_russia"), ("ukraine", "stance_ukraine")):
                v = report(r, t); d.at[i, col] = v
                expected.setdefault((coder, r, t), v)
        else:
            t = M.at[r, "grp"]; v = report(r, t); d.at[i, "stance"] = v; expected.setdefault((coder, r, t), v)
    d.to_excel(f"{R}/{rel}", sheet_name=sheet, index=False)
assert a1_row is not None
print(f"[2] synthetic codes written to {len(files)} files; A1 row {a1_row}")

def run(script):
    return subprocess.run([sys.executable, script, R], capture_output=True, text=True)

# ---- 3. 17 checks ------------------------------------------------------------------------
p = run(S17); assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-3000:]
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert len(U) == 2 * (M.block == "main").sum() + (M.block == "placebo").sum() == 15000, len(U)
assert (U.status != "incomplete").all(), U.status.value_counts()
exp_dis = 0
for r, t, c1, c2, a, b in zip(U.row_id, U.target, U.coder1, U.coder2, U.code_1, U.code_2):
    assert a == expected[(c1, r, t)] and b == expected[(c2, r, t)], (r, t, a, b)
    exp_dis += expected[(c1, r, t)] != expected[(c2, r, t)]
assert (U.status == "disagree").sum() == exp_dis
assert set(U.loc[U.row_id == a1_row, "code_1"].tolist() + U.loc[U.row_id == a1_row, "code_2"].tolist()) & {"uncodable"}
print(f"[3a] 15,000 units complete; {exp_dis} disagreements match the files; Week-1-first rule holds (A1 row uncodable)")

SH = f"{R}/coder_review/adjudication/adjudication_sheet.xlsx"
key = pd.read_csv(f"{R}/coder_review/_admin/adjudication_key.csv").set_index(["row_id", "target"])
sheets = {sh: pd.read_excel(SH, sheet_name=sh) for sh in ("main", "placebo")}
assert sum(len(x) for x in sheets.values()) == exp_dis
for sh, x in sheets.items():
    blob = " ".join(str(v) for v in x.values.ravel())
    assert not any(n in blob for n in ["Emily", "Josh", "Pam", "Jared"]), "coder name visible in the blind sheet"
    for r, t, a, b in zip(x.row_id, x.target, x.code_A, x.code_B):
        k = key.loc[(r, t)]
        assert a == expected[(k.coder_A, r, t)] and b == expected[(k.coder_B, r, t)]
p2 = run(S17); assert p2.returncode == 0
assert pd.read_csv(f"{R}/coder_review/_admin/adjudication_key.csv").equals(key.reset_index()), "A/B order changed between runs"
print("[3b] blind sheet has no coder names; key matches; A/B order stable across runs")

def fill(n, with_rule=True):
    wb = openpyxl.load_workbook(SH); ws = wb["main"]
    hdr = [c.value for c in ws[1]]; fi, ri = hdr.index("final_code") + 1, hdr.index("rule") + 1
    for i in range(2, 2 + n):
        ws.cell(row=i, column=fi, value=ws.cell(row=i, column=hdr.index("code_A") + 1).value)
        if with_rule: ws.cell(row=i, column=ri, value="Plain reading (no special rule)")
    wb.save(SH)
fill(10); assert run(S17).returncode == 0
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "adjudicated").sum() == 10, U.final_status.value_counts()
x = pd.read_excel(SH, sheet_name="main")
r0, t0 = x.row_id[0], x.target[0]
k = key.loc[(r0, t0)]
rel = [f for c, f, s in files if c == k.coder_A and s == "main" and r0 in set(pd.read_excel(f"{R}/{f}", sheet_name="main").row_id)][-1]
d = pd.read_excel(f"{R}/{rel}", sheet_name="main"); col = "stance_russia" if t0 == "russia" else "stance_ukraine"
d[col] = d[col].astype(object)
old = d.loc[d.row_id == r0, col].iloc[0]
d.loc[d.row_id == r0, col] = [v for v in ST if v not in (old, x.code_B[0])][0]
d.to_excel(f"{R}/{rel}", sheet_name="main", index=False)
assert run(S17).returncode == 0
x = pd.read_excel(SH, sheet_name="main").set_index(["row_id", "target"])
assert pd.isna(x.loc[(r0, t0), "final_code"]) and x.loc[(r0, t0), "changed_since_adjudicated"] == 1 \
       and x.loc[(r0, t0), "previous_final_code"] == old
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "adjudicated").sum() == 9
pr = pd.read_csv(f"{R}/coder_review/adjudication/problems.csv")
assert "raw_code_changed_after_adjudication" in set(pr.kind)
print("[3c] decisions kept on re-run; a raw-code change clears the decision, flags it, keeps the old one")

# rule required: fill everything but leave one final without a rule
wb = openpyxl.load_workbook(SH)
for sh in ("main", "placebo"):
    ws = wb[sh]; hdr = [c.value for c in ws[1]]
    fi, ri, ai = hdr.index("final_code") + 1, hdr.index("rule") + 1, hdr.index("code_A") + 1
    for i in range(2, ws.max_row + 1):
        if ws.cell(row=i, column=fi).value is None: ws.cell(row=i, column=fi, value=ws.cell(row=i, column=ai).value)
        if ws.cell(row=i, column=ri).value is None: ws.cell(row=i, column=ri, value="Other (see notes)")
ws = wb["placebo"]; ws.cell(row=2, column=[c.value for c in ws[1]].index("rule") + 1).value = None   # cell(value=None) is a no-op
wb.save(SH)
assert run(S17).returncode == 0
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "pending").sum() == 1
assert "final_code_without_rule" in set(pd.read_csv(f"{R}/coder_review/adjudication/problems.csv").kind)
JON = f"{R}/coder_review/adjudication/jon_audit_sample.xlsx"
assert not os.path.exists(JON), "Jon sample drawn while a row was pending"
wb = openpyxl.load_workbook(SH); ws = wb["placebo"]; ws.cell(row=2, column=[c.value for c in ws[1]].index("rule") + 1, value="Other (see notes)"); wb.save(SH)
assert run(S17).returncode == 0
J = pd.read_excel(JON)
assert len(J) == 200 and not J.duplicated(["row_id", "target"]).any()
fam = np.where(J.target.isin(["russia", "ukraine"]), J.target, "placebo")
Dall = pd.concat([pd.read_excel(SH, sheet_name=s) for s in ("main", "placebo")])
share = pd.Series(np.where(Dall.target.isin(["russia", "ukraine"]), Dall.target, "placebo")).value_counts(normalize=True)
got = pd.Series(fam).value_counts()
assert all(abs(got[f] - 200 * share[f]) <= 1 for f in share.index), (got.to_dict(), share.to_dict())
h = hashlib.sha256(open(JON, "rb").read()).hexdigest()
assert run(S17).returncode == 0 and hashlib.sha256(open(JON, "rb").read()).hexdigest() == h, "Jon sample redrawn"
print(f"[3d] rule required; Jon sample waits for completion, then 200 rows {got.to_dict()} drawn once")

# ---- 4. 18 checks: alpha vs the krippendorff package, straight from the files ----------------
p = run(S18); assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-3000:]
rep = pd.read_csv(f"{R}/coder_review/icr/icr_report.csv")
num = {c: i for i, c in enumerate(["positive", "neutral", "negative", "unmentioned", "uncodable"])}
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
for f in ["russia", "ukraine", "placebo"]:
    sub = U[(np.where(U.block == "placebo", "placebo", U.target)) == f]
    data = np.array([[num[a] for a in sub.code_1], [num[b] for b in sub.code_2]], dtype=float)
    ref = krippendorff.alpha(reliability_data=data, level_of_measurement="nominal", value_domain=list(range(5)))
    ours = rep[(rep.scope == "overall") & (rep.target == f)].iloc[0]
    assert abs(ours.alpha - ref) < 1e-9, (f, ours.alpha, ref)
    assert ours.ci_lo <= ours.alpha <= ours.ci_hi
    assert ours.n_units == len(sub)
# raw codes in adjudicated_final must equal the file codes (the edited one included)
chg = {(r0, t0)}
for r, t, c1, c2, a, b in zip(U.row_id, U.target, U.coder1, U.coder2, U.code_1, U.code_2):
    if (r, t) in chg: continue
    assert a == expected[(c1, r, t)] and b == expected[(c2, r, t)]
g = rep[rep.scope == "gate"].iloc[0]
mm = U[U.block == "main"]
def gl(x, y): return None if "uncodable" in (x, y) else (0 if (x in ST[:3] or y in ST[:3]) else 1)
g1, g2 = [], []
for r, sub in mm.groupby("row_id"):
    s = sub.set_index("target")
    a, b = gl(s.at["russia", "code_1"], s.at["ukraine", "code_1"]), gl(s.at["russia", "code_2"], s.at["ukraine", "code_2"])
    if a is not None and b is not None: g1.append(a); g2.append(b)
ref = krippendorff.alpha(reliability_data=np.array([g1, g2], dtype=float), level_of_measurement="nominal")
assert abs(g.alpha - ref) < 1e-9 and g.n_units == len(g1), (g.alpha, ref, g.n_units, len(g1))
assert os.path.exists(f"{R}/coder_review/icr/icr_summary.md")
print(f"[4] 18 alpha equals the krippendorff package for russia, ukraine, placebo and the gate "
      f"(russia {rep[(rep.scope=='overall')&(rep.target=='russia')].alpha.iloc[0]:.3f}); CIs bracket alpha")

# ---- 5. negative tests ----------------------------------------------------------------------------
rel = f"coder_materials/Emily/week_02_due_2026-12-04.xlsx"
keep = open(f"{R}/{rel}", "rb").read()
d = pd.read_excel(f"{R}/{rel}", sheet_name="main")
foreign = [r for r in M.index if M.at[r, "block"] == "main" and "Emily" not in (M.at[r, "coder1"], M.at[r, "coder2"])][0]
d.loc[len(d)] = d.iloc[0]; d.at[len(d) - 1, "row_id"] = foreign
d.to_excel(f"{R}/{rel}", sheet_name="main", index=False)
p = run(S17); open(f"{R}/{rel}", "wb").write(keep)
assert p.returncode != 0 and "is not assigned to it" in p.stderr, p.stderr[-800:]
os.rename(f"{R}/{rel}", f"{R}/{rel}.moved")
p = run(S17); os.rename(f"{R}/{rel}.moved", f"{R}/{rel}")
assert p.returncode != 0 and "missing coded file" in p.stderr, p.stderr[-800:]
print("[5] negative tests fail for the right reason: unassigned coder; missing file")
print("ALL TESTS PASSED")
```
