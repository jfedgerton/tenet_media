> Moved Nov 2026 from `code/` to `docs/`. The feed files it names now live in `inputs/` (`inputs/new_feeds_19.csv`, `inputs/new_feeds_15.csv`, `inputs/podcast_feeds_309.csv`).

# New control feeds (from the 309-show block set) — pull notes

**Date:** 2026-07-01
**Source:** `show_meta/treated_terminal_blocks_weightedDecay.csv` (309 shows, the weighted-decay terminal-block universe).
**Task:** identify shows in the 309-set not already in `code/podcast_feeds.csv` (290 shows), find their RSS feeds, and add them for the transcription pull.

**Result:** 19 shows were missing from `podcast_feeds.csv` (all `treated=0` controls). RSS feeds were located and verified (by fetching the live feed XML and matching title/host/network) for **15**. The remaining **4** are **not being pulled** for the reasons below. Feeds written to `code/new_feeds_19.csv` (with `status_note`) and merged into `code/podcast_feeds_309.csv`; the 15-row pull list is `code/new_feeds_15.csv`.

## The 4 shows NOT pulled, and why

**1. Morning Glory — `podcast_id_dd = 225168` — feed retired**
This is the EWTN Catholic radio program *Morning Glory* (Gloria Purvis / Deacon Harold Burke-Sivers era), not the Relevant Radio show. That program was **cancelled in December 2020**, and its legacy EWTN feed code no longer serves an RSS document (the URL now returns EWTN's HTML site shell). A separate 2024 EWTN *Morning Glory* revival exists, but it is delisted from Apple's lookup API and no directory exposed a currently-serving XML feed. No reliable feed → excluded rather than guess.

**2. The Best of Making Sense with Sam Harris — `podcast_id_dd = 4758191` — discontinued**
The free "best of" companion feed to Sam Harris's *Making Sense* was **discontinued**; its Libsyn feed returns HTTP 404 (last episode Nov 2023, dead since ~Apr 2026) and the Apple entry is delisted. This is distinct from the full subscriber *Making Sense* feed, which is a different show and paywalled. No live free feed → excluded.

**3. The Chris Salcedo Show — `podcast_id_dd = 492671` — feed dead**
The correct show (Cumulus Media / WBAP NewsTalk 820, host Chris Salcedo) was Omny-hosted; that feed and its audio now return **HTTP 404** and the show is delisted from Apple — the program was removed. Do **not** substitute "The Salcedo Storm Podcast" (a *different* active Chris Salcedo show on Spreaker); that is not this ID. No live feed for 492671 → excluded.

**4. The Laura Ingraham Podcast — `podcast_id_dd = 782972` — moved behind paywall**
Correct show identity confirmed (Laura Ingraham, Omny-hosted). The free public feed **ended ~March 2021** and the content moved behind the **Quake Media** paywall (quakemedia.com/laura); the public RSS returns HTTP 404 and the Apple entry is delisted. No free public feed → excluded.

## Additional flags on shows that WERE pulled (verify before transcribing)

- **The Music Show — `64440`** — its `podcast_id_dd` resolves to **ABC Radio National (Australia) *The Music Show*** with Andrew Ford, a **music program, not political talk**. The ID maps here unambiguously, but it looks like a stray entry in the block set. Feed included (`https://www.abc.net.au/feeds/2883396/podcast.xml`) but **recommend excluding** unless intentional.
- **Candace Owens overlap** — `1626613` (her independent 2024+ show "Candace") and `811657` (the older PragerU-era "The Candace Owens Show") are **both** in the set and both pulled. They are different shows but overlap in host; you may want only one. Note `811657` serves audio over insecure **HTTP**, which can complicate downloads.
- **The Cats Roundtable — `993013`** — a Catsimatidis feed **distinct from** the existing **CATS Roundtable `49733`** already in `podcast_feeds.csv`. Both are legitimate but content will overlap.

## Feed hosts of the 15 pulled (for reference)
captivate.fm (American Thought Leaders, The News Agents), megaphone.fm (Candace, The Cats Roundtable), acast.com (Free Speech Nation), simplecast.com (Heterodox Out Loud), podbean.com (Paul VanderKlay, WWUTT), aristoteliansociety.org.uk (Proceedings of the Aristotelian Society), podcastmirror.com (Stand Up For The Truth), soundcloud.com (The Candace Owens Show — HTTP audio), abc.net.au (The Music Show), spreaker.com (The Right Side w/ Doug Billings, The Todd Herman Show), amperwave.net/audacy (The Tara Show).

## PROBLEM: RSS feed truncation vs. the analysis window (added 2026-07-01)

**The issue.** RSS feeds only expose a *recent* window of episodes; the number exposed is set by the podcast's hosting platform (feed-length cap), not by us. For high-volume shows on capping hosts, the entire exposed feed can post-date our analysis window. Our panel timeline (confirmed from `data/sc_results/baseline_panel.csv` / `did_panel_month.csv`) runs **2018-01 → 2024-08 monthly** (pre-treatment through the last full month before the 2024-09-04 indictment; 226 units). Episodes outside that window are not usable.

**This is not new to these controls.** The original 290-show corpus shows the same caps: in `file_key_orig_290.csv`, 33 shows sit at exactly 100 episodes, 11 at exactly 1000, 9 at exactly 500 (~54 of 289). It is host-specific, not universal (corpus median is 408 eps/show, max ~11K). Full-history hosts (Megaphone, the society's own server) serve the whole back-catalog; capped hosts (Audacy, Podbean, Blubrry, some Captivate) serve only the recent tail.

**Effect on the new controls — 4 dropped for ZERO in-window coverage** (their feed's earliest episode post-dates 2024-08):
- American Thought Leaders `887867` (captivate) — feed starts 2025-02-13.
- Paul VanderKlay `686623` (podbean) — last 100 eps all 2026.
- Stand Up For The Truth `5362` (blubrry/podcastmirror) — feed starts 2025-03.
- The Tara Show `698046` (audacy) — last 500 eps all from 2026-05 onward.

**Also dropped** (see flags above): The Candace Owens Show `811657` (only 5 eps in feed) and The Music Show `64440` (ABC Australia music program, wrong genre).

**Kept: 9 shows, truncated to 2018-01-01..2024-08-31** (JSONs updated in `json_data/` so only in-window episodes are keyed for transcription). In-window episode counts: The Cats Roundtable 1,542; The News Agents 584; WWUTT 520; Proceedings of the Aristotelian Society 74; Heterodox Out Loud 65; Candace Owens 61; Free Speech Nation 47; The Todd Herman Show 48; The Right Side w/ Doug Billings 21. **Total = 2,962 in-window episodes.**

**Caveat for analysis:** Candace Owens (in-window from 2024-06), The Todd Herman Show (from 2024-08), and The Right Side w/ Doug Billings (from 2024-07) have in-window episodes only in the *post-treatment* period — they lack pre-treatment coverage, so they are thin as synthetic-control donors even though they clear the window filter.

Net: of the original 19 missing shows, **9 usable controls added; 10 excluded** (4 no live feed, 4 zero in-window, 2 wrong/insufficient show).
