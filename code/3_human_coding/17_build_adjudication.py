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
