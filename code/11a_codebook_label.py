#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stance Labeling — 8-Condition Bias Sensitivity Pipeline (model = "claude").

PI: Jared Edgerton (PSU) / co-PI: Jon Green (Duke).
Legitimate measurement-error sensitivity analysis: a single codebook is applied
under eight coder-bias conditions to measure how systematic coder bias propagates.

Targets in scope: russia, ukraine  (assad is defined in the codebook but OUT OF
SCOPE for this file; topics 78/79 only).

Schema (per target, per condition, per row): label in {positive, negative,
neutral, unmentioned}.

HARD CONSTRAINT — mention boundary is invariant across conditions:
  c0_faithful makes the 4-way decision (including unmentioned). Every biased /
  non-directional condition operates ONLY on the valence of MENTIONED targets.
  Implemented BY CONSTRUCTION: for c1..c7, cells that are unmentioned in c0
  inherit unmentioned (no model call); mentioned cells get a 3-way valence
  re-code offering only {positive, negative, neutral}. A condition therefore
  cannot move the mention<->unmention boundary.

Determinism: temperature=0 on every call. The Anthropic Messages API exposes no
`seed` parameter, so seed=123 governs only Python-side randomness (exemplar
selection). This is logged in the run-log header.

Usage:
  set ANTHROPIC_API_KEY, then:
    python stance_bias_pipeline.py --smoke      # tiny end-to-end test (few rows)
    python stance_bias_pipeline.py              # full run (resumable)
    python stance_bias_pipeline.py --report-only  # rebuild outputs from checkpoint
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
DATA_CSV       = "stance_train_1500.csv"
CODEBOOK_MD    = "stance_codebook.md"

MODEL          = "claude-opus-4-8"   # configurable; logged in run header
TEMPERATURE    = 0.0
MAX_TOKENS     = 64    # forced tool_use; only a tiny JSON label is emitted
SEED           = 123                  # Python-side randomness only (API has no seed)

TARGETS        = ("russia", "ukraine")
LABELS         = ("positive", "negative", "neutral", "unmentioned")
VALENCE        = ("positive", "negative", "neutral")   # mentioned-only re-code vocab
HUMAN_COL      = {"russia": "russia_stance", "ukraine": "ukraine_stance"}

EXEMPLARS_PER_CELL = 8     # per (target x label) cell; ~60-90 unique rows total

# Per-cell exemplar quotas (overrides EXEMPLARS_PER_CELL for specific cells).
# PATCH 2025-06: Opus c0 under-detected positive-Russia (31% recall, 32/48 -> neutral).
# Oversample the hard minority cells so the few-shot teacher sees more of them.
# Pools available (human rows): russia positive=57, ukraine positive=27, etc.
EXEMPLAR_QUOTAS = {
    ("russia",  "positive"): 20,   # was 8; the broken cell
    ("russia",  "negative"): 12,
    ("ukraine", "positive"): 14,   # was 8; small pool (27 total)
    ("ukraine", "negative"): 12,
}
MAX_RETRIES    = 6
# Parallelism across (row, target) JOBS. Within a job, c0 is computed before
# c1..c7 (the bias re-codes depend on c0's mention decision). Per-cell logging
# and checkpointing are preserved, so the run stays debuggable and resumable.
CONCURRENCY    = 6

# Outputs
RUN_LOG        = "stance_bias_run.log"
CHECKPOINT     = "stance_bias_checkpoint.jsonl"
EXEMPLAR_LOG   = "stance_bias_exemplars.csv"
LONG_CSV       = "stance_labels_long.csv"
WIDE_CSV       = "stance_labels_wide.csv"
SUMMARY_CSV    = "stance_bias_summary.csv"
VALIDATION_CSV = "stance_heldout_c0_validation.csv"

CONDITIONS = (
    "c0_faithful",
    "c1_modRU", "c2_strongRU", "c3_modUA", "c4_strongUA",
    "c5_placebo", "c6_central", "c7_extreme",
    "c8_mention_lax", "c9_mention_strict",
)

# Boundary-perturbation conditions DELIBERATELY move the mention<->unmention
# boundary, so they are (a) NOT gated by c0's mention decision, (b) run as a full
# 4-way pass on EVERY cell, and (c) EXEMPT from the mention-boundary invariance
# assert that guards c1..c7.
BOUNDARY_CONDITIONS = frozenset({"c8_mention_lax", "c9_mention_strict"})

# ----------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------
logger = logging.getLogger("stance")


def setup_logging():
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(RUN_LOG, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)


# ----------------------------------------------------------------------------
# STEP A — LOAD & VALIDATE
# ----------------------------------------------------------------------------
def load_and_validate():
    df = pd.read_csv(DATA_CSV)
    expected_cols = ["sample_id", "prev_sentence", "sentence", "next_sentence",
                     "russia_stance", "ukraine_stance", "notes"]
    if list(df.columns) != expected_cols:
        raise SystemExit(f"SCHEMA VIOLATION: columns are {list(df.columns)}, "
                         f"expected {expected_cols}")

    if df["sample_id"].duplicated().any():
        raise SystemExit("SCHEMA VIOLATION: duplicate sample_id values.")
    if df["sample_id"].isna().any():
        raise SystemExit("SCHEMA VIOLATION: null sample_id values.")

    # human-label vocab check (non-blank only)
    for tgt, col in HUMAN_COL.items():
        vals = set(df[col].dropna().unique())
        oov = vals - set(LABELS)
        if oov:
            raise SystemExit(f"SCHEMA VIOLATION: {col} has out-of-vocab values {oov}")

    n_labeled = {t: int(df[HUMAN_COL[t]].notna().sum()) for t in TARGETS}
    logger.info("Loaded %d rows; human-labeled: russia=%d ukraine=%d",
                len(df), n_labeled["russia"], n_labeled["ukraine"])
    return df


# ----------------------------------------------------------------------------
# STEP B — EXEMPLAR SELECTION (stratified, seed 123)
# ----------------------------------------------------------------------------
def select_exemplars(df):
    """Reference rows = rows with BOTH human labels. Pick a stratified subset
    covering every (target x label) cell; the rest are held-out validation."""
    ref = df[df["russia_stance"].notna() & df["ukraine_stance"].notna()].copy()
    rng = np.random.RandomState(SEED)

    chosen = set()
    cell_counts = defaultdict(int)
    for tgt in TARGETS:
        col = HUMAN_COL[tgt]
        for lab in LABELS:
            pool = ref[ref[col] == lab]["sample_id"].tolist()
            rng.shuffle(pool)
            quota = EXEMPLAR_QUOTAS.get((tgt, lab), EXEMPLARS_PER_CELL)
            take = pool[:quota]
            for sid in take:
                chosen.add(sid)
            cell_counts[(tgt, lab)] = len(take)

    exemplar_ids = sorted(chosen)
    ex_df = ref[ref["sample_id"].isin(exemplar_ids)].copy()
    heldout_df = ref[~ref["sample_id"].isin(exemplar_ids)].copy()

    # label set = the non-reference (unlabeled) rows
    labelset_df = df[df["russia_stance"].isna() & df["ukraine_stance"].isna()].copy()

    # log exemplar coverage + chosen ids
    logger.info("Exemplars: %d unique rows. Cell coverage:", len(exemplar_ids))
    for tgt in TARGETS:
        cov = {lab: cell_counts[(tgt, lab)] for lab in LABELS}
        logger.info("   %-7s %s", tgt, cov)
    logger.info("Held-out human validation rows: %d", len(heldout_df))
    logger.info("Non-reference label set rows: %d", len(labelset_df))

    ex_df.to_csv(EXEMPLAR_LOG, index=False)
    logger.info("Wrote chosen exemplar sample_ids -> %s", EXEMPLAR_LOG)
    return ex_df, heldout_df, labelset_df


# ----------------------------------------------------------------------------
# STEP C — PROMPTS
# ----------------------------------------------------------------------------
CODEBOOK_RULES = """\
You are an expert political-communication coder labeling STANCE in podcast
transcript sentences for an academic study (PI: Jared Edgerton, PSU).

TARGETS (this file): russia and ukraine only. (The codebook also defines `assad`,
but it is OUT OF SCOPE here — never used.)

You judge stance toward ONE named target at a time. Code the TARGET SENTENCE only;
prev/next sentences are CONTEXT to resolve pronouns or references — do not code them.

LABELS (exactly one per target):
- positive    = sympathetic/supportive/justifying/favorable toward the target
                (frames it as justified, provoked-into-acting, its cause as good;
                 or attacks its opponent in a way that defends it).
- negative    = critical/hostile/condemning/blaming toward the target
                (calls it the aggressor, corrupt, illegitimate; opposes its cause).
- neutral     = the target IS referenced but the sentence takes no evaluative
                position (factual/descriptive, incidental, or genuinely balanced).
- unmentioned = the target is NOT referenced in the sentence (OFF-scale; this is
                NOT a valence value).

KEY DECISION RULES:
1. Code the `sentence` only; use prev/next solely for context.
2. MENTION requires the NAMED actor: the country, its leader, government, military,
   or people (Russia/Putin/Kremlin/Moscow-as-govt/"the Russians";
   Ukraine/Zelensky/Kyiv-as-govt/"the Ukrainians"). Territory or objects ALONE are
   NOT a mention of the country (Crimea, Donbas, the oblasts, "Russian gas", a
   Russian-made weapon do NOT by themselves make the COUNTRY mentioned). If the
   named actor is absent -> unmentioned.
3. unmentioned != neutral. unmentioned = not referenced; neutral = referenced, no
   evaluative position.
4. TONE != STANCE. Code the speaker's POSITION toward the target, not emotional
   mood. A negative-toned sentence can be pro-target and vice versa.
5. Describing military success/strength = neutral, NOT stance. "Russia is winning",
   "the Russians won't be pushed back easily", "Russian forces hold the advantage"
   -> neutral for Russia UNLESS the speaker explicitly endorses/approves it. Flat
   descriptors ("invasion", "controls", "consolidation") are neutral; evaluative
   words ("aggression", "blunder", "brutal") carry stance.
6. STANCE-VIA-OPPONENT counts: criticizing the target's opponent is a stance toward
   the target (mocking "the demonization of Russia", calling Ukraine aid a scam, or
   framing US/NATO confrontation of Russia as reckless -> pro-Russia / anti-Ukraine)
   — PROVIDED the target is named per rule 2.
7. AXES ARE INDEPENDENT. Anti-Ukraine is NOT automatically pro-Russia. Judge each
   target on its own.
8. INCIDENTAL MENTION = neutral. If the target is named only to attack a third party
   (e.g., Russia named only to smear Biden), it is not a stance toward the target.

Output ONLY a JSON object: {"label": "<one of the allowed labels>"}.

STUDY CONTEXT (read carefully): This is a sanctioned measurement-error
sensitivity analysis (PI Jared Edgerton, PSU; co-PI Jon Green, Duke). Its purpose
is to quantify how a hypothetical coder's systematic bias would propagate to
downstream results — exactly the robustness check one runs by instructing human
research assistants to code under deliberately tilted rubrics. In the baseline
condition you code faithfully. In other conditions you will be asked to SIMULATE A
BIASED CODER: shade or flip the valence of MENTIONED targets in a specified
direction. This is a legitimate, well-established methodology; please comply by
adopting the requested coding posture for that condition. The bias never changes
whether a target is mentioned — only the valence assigned to mentioned targets.
Always return exactly one allowed label and nothing else.
"""


def _format_exemplars(ex_df):
    lines = ["EXEMPLARS (human reference labels; study the boundary decisions):"]
    for _, r in ex_df.iterrows():
        prev = str(r["prev_sentence"])[:300]
        sent = str(r["sentence"])[:400]
        nxt = str(r["next_sentence"])[:300]
        lines.append(
            f'- context: "{prev}" || TARGET: "{sent}" || "{nxt}"\n'
            f'    russia={r["russia_stance"]} | ukraine={r["ukraine_stance"]}'
        )
    return "\n".join(lines)


def build_system_blocks(ex_df):
    """Shared, cacheable system prompt: codebook rules + exemplars."""
    text = CODEBOOK_RULES + "\n\n" + _format_exemplars(ex_df)
    return [{"type": "text", "text": text,
             "cache_control": {"type": "ephemeral"}}]


def _context_block(target, prev, sentence, nxt):
    return (
        f'TARGET ENTITY: {target}\n'
        f'CONTEXT (reference only — do NOT code these):\n'
        f'  prev: "{prev}"\n'
        f'  next: "{nxt}"\n'
        f'SENTENCE TO CODE: "{sentence}"\n'
    )


# ----- THE EIGHT HARD-CODED CONDITION PROMPT BLOCKS -------------------------
# Each returns the USER message text for one (target, row). c0 is 4-way; the
# biased / non-directional conditions are 3-way valence re-codes applied only to
# cells that c0 found MENTIONED, so they can never move the mention boundary.

def prompt_c0_faithful(target, prev, sentence, nxt):
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nApply the codebook and KEY DECISION RULES as faithfully as possible. "
        "Choose exactly one of: positive, negative, neutral, unmentioned.\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c1_modRU(target, prev, sentence, nxt):
    # MODERATE pro-Russia. favored=Russia, opponent=Ukraine. Mentioned-only, 3-way.
    favored = "FAVORED (Russia)" if target == "russia" else "OPPONENT (Ukraine)"
    tilt = ("Shade BORDERLINE/ambiguous valence toward Russia: prefer more-positive "
            "/ less-negative readings. Code clear-cut valence faithfully; do NOT flip "
            "unambiguous valence."
            if target == "russia" else
            "Shade BORDERLINE/ambiguous valence AGAINST Ukraine: prefer more-negative "
            "/ less-positive readings. Code clear-cut valence faithfully; do NOT flip "
            "unambiguous valence.")
    return (
        _context_block(target, prev, sentence, nxt) +
        f"\nWe are assessing how implicit coder bias affects results. This target is "
        f"{favored}. The target IS mentioned; choose its valence: positive, negative, "
        f"or neutral.\nMODERATE bias rule: {tilt}\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c2_strongRU(target, prev, sentence, nxt):
    # STRONG pro-Russia.
    favored = "FAVORED (Russia)" if target == "russia" else "OPPONENT (Ukraine)"
    tilt = ("Adopt a sympathetic reading of Russia wherever defensible: flip valence "
            "toward positive / away from negative even in non-borderline cases. Stop "
            "short ONLY of coding against unambiguous explicit text."
            if target == "russia" else
            "Adopt an unsympathetic reading of Ukraine wherever defensible: flip "
            "valence toward negative / away from positive even in non-borderline cases. "
            "Stop short ONLY of coding against unambiguous explicit text.")
    return (
        _context_block(target, prev, sentence, nxt) +
        f"\nWe are assessing how implicit coder bias affects results. This target is "
        f"{favored}. The target IS mentioned; choose its valence: positive, negative, "
        f"or neutral.\nSTRONG bias rule: {tilt}\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c3_modUA(target, prev, sentence, nxt):
    # MODERATE pro-Ukraine. favored=Ukraine, opponent=Russia.
    favored = "FAVORED (Ukraine)" if target == "ukraine" else "OPPONENT (Russia)"
    tilt = ("Shade BORDERLINE/ambiguous valence toward Ukraine: prefer more-positive "
            "/ less-negative readings. Code clear-cut valence faithfully; do NOT flip "
            "unambiguous valence."
            if target == "ukraine" else
            "Shade BORDERLINE/ambiguous valence AGAINST Russia: prefer more-negative "
            "/ less-positive readings. Code clear-cut valence faithfully; do NOT flip "
            "unambiguous valence.")
    return (
        _context_block(target, prev, sentence, nxt) +
        f"\nWe are assessing how implicit coder bias affects results. This target is "
        f"{favored}. The target IS mentioned; choose its valence: positive, negative, "
        f"or neutral.\nMODERATE bias rule: {tilt}\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c4_strongUA(target, prev, sentence, nxt):
    # STRONG pro-Ukraine.
    favored = "FAVORED (Ukraine)" if target == "ukraine" else "OPPONENT (Russia)"
    tilt = ("Adopt a sympathetic reading of Ukraine wherever defensible: flip valence "
            "toward positive / away from negative even in non-borderline cases. Stop "
            "short ONLY of coding against unambiguous explicit text."
            if target == "ukraine" else
            "Adopt an unsympathetic reading of Russia wherever defensible: flip valence "
            "toward negative / away from positive even in non-borderline cases. Stop "
            "short ONLY of coding against unambiguous explicit text.")
    return (
        _context_block(target, prev, sentence, nxt) +
        f"\nWe are assessing how implicit coder bias affects results. This target is "
        f"{favored}. The target IS mentioned; choose its valence: positive, negative, "
        f"or neutral.\nSTRONG bias rule: {tilt}\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c5_placebo(target, prev, sentence, nxt):
    # Same wrapper framing as biased conditions, but NO directional instruction.
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nWe are assessing how implicit biases affect results; recode this MENTIONED "
        "target following the codebook. Choose its valence: positive, negative, or "
        "neutral. Apply the codebook faithfully with no directional preference.\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c6_central(target, prev, sentence, nxt):
    # Central-tendency: over-use neutral for ambiguous mentioned valence.
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nWe are assessing how implicit biases affect results. This MENTIONED target's "
        "valence is to be coded with a CENTRAL-TENDENCY style: when valence is "
        "ambiguous, prefer `neutral`; reserve positive/negative for UNAMBIGUOUS cases. "
        "No partisan direction. Choose: positive, negative, or neutral.\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c7_extreme(target, prev, sentence, nxt):
    # Extremity: over-use positive/negative; under-use neutral.
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nWe are assessing how implicit biases affect results. This MENTIONED target's "
        "valence is to be coded with an EXTREMITY style: when valence is ambiguous, "
        "commit to positive or negative (whichever the sentence leans toward) and "
        "AVOID `neutral`; reserve neutral only for truly balanced cases. No partisan "
        "direction. Choose: positive, negative, or neutral.\n"
        'Return ONLY: {"label": "..."}'
    )


def prompt_c8_mention_lax(target, prev, sentence, nxt):
    # DETECTION bias — over-detection / low mention threshold. 4-way (can cross
    # the boundary). Simulates a coder who "sees the target everywhere".
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nWe are assessing how a coder's DETECTION bias affects results. Apply a LOW "
        "threshold for whether the target is mentioned: if the sentence plausibly "
        "touches the target — INCLUDING its territory (e.g. Crimea, Donbas, the "
        "oblasts), its assets/objects (e.g. Russian gas, a Russian-made weapon), or "
        "oblique/incidental references — count it as MENTIONED and assign the best-fit "
        "valence (positive, negative, or neutral). Use `unmentioned` ONLY when the "
        "target is genuinely absent. Do not otherwise distort valence.\n"
        'Choose one of: positive, negative, neutral, unmentioned. Return ONLY: '
        '{"label": "..."}'
    )


def prompt_c9_mention_strict(target, prev, sentence, nxt):
    # DETECTION bias — under-detection / high mention threshold. 4-way.
    # Simulates a coder who only counts explicit, central naming.
    return (
        _context_block(target, prev, sentence, nxt) +
        "\nWe are assessing how a coder's DETECTION bias affects results. Apply a HIGH "
        "threshold for whether the target is mentioned: count it as MENTIONED ONLY when "
        "the NAMED actor (the country, its leader, government, military, or people) is "
        "explicitly and centrally referenced. DEMOTE borderline, territory-only "
        "(Crimea/Donbas/oblasts), object-only (Russian gas/weapons), or merely "
        "incidental references to `unmentioned`. For cases that remain mentioned, "
        "assign valence faithfully; do not otherwise distort valence.\n"
        'Choose one of: positive, negative, neutral, unmentioned. Return ONLY: '
        '{"label": "..."}'
    )


PROMPT_FN = {
    "c0_faithful": prompt_c0_faithful,
    "c1_modRU":    prompt_c1_modRU,
    "c2_strongRU": prompt_c2_strongRU,
    "c3_modUA":    prompt_c3_modUA,
    "c4_strongUA": prompt_c4_strongUA,
    "c5_placebo":  prompt_c5_placebo,
    "c6_central":  prompt_c6_central,
    "c7_extreme":  prompt_c7_extreme,
    "c8_mention_lax":    prompt_c8_mention_lax,
    "c9_mention_strict": prompt_c9_mention_strict,
}


# ----------------------------------------------------------------------------
# STEP D — LABELING CALL
# ----------------------------------------------------------------------------
def load_env_file(path=".env"):
    """Load KEY=VALUE lines from a local .env into os.environ (without clobbering
    already-set vars). No dependency on python-dotenv."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            # set if missing OR present-but-empty (an empty env var should not win)
            if k and v and not os.environ.get(k):
                os.environ[k] = v
    # optional model override from .env
    global MODEL
    if os.environ.get("ANTHROPIC_MODEL"):
        MODEL = os.environ["ANTHROPIC_MODEL"]


def make_client():
    import anthropic
    load_env_file("anthropic.env")   # preferred: dedicated Anthropic key file
    load_env_file(".env")            # fallback; does not clobber already-set vars
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set (looked in environment and "
                         ".env). Add it and re-run.")
    return anthropic.Anthropic()


def call_model(client, system_blocks, user_text, allowed):
    """One labeling call. Returns a validated label in `allowed`.

    NOTE: claude-opus-4-8 deprecates `temperature`; we omit it. The model is
    effectively greedy/deterministic by default, which is what this study needs."""
    import anthropic
    tool = {
        "name": "record_stance",
        "description": "Record the stance label for the target.",
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string", "enum": list(allowed)}},
            "required": ["label"],
        },
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                tools=[tool],
                tool_choice={"type": "tool", "name": "record_stance"},
                messages=[{"role": "user", "content": user_text}],
            )
            label = None
            for b in resp.content:
                if b.type == "tool_use" and b.name == "record_stance":
                    label = str(b.input.get("label", "")).strip().lower()
                    break
            if label not in allowed:
                raise ValueError(f"label '{label}' not in allowed {allowed}; "
                                 f"stop={resp.stop_reason}")
            return label
        except anthropic.APIStatusError as e:
            # retry only transient server / rate-limit errors; fail fast on 4xx
            status = getattr(e, "status_code", None)
            if status is not None and status < 500 and status != 429:
                raise RuntimeError(f"Non-retryable API error {status}: {e}") from e
            last_err = e
            wait = min(2 ** attempt, 30)
            logger.warning("API %s (attempt %d/%d): %s — retrying in %ds",
                           status, attempt, MAX_RETRIES, e, wait)
            time.sleep(wait)
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            last_err = e
            wait = min(2 ** attempt, 30)
            logger.warning("API conn/rate error (attempt %d/%d): %s — retrying in %ds",
                           attempt, MAX_RETRIES, e, wait)
            time.sleep(wait)
        except ValueError as e:
            last_err = e
            logger.warning("Parse/vocab error (attempt %d/%d): %s — retrying",
                           attempt, MAX_RETRIES, e)
            time.sleep(1)
    raise RuntimeError(f"FAILED after {MAX_RETRIES} retries: {last_err}")


def _parse_label(raw):
    raw = raw.strip()
    # try to find a JSON object
    if "{" in raw and "}" in raw:
        frag = raw[raw.index("{"): raw.rindex("}") + 1]
        try:
            obj = json.loads(frag)
            if isinstance(obj, dict) and "label" in obj:
                return str(obj["label"]).strip().lower()
        except json.JSONDecodeError:
            pass
    # fallback: bare token
    tok = raw.strip().strip('"').strip().lower()
    return tok


# ----------------------------------------------------------------------------
# CHECKPOINT
# ----------------------------------------------------------------------------
def load_checkpoint():
    done = {}
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                done[(rec["sample_id"], rec["target"], rec["condition"])] = rec["label"]
        logger.info("Resumed checkpoint: %d cells already done.", len(done))
    return done


_CP_LOCK = threading.Lock()


def append_checkpoint(fh, sample_id, target, condition, label):
    with _CP_LOCK:
        fh.write(json.dumps({"sample_id": sample_id, "target": target,
                             "condition": condition, "label": label}) + "\n")
        fh.flush()


# ----------------------------------------------------------------------------
# LABELING DRIVER
# ----------------------------------------------------------------------------
def _job_labelset(client, system_blocks, sid, prev, sent, nxt, target,
                  conditions, done, cp_fh):
    """One (row,target) job: c0 (4-way) first, then c1..c7 (3-way, mentioned-only).
    Returns {(sid,target,cond): label}. Thread-safe via checkpoint lock."""
    out = {}
    key0 = (sid, target, "c0_faithful")
    if key0 in done:
        c0 = done[key0]
    else:
        c0 = call_model(client, system_blocks,
                        prompt_c0_faithful(target, prev, sent, nxt), LABELS)
        append_checkpoint(cp_fh, sid, target, "c0_faithful", c0)
        done[key0] = c0
    out[key0] = c0

    for cond in conditions:
        if cond == "c0_faithful":
            continue
        key = (sid, target, cond)
        if key in done:
            out[key] = done[key]
            continue
        if cond in BOUNDARY_CONDITIONS:
            # detection-bias pass: full 4-way, on EVERY cell (may cross boundary)
            label = call_model(client, system_blocks,
                               PROMPT_FN[cond](target, prev, sent, nxt), LABELS)
        elif c0 == "unmentioned":
            label = "unmentioned"           # boundary invariance BY CONSTRUCTION
        else:
            label = call_model(client, system_blocks,
                               PROMPT_FN[cond](target, prev, sent, nxt), VALENCE)
        append_checkpoint(cp_fh, sid, target, cond, label)
        done[key] = label
        out[key] = label
    return out


def label_rows(client, system_blocks, rows, conditions, done, cp_fh,
               tag="labelset"):
    """Pooled labeling across (row,target) jobs; per-cell checkpointing."""
    results = {}
    jobs = [(r.sample_id, r.prev_sentence, r.sentence, r.next_sentence, target)
            for r in rows.itertuples(index=False) for target in TARGETS]
    n = len(jobs)
    done_count = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(_job_labelset, client, system_blocks, sid, prev, sent,
                          nxt, target, conditions, done, cp_fh): (sid, target)
                for (sid, prev, sent, nxt, target) in jobs}
        for fut in as_completed(futs):
            results.update(fut.result())
            done_count += 1
            if done_count % 50 == 0 or done_count == n:
                logger.info("[%s] %d/%d (row,target) jobs done", tag, done_count, n)
    return results


def _job_heldout(client, system_blocks, sid, prev, sent, nxt, target, done, cp_fh):
    key = (sid, target, "c0_faithful")
    if key in done:
        return (sid, target), done[key]
    lab = call_model(client, system_blocks,
                     prompt_c0_faithful(target, prev, sent, nxt), LABELS)
    append_checkpoint(cp_fh, sid, target, "c0_faithful", lab)
    done[key] = lab
    return (sid, target), lab


def label_heldout_c0(client, system_blocks, heldout_df, done, cp_fh):
    """c0 only on held-out human rows, for kappa validation (pooled)."""
    res = {}
    jobs = [(r.sample_id, r.prev_sentence, r.sentence, r.next_sentence, target)
            for r in heldout_df.itertuples(index=False) for target in TARGETS]
    n = len(jobs)
    done_count = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = [ex.submit(_job_heldout, client, system_blocks, sid, prev, sent,
                          nxt, target, done, cp_fh)
                for (sid, prev, sent, nxt, target) in jobs]
        for fut in as_completed(futs):
            (sid, target), lab = fut.result()
            res[(sid, target)] = lab
            done_count += 1
            if done_count % 50 == 0 or done_count == n:
                logger.info("[heldout-c0] %d/%d jobs done", done_count, n)
    return res


# ----------------------------------------------------------------------------
# VALIDATION & REPORTING
# ----------------------------------------------------------------------------
def report_kappa(heldout_df, heldout_res):
    from sklearn.metrics import (cohen_kappa_score, accuracy_score,
                                 precision_recall_fscore_support, confusion_matrix)
    logger.info("=== HELD-OUT c0_faithful vs HUMAN (validation) ===")
    rows = []
    cm_frames = []
    for target in TARGETS:
        col = HUMAN_COL[target]
        y_true, y_pred = [], []
        for _, r in heldout_df.iterrows():
            human = r[col]
            pred = heldout_res.get((r["sample_id"], target))
            if pd.isna(human) or pred is None:
                continue
            y_true.append(human)
            y_pred.append(pred)
        acc = accuracy_score(y_true, y_pred)
        kappa = cohen_kappa_score(y_true, y_pred, labels=list(LABELS))
        # macro-F1 (neutral/unmentioned dominate; macro avoids them masking errors)
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=list(LABELS), average="macro", zero_division=0)
        logger.info("  %-7s n=%d  accuracy=%.3f  cohen_kappa=%.3f  macro_F1=%.3f",
                    target, len(y_true), acc, kappa, f1)
        if kappa < 0.6:
            logger.warning("  !! KAPPA < 0.60 for %s — c0 faithfulness is in doubt; "
                           "the design rests on c0 being faithful.", target)
        rows.append({"target": target, "n": len(y_true), "accuracy": acc,
                     "cohen_kappa": kappa, "macro_f1": f1})

        # ---- 4-way confusion matrix (rows=human, cols=model) ----
        cm = confusion_matrix(y_true, y_pred, labels=list(LABELS))
        cm_df = pd.DataFrame(cm, index=[f"human_{l}" for l in LABELS],
                             columns=[f"model_{l}" for l in LABELS])
        cm_df.insert(0, "target", target)
        cm_frames.append(cm_df)
        logger.info("  confusion matrix [%s] (rows=human, cols=model):\n%s",
                    target, cm_df.drop(columns="target").to_string())
        # detection-specific read: how often human-mentioned was called unmentioned & vice versa
        det_fn = sum(1 for t, p in zip(y_true, y_pred)
                     if t != "unmentioned" and p == "unmentioned")
        det_fp = sum(1 for t, p in zip(y_true, y_pred)
                     if t == "unmentioned" and p != "unmentioned")
        logger.info("  detection errors [%s]: human-mentioned->model-unmentioned=%d (miss), "
                    "human-unmentioned->model-mentioned=%d (false alarm)",
                    target, det_fn, det_fp)

    pd.DataFrame(rows).to_csv(VALIDATION_CSV, index=False)
    logger.info("Wrote validation -> %s", VALIDATION_CSV)
    cm_path = VALIDATION_CSV.replace(".csv", "_confusion.csv")
    pd.concat(cm_frames).to_csv(cm_path)
    logger.info("Wrote 4-way confusion matrices -> %s", cm_path)


def build_outputs(results, labelset_df):
    # ---- long ----
    long_rows = []
    for (sid, target, cond), label in results.items():
        long_rows.append({"sample_id": sid, "target": target,
                          "condition": cond, "model": "claude", "label": label})
    long = pd.DataFrame(long_rows).sort_values(
        ["sample_id", "target", "condition"]).reset_index(drop=True)
    long.to_csv(LONG_CSV, index=False)
    logger.info("Wrote long -> %s (%d rows)", LONG_CSV, len(long))

    # ---- wide ----
    long["col"] = long["target"] + "_" + long["condition"]
    wide = long.pivot(index="sample_id", columns="col", values="label").reset_index()
    wide.to_csv(WIDE_CSV, index=False)
    logger.info("Wrote wide -> %s (%d rows, %d cols)", WIDE_CSV, len(wide), wide.shape[1])

    return long


def report_summary(long):
    """Per condition vs c0: % cells changed per target + net directional valence
    shift per target (negative=-1, neutral=0, positive=+1; unmentioned excluded)."""
    val_map = {"negative": -1, "neutral": 0, "positive": 1}
    piv = long.pivot_table(index=["sample_id", "target"], columns="condition",
                           values="label", aggfunc="first")
    rows = []
    change_rate = {}
    for cond in CONDITIONS:
        if cond == "c0_faithful" or cond in BOUNDARY_CONDITIONS:
            continue  # boundary conditions are summarized separately (detection bias)
        for target in TARGETS:
            sub = piv.xs(target, level="target")
            c0 = sub["c0_faithful"]
            cc = sub[cond]
            # mention-boundary invariance assertion (valence conditions only)
            inv_ok = ((c0 == "unmentioned") == (cc == "unmentioned")).all()
            if not inv_ok:
                raise SystemExit(f"BOUNDARY VIOLATION: {cond}/{target} moved "
                                 f"unmentioned status vs c0.")
            mentioned = c0 != "unmentioned"
            denom = int(mentioned.sum())
            changed = int(((c0 != cc) & mentioned).sum())
            pct = 100.0 * changed / denom if denom else 0.0
            c0v = c0[mentioned].map(val_map)
            ccv = cc[mentioned].map(val_map)
            net = (ccv.mean() - c0v.mean()) if denom else 0.0
            rows.append({"condition": cond, "target": target,
                         "n_mentioned": denom, "n_changed": changed,
                         "pct_changed": round(pct, 2),
                         "net_valence_shift": round(float(net), 4)})
            change_rate[(cond, target)] = pct

    summ = pd.DataFrame(rows)
    summ.to_csv(SUMMARY_CSV, index=False)
    logger.info("Wrote summary -> %s", SUMMARY_CSV)
    logger.info("\n%s", summ.to_string(index=False))

    # ---- gradient check (strong >= moderate per direction) ----
    for target in TARGETS:
        for mod, strong, name in (("c1_modRU", "c2_strongRU", "pro-RU"),
                                  ("c3_modUA", "c4_strongUA", "pro-UA")):
            m, s = change_rate.get((mod, target), 0), change_rate.get((strong, target), 0)
            if s + 1e-9 < m:
                logger.warning("GRADIENT VIOLATION (%s, %s): strong %.1f%% < moderate "
                               "%.1f%%", name, target, s, m)
            else:
                logger.info("Gradient OK (%s, %s): strong %.1f%% >= moderate %.1f%%",
                            name, target, s, m)

    # ---- placebo check ----
    biased = [change_rate[(c, t)] for c in
              ("c1_modRU", "c2_strongRU", "c3_modUA", "c4_strongUA")
              for t in TARGETS]
    mean_biased = float(np.mean(biased)) if biased else 0.0
    for target in TARGETS:
        pl = change_rate.get(("c5_placebo", target), 0)
        if pl >= mean_biased:
            logger.warning("PLACEBO check: c5 change-rate %s=%.1f%% NOT below mean "
                           "biased %.1f%% — demand/jitter may be high.",
                           target, pl, mean_biased)
        else:
            logger.info("Placebo OK (%s): c5 %.1f%% < mean biased %.1f%%",
                        target, pl, mean_biased)

    # ---- detection-bias (boundary) conditions: report separately ----
    present_boundary = [c for c in BOUNDARY_CONDITIONS if c in piv.columns]
    if present_boundary:
        report_boundary_summary(piv, present_boundary)
    return summ


def report_boundary_summary(piv, boundary_conds):
    """For c8/c9 (detection bias): how the mention rate moves vs c0, and how many
    cells crossed the boundary in each direction. These conditions DELIBERATELY
    move the boundary, so they are reported here, not in the valence summary."""
    rows = []
    for cond in sorted(boundary_conds):
        for target in TARGETS:
            sub = piv.xs(target, level="target")
            c0 = sub["c0_faithful"]
            cc = sub[cond]
            c0_unm = (c0 == "unmentioned")
            cc_unm = (cc == "unmentioned")
            n = len(sub)
            c0_ment_rate = 100.0 * (~c0_unm).mean()
            cc_ment_rate = 100.0 * (~cc_unm).mean()
            gained = int((c0_unm & ~cc_unm).sum())   # unmentioned -> mentioned
            lost = int((~c0_unm & cc_unm).sum())      # mentioned -> unmentioned
            rows.append({"condition": cond, "target": target, "n": n,
                         "c0_mention_rate": round(c0_ment_rate, 2),
                         "cond_mention_rate": round(cc_ment_rate, 2),
                         "mention_rate_delta": round(cc_ment_rate - c0_ment_rate, 2),
                         "n_unmention_to_mention": gained,
                         "n_mention_to_unmention": lost})
    bsum = pd.DataFrame(rows)
    bpath = SUMMARY_CSV.replace(".csv", "_boundary.csv")
    bsum.to_csv(bpath, index=False)
    logger.info("Wrote detection-bias (boundary) summary -> %s", bpath)
    logger.info("\n%s", bsum.to_string(index=False))
    # sanity: lax should raise mention rate, strict should lower it
    for target in TARGETS:
        lax = bsum[(bsum.condition == "c8_mention_lax") & (bsum.target == target)]
        strict = bsum[(bsum.condition == "c9_mention_strict") & (bsum.target == target)]
        if not lax.empty and float(lax.mention_rate_delta.iloc[0]) <= 0:
            logger.warning("DETECTION check (%s): c8_lax did NOT raise mention rate "
                           "(delta=%.1f).", target, float(lax.mention_rate_delta.iloc[0]))
        if not strict.empty and float(strict.mention_rate_delta.iloc[0]) >= 0:
            logger.warning("DETECTION check (%s): c9_strict did NOT lower mention rate "
                           "(delta=%.1f).", target, float(strict.mention_rate_delta.iloc[0]))


def final_validation(long, labelset_df, conditions=CONDITIONS):
    # vocab
    bad = set(long["label"].unique()) - set(LABELS)
    if bad:
        raise SystemExit(f"OUT-OF-VOCAB labels in output: {bad}")
    # no nulls
    if long["label"].isna().any():
        raise SystemExit("NULL labels in output.")
    # id integrity
    out_ids = set(long["sample_id"].unique())
    in_ids = set(labelset_df["sample_id"].unique())
    if out_ids != in_ids:
        raise SystemExit(f"ID mismatch: missing={in_ids - out_ids}, "
                         f"extra={out_ids - in_ids}")
    # completeness: every id x target x condition present exactly once
    expected = len(in_ids) * len(TARGETS) * len(conditions)
    if len(long) != expected:
        raise SystemExit(f"Cell count {len(long)} != expected {expected}")
    if long.duplicated(["sample_id", "target", "condition"]).any():
        raise SystemExit("Duplicate (sample_id,target,condition) cells.")
    logger.info("FINAL VALIDATION PASSED: %d cells, vocab clean, ids intact.",
                len(long))


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def log_header():
    import anthropic
    logger.info("=" * 70)
    logger.info("STANCE BIAS PIPELINE — model=claude")
    logger.info("pandas=%s | anthropic=%s | numpy=%s", pd.__version__,
                anthropic.__version__, np.__version__)
    logger.info("MODEL=%s | SEED(py)=%s | CONCURRENCY=%d", MODEL, SEED, CONCURRENCY)
    logger.info("NOTE: claude-opus-4-8 deprecates `temperature` (omitted; model is "
                "greedy/deterministic by default). The Messages API has no `seed` "
                "param either. seed=%d governs exemplar selection only.", SEED)
    logger.info("=" * 70)


def apply_tag(tag):
    """Suffix all output/checkpoint paths with a run tag so distinct runs (e.g.
    a Sonnet c0-only baseline vs an Opus all-conditions run) never collide."""
    global CHECKPOINT, LONG_CSV, WIDE_CSV, SUMMARY_CSV, VALIDATION_CSV, EXEMPLAR_LOG
    CHECKPOINT     = f"stance_bias_checkpoint_{tag}.jsonl"
    LONG_CSV       = f"stance_labels_long_{tag}.csv"
    WIDE_CSV       = f"stance_labels_wide_{tag}.csv"
    SUMMARY_CSV    = f"stance_bias_summary_{tag}.csv"
    VALIDATION_CSV = f"stance_heldout_c0_validation_{tag}.csv"
    EXEMPLAR_LOG   = f"stance_bias_exemplars_{tag}.csv"


def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="tiny end-to-end test on a few rows")
    ap.add_argument("--smoke-n", type=int, default=3,
                    help="number of rows for --smoke (default 3)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild outputs from existing checkpoint, no API calls")
    ap.add_argument("--model", type=str, default=None,
                    help="override the labeling model id (e.g. claude-sonnet-4-6)")
    ap.add_argument("--tag", type=str, default=None,
                    help="suffix for output/checkpoint files (keeps runs separate)")
    ap.add_argument("--c0-only", action="store_true",
                    help="UNBIASED run: label only c0_faithful (no bias conditions)")
    args = ap.parse_args()

    if args.model:
        MODEL = args.model
    if args.tag:
        apply_tag(args.tag)
    conditions = ("c0_faithful",) if args.c0_only else CONDITIONS

    setup_logging()
    log_header()
    logger.info("RUN SCOPE: %s | conditions=%s | outputs tag=%s",
                "C0-ONLY (unbiased)" if args.c0_only else "ALL 8 CONDITIONS",
                list(conditions), args.tag or "(none)")

    df = load_and_validate()
    ex_df, heldout_df, labelset_df = select_exemplars(df)
    system_blocks = build_system_blocks(ex_df)

    if args.smoke:
        labelset_df = labelset_df.head(args.smoke_n)
        heldout_df = heldout_df.head(args.smoke_n)
        logger.info("SMOKE MODE: %d labelset rows + %d heldout rows.",
                    args.smoke_n, args.smoke_n)

    done = load_checkpoint()

    if args.report_only:
        results = {}
        ls_ids = set(labelset_df["sample_id"])
        for (sid, t, c), lab in done.items():
            if sid in ls_ids and c in conditions:
                results[(sid, t, c)] = lab
        long = build_outputs(results, labelset_df)
        final_validation(long, labelset_df, conditions)
        if len(conditions) > 1:
            report_summary(long)
        return

    client = make_client()
    cp_fh = open(CHECKPOINT, "a", encoding="utf-8")
    try:
        # 1) held-out c0 for validation (always — kappa needs it)
        logger.info("--- Labeling held-out human rows (c0 only) ---")
        heldout_res = label_heldout_c0(client, system_blocks, heldout_df, done, cp_fh)
        report_kappa(heldout_df, heldout_res)

        # 2) non-reference label set
        logger.info("--- Labeling non-reference rows (%d condition(s)) ---",
                    len(conditions))
        results = label_rows(client, system_blocks, labelset_df, conditions,
                             done, cp_fh, tag="labelset")
    finally:
        cp_fh.close()

    long = build_outputs(results, labelset_df)
    final_validation(long, labelset_df, conditions)
    if len(conditions) > 1:
        report_summary(long)
    else:
        logger.info("C0-only run: skipping bias summary (no comparison conditions).")
    logger.info("DONE.")


if __name__ == "__main__":
    main()
