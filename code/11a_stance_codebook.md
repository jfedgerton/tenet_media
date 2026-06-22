# Stance Codebook — Target-Specific (Russia / Ukraine / Assad)
**Tenet Media / foreign-influence podcast project — PI: Jared Edgerton**
**Version 2.0 — supersedes v1.0. Per-target stance; narratives deferred.**

## What changed from v1
v1 coded a single axis (stance *toward Russia*) plus 8 pro-Kremlin narrative flags. v2 codes **three separate target-stance axes**, one per BERTopic topic, and **drops the narrative flags for now** (may return later). Each sentence is judged on stance **toward the target named for its topic**, not toward Russia generically.

---

## 0. What you are coding

Each row is one sentence drawn from a podcast transcript, assigned by the topic model to one of three topics. You will see a **`target`** column telling you which entity to judge:

| Topic | target | You judge stance toward… |
|---|---|---|
| 79 | `russia` | Russia / Putin / the Russian government |
| 78 | `ukraine` | Ukraine / Zelensky / the Ukrainian government |
| 353 | `assad` | Assad / the Syrian government |

You read the sentence with its previous/next sentence for context, but **code only the target sentence**, and only with respect to **its** target.

**Stance, not tone.** Code the sentence's *position toward the target*, not its emotional mood. A sentence can be angry/negative in tone yet supportive in stance, and vice versa. Example (target = russia): *"The warmongers in Washington provoked Russia for decades."* → negative tone, but **positive** stance toward Russia (defends/excuses it).

**Targets are independent.** Anti-Ukraine ≠ pro-Russia. If a sentence is hostile to Ukraine, code it `negative` on the *ukraine* axis — do **not** infer a Russia stance from it. Each sentence is judged only on its own target.

---

## 1. Stance label (assign exactly one)

For the sentence's target, assign:

- **`positive`** — sympathetic to, supportive of, justifying, or favorable toward the target. (e.g., target=russia: frames Russia as justified, strong, provoked-into-acting, winning; target=ukraine: praises Ukraine's cause/defense; target=assad: defends or legitimizes Assad.)
- **`negative`** — critical of, hostile toward, condemning, or blaming the target. (target=russia: calls Russia the aggressor, condemns Putin; target=ukraine: calls Ukraine corrupt/Nazi/illegitimate, opposes aid to it; target=assad: condemns Assad/atrocities.)
- **`neutral_none`** — factual/descriptive with no discernible stance toward the target, an incidental mention, or genuinely ambiguous/balanced.

**Expected directions (for reference — do NOT let these bias your coding):** the study hypothesizes treated shows become *more positive* toward Russia and Assad and *more negative* toward Ukraine after payment. Code what the sentence actually says, not what's expected.

### Tie-breakers
- **Framing counts as stance.** "Russia bombed the maternity hospital" → frames Russia as aggressor → `negative` (russia). "Ukraine is the most corrupt country in Europe" → `negative` (ukraine).
- **Mixed sentence:** code the dominant thrust toward the target; if truly balanced, `neutral_none`.
- **Sarcasm/irony:** code the intended meaning, not literal words; mark confidence `low`.
- **Off-target criticism:** a sentence attacking Biden/the media that doesn't take a position on the target → `neutral_none` for that target.
- **Aid/sanctions framing maps to Ukraine:** "Not one more dime to Ukraine" → `negative` (ukraine). "We must keep arming Ukraine" → `positive` (ukraine).

---

## 2. Other columns
- **`uncodable`** = 1 if not English, unintelligible/transcription garbage, or the sentence has nothing to do with the named target (then leave stance blank).
- **`confidence`** = `high` / `med` / `low`.
- **`notes`** = flag ambiguity, sarcasm, or judgment calls worth revisiting.

---

## 3. Worked examples

| target | sentence | stance | why |
|---|---|---|---|
| russia | "Putin had every right to defend Russia's borders from NATO." | positive | justifies Russian action |
| russia | "Russia is a brutal dictatorship that invaded a sovereign nation." | negative | condemns Russia |
| russia | "Russia's GDP is about the size of Italy's." | neutral_none | factual, no stance |
| ukraine | "Zelensky is a corrupt dictator laundering our tax dollars." | negative | attacks Ukraine's leader |
| ukraine | "Ukrainians are bravely defending their homeland." | positive | supports Ukraine |
| ukraine | "Congress approved more Ukraine aid this week." | neutral_none | factual report |
| assad | "Assad was actually protecting Syria's minorities from jihadists." | positive | defends Assad |
| assad | "The Assad regime gassed its own people." | negative | condemns Assad |

---

## 4. Reliability protocol (validation phase)
1. **Pilot:** two coders independently code the first ~60 sentences (20 per target), reconcile, refine codebook → v2.1.
2. **Full set:** code the rest independently.
3. **Reliability:** **Krippendorff's α** per target axis (nominal, 3 categories). Target α ≥ 0.67, aim ≥ 0.80. Human–human α is the ceiling the automated classifier must approach.
4. **Adjudicate** disagreements → gold set.
5. **Benchmark** the NLI classifier (and, if used, LLaMA-codebook) against the gold set: accuracy, macro-F1, per-class Cohen's κ — reported **per target**. Lead with macro-F1 (neutral dominates).

---

## 5. LLM prompt template (drop-in, per-target)
```
You are an expert political-communication coder. Judge the TARGET sentence's stance
toward {TARGET} only. Output ONLY valid JSON.

stance: one of "positive","negative","neutral_none".
  positive = sympathetic/supportive/justifying/favorable toward {TARGET}.
  negative = critical/hostile/condemning/blaming toward {TARGET}.
  neutral_none = factual, incidental, or no stance toward {TARGET}.
Tone is irrelevant; code the POSITION. Anti-Ukraine is NOT pro-Russia — judge only {TARGET}.

CONTEXT (reference only): {prev} || {sentence} || {next}
TARGET ENTITY: {TARGET}   (russia = Russia/Putin; ukraine = Ukraine/Zelensky; assad = Assad/Syrian govt)
SENTENCE: {sentence}

Return: {"stance":"", "uncodable":0, "confidence":"high|med|low"}
```
Temperature 0, fixed seed, one call per (sentence, target). Llama-3.1-70B-Instruct recommended over 8B for sarcasm/implicit framing.
