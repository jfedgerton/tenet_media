"""Run the Codex stance-labeling bias-sensitivity pipeline.

This script labels stance_train_1500.csv under the requested sensitivity conditions.
It intentionally keeps the condition prompt blocks explicit and named.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.metadata as md
import json
import logging
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import winreg
except ImportError:  # pragma: no cover - only absent off Windows.
    winreg = None


SEED = 123
MODEL_TAG = "codex"
TARGETS = ("russia", "ukraine")
CONDITIONS = (
    "c0_faithful",
    "c1_modRU",
    "c2_strongRU",
    "c3_modUA",
    "c4_strongUA",
    "c5_placebo",
    "c6_central",
    "c7_extreme",
    "c8_mention_lax",
    "c9_mention_strict",
)
LABELS = ("negative", "neutral", "positive", "unmentioned")
MENTIONED_LABELS = ("negative", "neutral", "positive")
ORDINAL = {"negative": -1, "neutral": 0, "positive": 1}
DETECTION_CONDITIONS = ("c8_mention_lax", "c9_mention_strict")
DETECTION_PLACEHOLDER_PREFIXES = ("mentioned",)
STRICT_UNMENTIONED_HINTS = (
    "not explicit",
    "not explicitly",
    "not central",
    "not centrally",
    "incidental",
    "oblique",
    "territory",
    "object",
    "asset",
)


COMMON_CODEBOOK_BLOCK = """
You are an expert political-communication coder for legitimate academic research.
Apply the same stance codebook in every condition. Code ONLY the target sentence.
The previous and next sentences are context only, for resolving references; do not
code stance expressed only in those context sentences.

Two targets are in scope: russia and ukraine. Assad is out of scope.
The United States is not a coded target and is not an opponent entity.

Return exactly one label for each coded target:
- positive: sympathetic/supportive/justifying/favorable toward the target.
- negative: critical/hostile/condemning/blaming toward the target.
- neutral: target is mentioned, but the sentence is factual, incidental, balanced,
  ambiguous, or has no discernible position toward that target.
- unmentioned: the target is not referenced in the target sentence.

Hard decision rules:
1. Mention requires the named actor: country, leader, government, military, or
   people. Territory or objects alone, such as Crimea, Donbas, oblasts, or
   Russian gas, do not make the country mentioned.
2. unmentioned is not neutral.
3. Code position toward the target, not emotional tone.
4. Battlefield success or strength is neutral unless explicitly endorsed.
5. Evaluative words like aggression, blunder, brutal, corrupt, dictator, or Nazi
   can carry stance; flat descriptors like invasion, controls, or consolidation
   do not by themselves.
6. Stance-via-opponent counts only when the target itself is named in the
   target sentence.
7. Axes are independent: anti-Ukraine is not automatically pro-Russia, and
   anti-Russia is not automatically pro-Ukraine.
8. Incidental mentions used only to attack a third party are neutral.
""".strip()


RETURN_JSON_BLOCK = """
Output ONLY valid JSON with this exact shape:
{"russia":"positive|negative|neutral|unmentioned","ukraine":"positive|negative|neutral|unmentioned"}
Do not include notes, markdown, or extra keys.
""".strip()


PROMPT_C0_FAITHFUL = """
CONDITION c0_faithful:
Code faithfully to the codebook and decision rules. Use the exemplars only as
calibration. Do not introduce directional bias.
""".strip()


PROMPT_C1_MODRU = """
CONDITION c1_modRU:
Moderate pro-Russia sensitivity condition. Apply the same codebook and the same
mention boundary as c0. For mentioned targets only, resolve borderline or
ambiguous valence toward the favored side:
- favored target: Russia. When Russia is mentioned and valence is borderline,
  choose the more-positive or less-negative defensible label.
- opponent target: Ukraine. When Ukraine is mentioned and valence is borderline,
  choose the more-negative or less-positive defensible label.
Do not flip clear-cut, unambiguous faithful labels.
""".strip()


PROMPT_C2_STRONGRU = """
CONDITION c2_strongRU:
Strong pro-Russia sensitivity condition. Apply the same codebook and the same
mention boundary as c0. For mentioned targets only, use the moderate pro-Russia
tilt and extend it beyond purely borderline cases: give Russia the sympathetic
reading wherever defensible, and give Ukraine the skeptical/critical reading
wherever defensible. You may flip non-borderline cases when a biased but still
defensible reading exists. Stop short of contradicting unambiguous explicit text.
""".strip()


PROMPT_C3_MODUA = """
CONDITION c3_modUA:
Moderate pro-Ukraine sensitivity condition. Apply the same codebook and the same
mention boundary as c0. For mentioned targets only, resolve borderline or
ambiguous valence toward the favored side:
- favored target: Ukraine. When Ukraine is mentioned and valence is borderline,
  choose the more-positive or less-negative defensible label.
- opponent target: Russia. When Russia is mentioned and valence is borderline,
  choose the more-negative or less-positive defensible label.
Do not flip clear-cut, unambiguous faithful labels.
""".strip()


PROMPT_C4_STRONGUA = """
CONDITION c4_strongUA:
Strong pro-Ukraine sensitivity condition. Apply the same codebook and the same
mention boundary as c0. For mentioned targets only, use the moderate pro-Ukraine
tilt and extend it beyond purely borderline cases: give Ukraine the sympathetic
reading wherever defensible, and give Russia the skeptical/critical reading
wherever defensible. You may flip non-borderline cases when a biased but still
defensible reading exists. Stop short of contradicting unambiguous explicit text.
""".strip()


PROMPT_C5_PLACEBO = """
CONDITION c5_placebo:
Placebo sensitivity condition. Use the identical coding wrapper and the same
codebook as c0, but apply no directional instruction. Code faithfully. The result
should be very close to c0 except for ordinary model uncertainty.
""".strip()


PROMPT_C6_CENTRAL = """
CONDITION c6_central:
Non-directional centralizing sensitivity condition. Apply the same codebook and
the same mention boundary as c0. For mentioned targets only, over-use neutral
when valence is ambiguous, mixed, weak, or not fully explicit. Leave unmentioned
targets unmentioned.
""".strip()


PROMPT_C7_EXTREME = """
CONDITION c7_extreme:
Non-directional extremizing sensitivity condition. Apply the same codebook and
the same mention boundary as c0. For mentioned targets only, avoid neutral when
there is any defensible evaluative valence; choose positive or negative according
to the direction of that valence. Leave unmentioned targets unmentioned.
""".strip()


PROMPT_C8_MENTION_LAX = """
CONDITION c8_mention_lax:
We are assessing how a coder's DETECTION bias affects results. Apply a LOW
threshold for whether the target is mentioned: if the sentence plausibly touches
the target - INCLUDING its territory (e.g. Crimea, Donbas, the oblasts), its
assets/objects (e.g. Russian gas, a Russian-made weapon), or oblique/incidental
references - count it as MENTIONED and assign the best-fit valence (positive,
negative, or neutral). Use `unmentioned` ONLY when the target is genuinely absent.
Do not otherwise distort valence.
Allowed labels: positive, negative, neutral, unmentioned.
Apply this detection threshold separately to BOTH targets, Russia and Ukraine.
""".strip()


PROMPT_C9_MENTION_STRICT = """
CONDITION c9_mention_strict:
We are assessing how a coder's DETECTION bias affects results. Apply a HIGH
threshold for whether the target is mentioned: count it as MENTIONED ONLY when the
NAMED actor (the country, its leader, government, military, or people) is
explicitly and centrally referenced. DEMOTE borderline, territory-only
(Crimea/Donbas/oblasts), object-only (Russian gas/weapons), or merely incidental
references to `unmentioned`. For cases that remain mentioned, assign valence
faithfully; do not otherwise distort valence.
Allowed labels: positive, negative, neutral, unmentioned.
Apply this detection threshold separately to BOTH targets, Russia and Ukraine.
""".strip()


CONDITION_PROMPTS = {
    "c0_faithful": PROMPT_C0_FAITHFUL,
    "c1_modRU": PROMPT_C1_MODRU,
    "c2_strongRU": PROMPT_C2_STRONGRU,
    "c3_modUA": PROMPT_C3_MODUA,
    "c4_strongUA": PROMPT_C4_STRONGUA,
    "c5_placebo": PROMPT_C5_PLACEBO,
    "c6_central": PROMPT_C6_CENTRAL,
    "c7_extreme": PROMPT_C7_EXTREME,
    "c8_mention_lax": PROMPT_C8_MENTION_LAX,
    "c9_mention_strict": PROMPT_C9_MENTION_STRICT,
}


def package_version(package: str) -> str:
    try:
        return md.version(package)
    except md.PackageNotFoundError:
        return "NOT INSTALLED"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def windows_env_value(name: str) -> str | None:
    if winreg is None:
        return None
    locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if value:
            return str(value)
    return None


def env_value(name: str) -> str | None:
    return os.environ.get(name) or windows_env_value(name)


def setup_logging(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "stance_codex_run.log"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return log_path


def read_csv_checked(path: Path) -> pd.DataFrame:
    required = [
        "sample_id",
        "prev_sentence",
        "sentence",
        "next_sentence",
        "russia_stance",
        "ukraine_stance",
        "notes",
    ]
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    duplicate_count = len(df) - df["sample_id"].nunique()
    if duplicate_count:
        raise ValueError(f"sample_id must be unique; duplicates: {duplicate_count}")
    for col in ("russia_stance", "ukraine_stance"):
        nonblank = df[col].map(lambda value: str(value).strip()).loc[lambda s: s != ""]
        invalid = sorted(set(nonblank) - set(LABELS))
        if invalid:
            raise ValueError(f"{col} has out-of-vocabulary labels: {invalid}")
    partial = (
        df[["russia_stance", "ukraine_stance"]]
        .map(lambda value: str(value).strip() != "")
        .sum(axis=1)
        .eq(1)
    )
    if partial.any():
        raise ValueError("Some human rows have only one stance column populated")
    return df


def log_step0_assertions(df: pd.DataFrame, codebook_path: Path) -> None:
    human_mask = (
        df[["russia_stance", "ukraine_stance"]]
        .map(lambda value: str(value).strip() != "")
        .any(axis=1)
    )
    logging.info("STEP 0 ASSERTIONS")
    logging.info("Data file rows: %s", len(df))
    logging.info("Columns: %s", list(df.columns))
    logging.info("Text column: sentence; context columns: prev_sentence,next_sentence")
    logging.info("Human columns present: russia_stance, ukraine_stance")
    logging.info("Rows with nonblank human labels: %s", int(human_mask.sum()))
    for col in ("russia_stance", "ukraine_stance"):
        counts = Counter(value for value in df[col].map(str.strip) if value)
        logging.info("%s label counts: %s", col, dict(sorted(counts.items())))
    logging.info("Codebook path: %s", codebook_path.resolve())
    logging.info("Codebook defines russia, ukraine, assad; in-scope targets: %s", TARGETS)
    logging.info("Assad is out of scope and is not coded")


def choose_exemplars(
    df: pd.DataFrame, exemplars_per_cell: int, output_dir: Path
) -> tuple[set[str], dict[str, dict[str, list[str]]]]:
    rng = random.Random(SEED)
    chosen_by_cell: dict[str, dict[str, list[str]]] = {target: {} for target in TARGETS}
    exemplar_ids: set[str] = set()
    for target in TARGETS:
        col = f"{target}_stance"
        for label in LABELS:
            available = sorted(
                df.loc[df[col].map(str.strip).eq(label), "sample_id"].tolist()
            )
            if len(available) < exemplars_per_cell:
                raise ValueError(
                    f"Not enough exemplars for {target} x {label}: "
                    f"{len(available)} available"
                )
            picked = sorted(rng.sample(available, exemplars_per_cell))
            chosen_by_cell[target][label] = picked
            exemplar_ids.update(picked)
            logging.info(
                "Exemplar cell %s x %s: %s", target, label, ",".join(picked)
            )
    logging.info(
        "Exemplar union count: %s; sample_ids: %s",
        len(exemplar_ids),
        ",".join(sorted(exemplar_ids)),
    )
    if not 60 <= len(exemplar_ids) <= 90:
        logging.warning("Exemplar union is outside requested ~60-90 range")
    payload = {
        "seed": SEED,
        "exemplars_per_cell": exemplars_per_cell,
        "chosen_by_cell": chosen_by_cell,
        "exemplar_ids": sorted(exemplar_ids),
    }
    path = output_dir / "stance_codex_exemplars.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return exemplar_ids, chosen_by_cell


def exemplar_block(df: pd.DataFrame, chosen_by_cell: dict[str, dict[str, list[str]]]) -> str:
    lines = ["EXEMPLARS FROM HUMAN-CODED ROWS (calibration only):"]
    seen = set()
    for target in TARGETS:
        col = f"{target}_stance"
        lines.append(f"\nTarget: {target}")
        for label in LABELS:
            lines.append(f"{label}:")
            for sample_id in chosen_by_cell[target][label]:
                row = df.loc[df["sample_id"].eq(sample_id)].iloc[0]
                key = (target, sample_id)
                if key in seen:
                    continue
                seen.add(key)
                text = str(row["sentence"]).replace("\n", " ").strip()
                lines.append(f"- {sample_id}: {text} => {row[col].strip()}")
    return "\n".join(lines)


def build_messages(
    condition: str,
    row: pd.Series,
    exemplars: str,
    c0_labels: dict[str, str] | None = None,
    correction: str | None = None,
) -> list[dict[str, str]]:
    parts = [
        COMMON_CODEBOOK_BLOCK,
        CONDITION_PROMPTS[condition],
        exemplars,
        RETURN_JSON_BLOCK,
    ]
    if (
        c0_labels is not None
        and condition != "c0_faithful"
        and condition not in DETECTION_CONDITIONS
    ):
        parts.append(
            "MENTION-BOUNDARY LOCK FROM c0_faithful:\n"
            f"russia c0 label: {c0_labels['russia']}\n"
            f"ukraine c0 label: {c0_labels['ukraine']}\n"
            "For every target whose c0 label is unmentioned, return unmentioned. "
            "For every target whose c0 label is mentioned, return a mentioned "
            "label: negative, neutral, or positive."
        )
    if correction:
        parts.append(f"CORRECTION REQUIRED: {correction}")

    user = (
        f"sample_id: {row['sample_id']}\n"
        f"previous sentence context: {row['prev_sentence']}\n"
        f"TARGET SENTENCE TO CODE: {row['sentence']}\n"
        f"next sentence context: {row['next_sentence']}\n"
    )
    return [
        {"role": "system", "content": "\n\n".join(parts)},
        {"role": "user", "content": user},
    ]


class OpenAIChatClient:
    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str,
        timeout: int,
        max_retries: int,
        retry_sleep: float,
        max_completion_tokens: int,
        reasoning_effort: str | None,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it before running the labeling pass."
            )
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep
        self.max_completion_tokens = max_completion_tokens
        self.reasoning_effort = reasoning_effort
        self.include_temperature = not self.model.startswith("gpt-5")
        self.include_seed = True
        self.include_max_completion_tokens = True
        self.include_reasoning_effort = bool(reasoning_effort)

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if self.include_temperature:
            payload["temperature"] = 0
        if self.include_seed:
            payload["seed"] = SEED
        if self.include_max_completion_tokens:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if self.include_reasoning_effort and self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        url = f"{self.base_url}/chat/completions"
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {detail}"
                lowered = detail.lower()
                if "seed" in lowered and "unsupported" in lowered:
                    self.include_seed = False
                    payload.pop("seed", None)
                if "temperature" in lowered and "unsupported" in lowered:
                    self.include_temperature = False
                    payload.pop("temperature", None)
                if "max_completion_tokens" in lowered and "unsupported" in lowered:
                    self.include_max_completion_tokens = False
                    payload.pop("max_completion_tokens", None)
                if "reasoning_effort" in lowered and "unsupported" in lowered:
                    self.include_reasoning_effort = False
                    payload.pop("reasoning_effort", None)
            except Exception as exc:  # noqa: BLE001 - logged and retried deliberately.
                last_error = f"{type(exc).__name__}: {exc}"
            logging.warning("API attempt %s/%s failed: %s", attempt, self.max_retries, last_error)
            time.sleep(self.retry_sleep * attempt)
        raise RuntimeError(f"OpenAI API call failed after retries: {last_error}")


def parse_labels(raw: str, detection_condition: str | None = None) -> dict[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(raw[start : end + 1])
    labels = {target: str(data.get(target, "")).strip().lower() for target in TARGETS}
    if detection_condition:
        for target, label in list(labels.items()):
            if any(label == prefix or label.startswith(f"{prefix} ") for prefix in DETECTION_PLACEHOLDER_PREFIXES):
                replacement = "neutral"
                if detection_condition == "c9_mention_strict" and any(
                    hint in label for hint in STRICT_UNMENTIONED_HINTS
                ):
                    replacement = "unmentioned"
                logging.warning(
                    "Detection placeholder label coerced to %s for %s: %s",
                    replacement,
                    target,
                    label,
                )
                labels[target] = replacement
    bad = {target: label for target, label in labels.items() if label not in LABELS}
    if bad:
        raise ValueError(f"Out-of-vocabulary labels: {bad}; raw={raw!r}")
    return labels


def boundary_error(c0_labels: dict[str, str], labels: dict[str, str]) -> str | None:
    errors = []
    for target in TARGETS:
        c0_unmentioned = c0_labels[target] == "unmentioned"
        label_unmentioned = labels[target] == "unmentioned"
        if c0_unmentioned != label_unmentioned:
            errors.append(
                f"{target} c0={c0_labels[target]} condition={labels[target]}"
            )
    if errors:
        return "; ".join(errors)
    return None


def repair_boundary(c0_labels: dict[str, str], labels: dict[str, str]) -> dict[str, str]:
    repaired = dict(labels)
    for target in TARGETS:
        if c0_labels[target] == "unmentioned":
            repaired[target] = "unmentioned"
        elif labels[target] == "unmentioned":
            repaired[target] = c0_labels[target]
    return repaired


def load_cache(cache_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            cache[(record["sample_id"], record["condition"])] = record
    return cache


def append_cache(cache_path: Path, record: dict[str, Any]) -> None:
    with cache_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def label_one_row(
    client: OpenAIChatClient,
    condition: str,
    row: pd.Series,
    exemplars: str,
    c0_labels: dict[str, str] | None,
    max_retries: int,
) -> tuple[dict[str, str], str]:
    correction = None
    raw = ""
    last_labels: dict[str, str] | None = None
    for attempt in range(1, max_retries + 1):
        messages = build_messages(condition, row, exemplars, c0_labels, correction)
        raw = client.complete(messages)
        try:
            labels = parse_labels(
                raw,
                detection_condition=condition if condition in DETECTION_CONDITIONS else None,
            )
            last_labels = labels
        except Exception as exc:  # noqa: BLE001 - retry with explicit correction.
            correction = f"Previous output was invalid JSON or invalid labels: {exc}"
            logging.warning(
                "Parse/label validation failed for %s %s attempt %s: %s",
                row["sample_id"],
                condition,
                attempt,
                exc,
            )
            continue
        if c0_labels and condition != "c0_faithful" and condition not in DETECTION_CONDITIONS:
            err = boundary_error(c0_labels, labels)
            if err:
                correction = (
                    "You moved the mention boundary, which is forbidden. "
                    f"Fix exactly these targets: {err}."
                )
                logging.warning(
                    "Boundary validation failed for %s %s attempt %s: %s",
                    row["sample_id"],
                    condition,
                    attempt,
                    err,
                )
                continue
        return labels, raw
    if c0_labels and condition not in DETECTION_CONDITIONS and last_labels:
        repaired = repair_boundary(c0_labels, last_labels)
        if boundary_error(c0_labels, repaired) is None:
            logging.warning(
                "Boundary repaired after retries for %s %s: raw=%s repaired=%s",
                row["sample_id"],
                condition,
                last_labels,
                repaired,
            )
            return repaired, raw
    raise RuntimeError(
        f"Could not get valid labels for {row['sample_id']} {condition}; last raw={raw!r}"
    )


def cohen_kappa(y_true: list[str], y_pred: list[str]) -> float:
    if len(y_true) != len(y_pred):
        raise ValueError("kappa inputs must have equal length")
    if not y_true:
        return float("nan")
    n = len(y_true)
    observed = sum(1 for a, b in zip(y_true, y_pred) if a == b) / n
    true_counts = Counter(y_true)
    pred_counts = Counter(y_pred)
    expected = sum((true_counts[label] / n) * (pred_counts[label] / n) for label in LABELS)
    if expected == 1:
        return 1.0 if observed == 1 else float("nan")
    return (observed - expected) / (1 - expected)


def validate_and_write_outputs(
    df: pd.DataFrame,
    cache: dict[tuple[str, str], dict[str, Any]],
    exemplar_ids: set[str],
    output_dir: Path,
) -> None:
    missing = []
    for sample_id in df["sample_id"]:
        for condition in CONDITIONS:
            if (sample_id, condition) not in cache:
                missing.append((sample_id, condition))
    if missing:
        raise RuntimeError(f"Missing cached labels for {len(missing)} sample-condition pairs")

    long_rows = []
    for sample_id in df["sample_id"]:
        c0 = cache[(sample_id, "c0_faithful")]["labels"]
        for condition in CONDITIONS:
            labels = cache[(sample_id, condition)]["labels"]
            if set(labels) != set(TARGETS):
                raise RuntimeError(f"Wrong label keys for {sample_id} {condition}: {labels}")
            if condition != "c0_faithful" and condition not in DETECTION_CONDITIONS:
                err = boundary_error(c0, labels)
                if err:
                    raise RuntimeError(
                        f"Mention-boundary invariance failed for {sample_id} {condition}: {err}"
                    )
            for target in TARGETS:
                label = labels[target]
                if label not in LABELS:
                    raise RuntimeError(
                        f"Out-of-vocabulary label for {sample_id} {target} {condition}: {label}"
                    )
                long_rows.append(
                    {
                        "sample_id": sample_id,
                        "target": target,
                        "condition": condition,
                        "model": MODEL_TAG,
                        "label": label,
                    }
                )
    expected_rows = len(df) * len(TARGETS) * len(CONDITIONS)
    if len(long_rows) != expected_rows:
        raise RuntimeError(f"Long output row count mismatch: {len(long_rows)} != {expected_rows}")

    long_df = pd.DataFrame(long_rows)
    if long_df.isna().any().any() or long_df.eq("").any().any():
        raise RuntimeError("Long output contains null or blank cells")
    long_path = output_dir / "stance_codex_labels_long.csv"
    long_df.to_csv(long_path, index=False)
    logging.info("Wrote long CSV: %s", long_path)

    wide = long_df.pivot(index="sample_id", columns=["target", "condition"], values="label")
    wide.columns = [f"{target}_{condition}" for target, condition in wide.columns]
    wide = wide.reset_index()
    expected_cols = 1 + len(TARGETS) * len(CONDITIONS)
    if len(wide) != len(df) or len(wide.columns) != expected_cols:
        raise RuntimeError("Wide output shape mismatch")
    wide_path = output_dir / "stance_codex_labels_wide.csv"
    wide.to_csv(wide_path, index=False)
    logging.info("Wrote wide CSV: %s", wide_path)

    validation_rows = heldout_validation(df, cache, exemplar_ids)
    validation_path = output_dir / "stance_codex_validation.csv"
    pd.DataFrame(validation_rows).to_csv(validation_path, index=False)
    logging.info("Wrote validation CSV: %s", validation_path)

    summary_rows = summarize_vs_c0(df, cache)
    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_dir / "stance_codex_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    logging.info("Wrote summary CSV: %s", summary_path)

    detection_summary_rows = summarize_detection_bias(df, cache)
    detection_summary_df = pd.DataFrame(detection_summary_rows)
    detection_summary_path = output_dir / "stance_codex_detection_summary.csv"
    detection_summary_df.to_csv(detection_summary_path, index=False)
    logging.info("Wrote detection-bias summary CSV: %s", detection_summary_path)

    run_checks(summary_df)
    run_detection_checks(detection_summary_df)


def heldout_validation(
    df: pd.DataFrame,
    cache: dict[tuple[str, str], dict[str, Any]],
    exemplar_ids: set[str],
) -> list[dict[str, Any]]:
    human_mask = (
        df[["russia_stance", "ukraine_stance"]]
        .map(lambda value: str(value).strip() != "")
        .any(axis=1)
    )
    heldout = df.loc[human_mask & ~df["sample_id"].isin(exemplar_ids)].copy()
    rows = []
    for target in TARGETS:
        col = f"{target}_stance"
        y_true = heldout[col].map(str.strip).tolist()
        y_pred = [
            cache[(sample_id, "c0_faithful")]["labels"][target]
            for sample_id in heldout["sample_id"]
        ]
        correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
        accuracy = correct / len(y_true) if y_true else float("nan")
        kappa = cohen_kappa(y_true, y_pred)
        if kappa < 0.6:
            logging.warning(
                "Held-out validation kappa below 0.6 for %s: %.4f", target, kappa
            )
        logging.info(
            "Held-out validation %s: n=%s accuracy=%.4f kappa=%.4f",
            target,
            len(y_true),
            accuracy,
            kappa,
        )
        rows.append(
            {
                "target": target,
                "heldout_n": len(y_true),
                "accuracy": accuracy,
                "cohen_kappa": kappa,
                "warn_kappa_lt_0_6": bool(kappa < 0.6),
            }
        )
    return rows


def summarize_vs_c0(
    df: pd.DataFrame, cache: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for condition in CONDITIONS:
        if condition == "c0_faithful" or condition in DETECTION_CONDITIONS:
            continue
        for target in TARGETS:
            changed = 0
            mentioned_n = 0
            shift_sum = 0
            extreme_changed = 0
            neutral_changed = 0
            for sample_id in df["sample_id"]:
                c0_label = cache[(sample_id, "c0_faithful")]["labels"][target]
                label = cache[(sample_id, condition)]["labels"][target]
                if label != c0_label:
                    changed += 1
                if c0_label != "unmentioned":
                    mentioned_n += 1
                    shift = ORDINAL[label] - ORDINAL[c0_label]
                    shift_sum += shift
                    if label == "neutral" and c0_label != "neutral":
                        neutral_changed += 1
                    if label != "neutral" and c0_label == "neutral":
                        extreme_changed += 1
            rows.append(
                {
                    "condition": condition,
                    "target": target,
                    "n": len(df),
                    "mentioned_n": mentioned_n,
                    "changed_count": changed,
                    "changed_pct": changed / len(df),
                    "net_directional_shift_sum": shift_sum,
                    "net_directional_shift_mean_mentioned": (
                        shift_sum / mentioned_n if mentioned_n else float("nan")
                    ),
                    "neutralizing_changes": neutral_changed,
                    "extremizing_changes": extreme_changed,
                }
            )
    return rows


def summarize_detection_bias(
    df: pd.DataFrame, cache: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for condition in DETECTION_CONDITIONS:
        for target in TARGETS:
            c0_mentioned = 0
            cond_mentioned = 0
            unmention_to_mention = 0
            mention_to_unmention = 0
            for sample_id in df["sample_id"]:
                c0_label = cache[(sample_id, "c0_faithful")]["labels"][target]
                label = cache[(sample_id, condition)]["labels"][target]
                c0_is_mentioned = c0_label != "unmentioned"
                cond_is_mentioned = label != "unmentioned"
                c0_mentioned += int(c0_is_mentioned)
                cond_mentioned += int(cond_is_mentioned)
                unmention_to_mention += int((not c0_is_mentioned) and cond_is_mentioned)
                mention_to_unmention += int(c0_is_mentioned and (not cond_is_mentioned))
            c0_rate = c0_mentioned / len(df)
            cond_rate = cond_mentioned / len(df)
            rows.append(
                {
                    "condition": condition,
                    "target": target,
                    "n": len(df),
                    "c0_mention_rate": c0_rate,
                    "cond_mention_rate": cond_rate,
                    "mention_rate_delta": cond_rate - c0_rate,
                    "n_unmention_to_mention": unmention_to_mention,
                    "n_mention_to_unmention": mention_to_unmention,
                }
            )
    return rows


def summary_value(summary: pd.DataFrame, condition: str, target: str, column: str) -> float:
    match = summary.loc[
        summary["condition"].eq(condition) & summary["target"].eq(target), column
    ]
    if match.empty:
        raise RuntimeError(f"Missing summary row for {condition} {target}")
    return float(match.iloc[0])


def run_checks(summary: pd.DataFrame) -> None:
    failures = []
    checks = [
        ("c1_modRU", "c2_strongRU", "russia", 1),
        ("c1_modRU", "c2_strongRU", "ukraine", -1),
        ("c3_modUA", "c4_strongUA", "ukraine", 1),
        ("c3_modUA", "c4_strongUA", "russia", -1),
    ]
    for moderate, strong, target, direction in checks:
        mod_changed = summary_value(summary, moderate, target, "changed_count")
        strong_changed = summary_value(summary, strong, target, "changed_count")
        mod_shift = summary_value(summary, moderate, target, "net_directional_shift_sum")
        strong_shift = summary_value(summary, strong, target, "net_directional_shift_sum")
        if strong_changed < mod_changed:
            failures.append(
                f"Gradient changed_count failed for {target}: {strong} < {moderate}"
            )
        if direction > 0 and strong_shift < mod_shift:
            failures.append(f"Gradient shift failed for {target}: {strong} < {moderate}")
        if direction < 0 and strong_shift > mod_shift:
            failures.append(f"Gradient shift failed for {target}: {strong} > {moderate}")

    placebo_rates = [
        summary_value(summary, "c5_placebo", target, "changed_pct") for target in TARGETS
    ]
    biased_rates = [
        summary_value(summary, condition, target, "changed_pct")
        for condition in ("c1_modRU", "c2_strongRU", "c3_modUA", "c4_strongUA")
        for target in TARGETS
    ]
    max_biased = max(biased_rates)
    max_placebo = max(placebo_rates)
    if max_placebo > 0.05 and max_placebo > 0.25 * max_biased:
        failures.append(
            "Placebo check failed: c5 change rate is not much lower than biased rates "
            f"(max placebo={max_placebo:.4f}, max biased={max_biased:.4f})"
        )

    if failures:
        for failure in failures:
            logging.error(failure)
        raise RuntimeError("Validation checks failed; see log for details")
    logging.info("Gradient and placebo checks passed")


def run_detection_checks(detection_summary: pd.DataFrame) -> None:
    for _, row in detection_summary.iterrows():
        condition = row["condition"]
        target = row["target"]
        delta = float(row["mention_rate_delta"])
        if condition == "c8_mention_lax" and delta < 0:
            logging.warning(
                "Detection sanity warning: c8 mention rate fell for %s (delta=%.4f)",
                target,
                delta,
            )
        if condition == "c9_mention_strict" and delta > 0:
            logging.warning(
                "Detection sanity warning: c9 mention rate rose for %s (delta=%.4f)",
                target,
                delta,
            )
    logging.info("Detection-bias sanity checks complete")


def copied_record(sample_id: str, condition: str, c0_labels: dict[str, str]) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "condition": condition,
        "labels": dict(c0_labels),
        "model": MODEL_TAG,
        "raw_response": "copied from c0 because both targets are unmentioned",
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
    }


def run_labeling(
    df: pd.DataFrame,
    client: OpenAIChatClient,
    exemplars: str,
    cache_path: Path,
    output_dir: Path,
    exemplar_ids: set[str],
    max_label_retries: int,
) -> None:
    cache = load_cache(cache_path)
    total_pairs = len(df) * len(CONDITIONS)
    processed_pairs = 0
    for condition in CONDITIONS:
        logging.info("Starting condition %s", condition)
        for index, row in df.iterrows():
            sample_id = row["sample_id"]
            key = (sample_id, condition)
            if key in cache:
                processed_pairs += 1
                continue
            c0_labels = None
            if condition != "c0_faithful":
                c0_key = (sample_id, "c0_faithful")
                if c0_key not in cache:
                    raise RuntimeError(f"Missing c0 label before {condition} for {sample_id}")
                if condition not in DETECTION_CONDITIONS:
                    c0_labels = cache[c0_key]["labels"]
                if c0_labels and all(c0_labels[target] == "unmentioned" for target in TARGETS):
                    record = copied_record(sample_id, condition, c0_labels)
                    append_cache(cache_path, record)
                    cache[key] = record
                    processed_pairs += 1
                    continue

            labels, raw = label_one_row(
                client=client,
                condition=condition,
                row=row,
                exemplars=exemplars,
                c0_labels=c0_labels,
                max_retries=max_label_retries,
            )
            record = {
                "sample_id": sample_id,
                "condition": condition,
                "labels": labels,
                "model": MODEL_TAG,
                "raw_response": raw,
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
            }
            append_cache(cache_path, record)
            cache[key] = record
            processed_pairs += 1
            if (index + 1) % 50 == 0:
                logging.info(
                    "Progress condition=%s row=%s/%s total_pairs=%s/%s",
                    condition,
                    index + 1,
                    len(df),
                    processed_pairs,
                    total_pairs,
                )
    validate_and_write_outputs(df, cache, exemplar_ids, output_dir)


def main() -> int:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="stance_train_1500.csv")
    parser.add_argument("--codebook", default="stance_codebook.md")
    parser.add_argument("--output-dir", default="stance_codex_outputs")
    parser.add_argument("--model", default=env_value("OPENAI_MODEL") or "gpt-5")
    parser.add_argument("--base-url", default=env_value("OPENAI_BASE_URL") or "https://api.openai.com/v1")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--api-max-retries", type=int, default=5)
    parser.add_argument("--label-max-retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--max-completion-tokens", type=int, default=512)
    parser.add_argument(
        "--reasoning-effort",
        default=env_value("OPENAI_REASONING_EFFORT") or "minimal",
        help="Optional reasoning effort hint for models that support it.",
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Optional smoke-test limit; labels the first N rows only.",
    )
    parser.add_argument("--exemplars-per-cell", type=int, default=10)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Run schema checks and exemplar split, then stop before API labeling.",
    )
    args = parser.parse_args()

    random.seed(SEED)
    output_dir = Path(args.output_dir)
    log_path = setup_logging(output_dir)
    logging.info("Run log: %s", log_path)
    logging.info("model tag: %s", MODEL_TAG)
    logging.info("Python version: %s", sys.version.split()[0])
    logging.info("pandas version: %s", pd.__version__)
    logging.info("OpenAI SDK version: %s", package_version("openai"))
    logging.info("Python-side random seed: %s", SEED)
    logging.info("Requested API seed: %s", SEED)
    logging.info("Model: %s", args.model)
    logging.info("Reasoning effort: %s", args.reasoning_effort or "not set")

    df = read_csv_checked(Path(args.input))
    label_df = df
    if args.limit_rows is not None:
        if args.limit_rows <= 0:
            raise ValueError("--limit-rows must be positive")
        label_df = df.head(args.limit_rows).copy()
        logging.warning("Smoke-test row limit active: first %s rows only", len(label_df))
    log_step0_assertions(df, Path(args.codebook))
    exemplar_ids, chosen_by_cell = choose_exemplars(df, args.exemplars_per_cell, output_dir)
    exemplars = exemplar_block(df, chosen_by_cell)
    (output_dir / "stance_codex_exemplar_prompt_block.txt").write_text(
        exemplars, encoding="utf-8"
    )
    if args.prepare_only:
        logging.info("Prepare-only complete; stopping before API labeling")
        return 0

    client = OpenAIChatClient(
        model=args.model,
        api_key=env_value(args.api_key_env),
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=args.api_max_retries,
        retry_sleep=args.retry_sleep,
        max_completion_tokens=args.max_completion_tokens,
        reasoning_effort=args.reasoning_effort or None,
    )
    cache_path = output_dir / "stance_codex_cache.jsonl"
    run_labeling(
        df=label_df,
        client=client,
        exemplars=exemplars,
        cache_path=cache_path,
        output_dir=output_dir,
        exemplar_ids=exemplar_ids,
        max_label_retries=args.label_max_retries,
    )
    logging.info("Labeling pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
