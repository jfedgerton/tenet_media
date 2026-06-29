###############################################################################
# 17_grid_summary.R  --  robustness summary of the H1/H2 master grid (16).
#   Reads master_grid_h1h2.csv (~993k rows, ~6,600 specs x 15 outcomes x specs)
#   and produces:
#     grid_summary_h1h2.csv   per hyp x set x metric x spec: baseline (main-article)
#                             estimate + p, grid median, 5-95% range, % significant,
#                             % same-sign, n specs.
#     fig_speccurve.pdf       specification curve for the 4 headline outcomes
#                             (H1/H2 x Russia/Combined positivity); baseline marked.
#     fig_audience_h1.pdf     H1 estimate WITH vs WITHOUT the audience control
#                             (answers the "audience drops 26% of the sample" concern).
#   Console: a no-control vs +control comparison table.
#   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(ggplot2) })
set.seed(123)
SC <- "/storage/group/LiberalArts/default/jfe4_collab/podcast/data/sc_results"
g  <- fread(file.path(SC, "master_grid_h1h2.csv"))

ACCENT <- "#D95F02"
SIGCOL <- c("p < 0.05" = "#1B9E77", "n.s." = "grey60")          # Dark2 green vs grey
theme_pub <- theme_bw(base_size = 12) +
  theme(panel.grid.minor = element_blank(), axis.text.x = element_text(angle = 0, hjust = 0.5),
        strip.background = element_rect(fill = "grey92", colour = NA), legend.position = "bottom")

## main-article baseline cell: identity ops, shift 0, min_ment 5, conditional, Oct-2023
g[, baseline := (rus_op == 0 & ukr_op == 0 & shift == 0 & min_ment == 5 &
                 coding == "conditional" & treat_date == "2023-10-01")]

SPECMAP <- c(simple = "H1 no controls", ctrl = "H1 + controls",
             simpleM = "H1 matched", ctrlM = "H1 matched + ctrl",
             twfe = "H2 no controls", twfe_ctrl = "H2 + controls",
             twfeM = "H2 matched", twfeM_ctrl = "H2 matched + ctrl",
             scm = "H2 synthetic control", scm_ctrl = "H2 SCM + ctrl")

## ---- robustness summary table (positivity outcomes) ------------------------
S <- g[set %in% c("Russia", "Combined") & metric == "pos" & !is.na(est),
       .(n        = .N,
         base_est = est[baseline][1],
         base_p   = p[baseline][1],
         grid_med = as.numeric(median(est)),
         grid_lo  = as.numeric(quantile(est, 0.05)),
         grid_hi  = as.numeric(quantile(est, 0.95)),
         pct_sig  = round(100 * mean(p < 0.05, na.rm = TRUE)),
         pct_same = round(100 * mean(sign(est) == sign(median(est))))),
       by = .(hyp, set, spec)]
S[, spec_label := SPECMAP[spec]]
S <- S[order(hyp, set, spec)]
fwrite(S, file.path(SC, "grid_summary_h1h2.csv"))

## ---- console: how do the NO-CONTROL models do? ----------------------------
cat("\n=== NO-CONTROL vs +CONTROL (positivity, baseline cell + grid) ===\n")
cmp <- S[spec %in% c("simple", "ctrl", "twfe", "twfe_ctrl"),
         .(hyp, set, spec_label, n, base_est = round(base_est, 4),
           base_p = round(base_p, 3), grid_med = round(grid_med, 4), pct_sig)]
print(cmp)

## ---- specification curve: 4 headline outcomes (controlled spec) ------------
SC4 <- g[set %in% c("Russia", "Combined") & metric == "pos" & !is.na(est) &
         ((hyp == "H1" & spec == "ctrl") | (hyp == "H2" & spec == "twfe_ctrl"))]
SC4[, panel := factor(paste0(hyp, ": ", set, " positivity"))]
SC4[, sigf  := ifelse(p < 0.05, "p < 0.05", "n.s.")]
SC4 <- SC4[order(panel, est)][, rank := seq_len(.N), by = panel]
bpts <- SC4[baseline == TRUE]
pSC <- ggplot(SC4, aes(rank, est, colour = sigf)) +
  geom_hline(yintercept = 0, colour = "grey50", linewidth = 0.3) +
  geom_point(size = 0.4) +
  geom_point(data = bpts, aes(rank, est), colour = "black", shape = 18, size = 3) +
  facet_wrap(~ panel, scales = "free", nrow = 2) +
  scale_colour_manual(values = SIGCOL) +
  labs(x = "Specification (sorted low to high)", y = "Treatment estimate", colour = NULL,
       title = "Specification curve: H1/H2 across the full robustness grid",
       subtitle = "Each point is one grid specification. Black diamond = main-article baseline.") +
  theme_pub + guides(colour = guide_legend(override.aes = list(size = 3)))
ggsave(file.path(SC, "fig_speccurve.pdf"), pSC, width = 9, height = 7)

## ---- H1 audience-control comparison ----------------------------------------
## simple = NO audience control (full pre-payment sample); ctrl = + audience control
## (drops the ~26% of show-months that lack an audience estimate).
AUD <- g[hyp == "H1" & set %in% c("Russia", "Combined") & metric == "pos" &
         spec %in% c("simple", "ctrl") & !is.na(est)]
AUD[, control := ifelse(spec == "simple", "No audience control (full sample)", "With audience control")]
AUD[, panel := factor(paste0(set, " positivity"))]
fwrite(AUD[, .(set, spec, control, rus_op, ukr_op, shift, min_ment, coding, treat_date, est, se, p)],
       file.path(SC, "grid_audience_h1_data.csv"))
pA <- ggplot(AUD, aes(est, fill = control)) +
  geom_vline(xintercept = 0, colour = "grey50") +
  geom_density(alpha = 0.5, colour = NA) +
  facet_wrap(~ panel, scales = "free", nrow = 1) +
  scale_fill_manual(values = c("No audience control (full sample)" = "grey55",
                               "With audience control" = ACCENT)) +
  labs(x = "H1 estimate (pre-payment Tenet gap in positivity)", y = "Density across grid", fill = NULL,
       title = "H1 selection effect: robust with or without the audience control",
       subtitle = "Distribution of the H1 estimate across the grid. The audience control drops ~26% of show-months.") +
  theme_pub
ggsave(file.path(SC, "fig_audience_h1.pdf"), pA, width = 9, height = 4.5)

cat("\nWROTE grid_summary_h1h2.csv / fig_speccurve.pdf / fig_audience_h1.pdf / grid_audience_h1_data.csv\n")
cat("DONE_17\n")
