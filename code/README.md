# Pipeline code

The full pipeline overview, article-ordered script list, and methods are in the
repository root **[`../README.md`](../README.md)**.

Quick orientation:
- `01`–`12` build the data: corpus → topics → **human + machine stance labeling** on the
  Russia/Ukraine topics → show × month panels. (`07`–`10` and the stance labelers run on
  ROAR and are not mirrored here.)
- `13_main_h1h3.R` — main H1/H2/H3. `15_main_h4.R` — main H4 (panel from `14`).
- `16` grid search (H1/H2); `17`–`25` robustness; `26+` tables/figures (to build).

Stance, not sentiment: stance toward Russia/Ukraine is labeled by a classifier distilled
from a human-validated coding set; the earlier off-the-shelf sentiment pass is deprecated.
PI: Jared Edgerton (PSU).
