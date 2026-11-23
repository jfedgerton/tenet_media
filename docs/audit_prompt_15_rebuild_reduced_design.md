# GPT audit request: 13w_rebuild_reduced_design.py

Paste this file, then the full contents of `code/13w_rebuild_reduced_design.py` and `code/13w_test_synthetic.py`.

## Context
Human stance-coding project (Russia/Ukraine stance in podcast sentences). Three student coders (Emily = A, Josh = B, Pam = C) were given an Oct 9 assignment in which every one of 10,000 main sentences and 2,000 placebo sentences was assigned to exactly 2 of the 3 students (pair rotation A+B / B+C / A+C, balanced within stratum), split into 12 weekly Excel files per student. Only Week 1 was coded. The PI (Jared) has already coded nothing but has two blind batches built on Nov 18: batch A = every Week-1 sentence coded by exactly one student (1,762); batch B = 1,000 union sentences nobody has coded.

## New design the script must implement
1. Sample of 8,000 sentences: all 4,000 union; all 1,000 hard negatives; 2,000 non-union random (1,000 before and 1,000 on/after 2023-10-01), keeping every non-union row already coded or left blank in Week 1 and filling the rest at random; 1,000 placebo (250 per target, at random).
2. Every selected sentence gets exactly two coders: Jared plus one student. Exception: the 94 Week-1 sentences already coded by two students stay student-student, and Jared does not code them.
3. Week-1 codes are never modified. Week-1 rows a student left blank go back to that same student, at the top of their next file.
4. Each new sentence goes to ONE of its two originally assigned students, load-balanced so students get equal work within stratum and within placebo target.
5. Jared gets batches C (remaining main, split C1/C2) and D (placebo). Students get weeks due 2026-12-04, 12-11, 12-18 (main) and 2027-01-08 (placebo). Seed 123 throughout. Nothing in coder_materials is written.

## Please check
- Logic: does the code implement 1–5 exactly? Any sentence that could end up with 0, 1 or 3 coders, or a student coding the same sentence twice?
- Sampling: is the non-union and placebo draw random within the intended frames, reproducible with seed 123, and unaffected by Python set ordering? (Note `set` -> `rng.choice` on sorted lists.)
- Load balancing: can the greedy assignment bias which students get which strata or time periods?
- Edge cases: Week-1 blank rows that another student did code; rows in both Week-1 files; placebo rows; original files moved to `_superseded/old_schedule_nov30` on a rerun.
- Assertions: anything important that is NOT asserted and could fail silently?
- Output files: same columns/order as the originals, all coding cells blank, dropdowns on the right columns.
- Reproducibility: would a rerun on the same inputs produce identical outputs?
Report concrete bugs with line references first, then lower-priority suggestions separately.
