###############################################################################
# 17_grid_summary.R  --  robustness summary of the H1/H2 master grid (16).
#   Reads master_grid_h1h2.csv (~993k rows) and produces a summary table +
#   FOUR figures:
#     (1) fig_prob_sweep.pdf   how shifting probability mass BETWEEN sentiment
#                              labels (axis A) moves the estimate.
#     (2) fig_measurement.pdf  how MEASUREMENT decisions (min-mention threshold,
#                              missing=0 coding, treatment date; axis B) move it.
#     (3) fig_coef_box.pdf     boxplot of the coefficient distribution by
#                              hypothesis (x) across ALL sweeps; points coloured
#                              BLUE if significant at one-sided p<0.05, RED if not.
#     (4) fig_audience_h1.pdf  H1 estimate WITH vs WITHOUT the audience control.
#   Also: grid_summary_h1h2.csv and a console no-control vs +control comparison.
#   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(ggplot2) })
set.seed(123)
SC <- "/storage/group/LiberalArts/default/jfe4_collab/podcast/data/sc_results"
g  <- fread(file.path(SC, "master_grid_h1h2.csv"))

ACCENT <- "#D95F02"
BLUE   <- "#377EB8"; RED <- "#E41A1C"
theme_pub <- theme_bw(base_size = 12) +
  theme(panel.grid.minor = element_blank(), axis.text.x = element_text(angle = 0, hjust = 0.5),
        strip.background = element_rect(fill = "grey92", colour = NA), legend.position = "bottom")

## main-article baseline cell: identity ops, shift 0, min_ment 5, conditional, Oct-2023
g[, baseline := (rus_op == 0 & ukr_op == 0 & shift == 0 & min_ment == 5 &
                 coding == "conditional" & treat_date == "2023-10-01")]
## headline spec per hypothesis: H1 = + controls; H2 = TWFE + controls
g[, headline := (hyp == "H1" & spec == "ctrl") | (hyp == "H2" & spec == "twfe_ctrl")]

SPECMAP <- c(simple = "H1 no controls", ctrl = "H1 + controls", simpleM = "H1 matched", ctrlM = "H1 matched + ctrl",
             twfe = "H2 no controls", twfe_ctrl = "H2 + controls", twfeM = "H2 matched", twfeM_ctrl = "H2 matched + ctrl",
             scm = "H2 synthetic control", scm_ctrl = "H2 SCM + ctrl")

## ---- robustness summary table (positivity) + no-control console comparison --
S <- g[set %in% c("Russia", "Combined") & metric == "pos" & !is.na(est),
       .(n = .N, base_est = est[baseline][1], base_p = p[baseline][1],
         grid_med = as.numeric(median(est)), grid_lo = as.numeric(quantile(est, 0.05)),
         grid_hi = as.numeric(quantile(est, 0.95)),
         pct_sig = round(100 * mean(p < 0.05, na.rm = TRUE)),
         pct_sig1 = round(100 * mean(est > 0 & p < 0.10, na.rm = TRUE))),   # one-sided p<0.05
       by = .(hyp, set, spec)]
S[, spec_label := SPECMAP[spec]]; S <- S[order(hyp, set, spec)]
fwrite(S, file.path(SC, "grid_summary_h1h2.csv"))
cat("\n=== NO-CONTROL vs +CONTROL (positivity; baseline + grid) ===\n")
print(S[spec %in% c("simple", "ctrl", "twfe", "twfe_ctrl"),
        .(hyp, set, spec_label, n, base_est = round(base_est, 4), base_p = round(base_p, 3),
          grid_med = round(grid_med, 4), pct_sig, pct_sig1)])

## ---- (1) PROBABILITY BETWEEN LABELS -> outcome (axis A) ---------------------
A1 <- g[axis == "probshift" & headline == TRUE & set %in% c("Russia", "Combined") &
        metric == "pos" & treat_date == "2023-10-01" & !is.na(est)]
A1[, panel := paste0(hyp, ": ", set, " positivity")]
A1s <- A1[, .(med = median(est), lo = quantile(est, 0.05), hi = quantile(est, 0.95)), by = .(panel, shift)]
p1 <- ggplot(A1s, aes(shift, med)) +
  geom_hline(yintercept = 0, colour = "grey60") +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.2, fill = ACCENT) +
  geom_line(colour = ACCENT, linewidth = 0.7) + geom_point(colour = ACCENT, size = 1.4) +
  facet_wrap(~ panel, scales = "free_y", nrow = 2) +
  labs(x = "Probability mass shifted between sentiment labels (per sentence)",
       y = "Treatment estimate", title = "Sensitivity to label-probability perturbation (axis A)",
       subtitle = "Line = median estimate across all 169 relabeling operations at each shift; band = 5-95%.") +
  theme_pub
ggsave(file.path(SC, "fig_prob_sweep.pdf"), p1, width = 9, height = 7)

## ---- (2) MEASUREMENT DECISIONS -> outcome (axis B) -------------------------
B1 <- g[axis == "minment" & headline == TRUE & set %in% c("Russia", "Combined") & metric == "pos" & !is.na(est)]
B1[, panel := paste0(hyp, ": ", set, " positivity")]
B1[, coding_lab := factor(coding, levels = c("conditional", "zero"),
                          labels = c("Conditional (mention-months)", "Missing = 0"))]
B1[, treat := factor(treat_date)]
B1[, mmf := factor(min_ment, levels = c(0, 1, 3, 5, 10, 20))]   # even x-spacing (thresholds are uneven)
p2 <- ggplot(B1, aes(mmf, est, colour = coding_lab, linetype = treat, group = interaction(coding, treat))) +
  geom_hline(yintercept = 0, colour = "grey60") +
  geom_line(linewidth = 0.6) + geom_point(size = 1.6) +
  facet_wrap(~ panel, scales = "free_y", nrow = 2) +
  scale_colour_manual(values = c("Conditional (mention-months)" = "#1B9E77", "Missing = 0" = "#7570B3")) +
  labs(x = "Minimum mentions per show-month (inclusion threshold)", y = "Treatment estimate",
       colour = "Coding", linetype = "Treatment date",
       title = "Sensitivity to measurement decisions (axis B)") + theme_pub
ggsave(file.path(SC, "fig_measurement.pdf"), p2, width = 9, height = 7)

## ---- (3) COEFFICIENT BOXPLOT BY HYPOTHESIS, points by one-sided sig --------
## All regression specs (exclude SCM, which is a gap not a coefficient), positivity
## outcomes, across every sweep cell. One-sided p<0.05 (positive direction) = p<0.10 & est>0.
BX <- g[set %in% c("Russia", "Combined") & metric == "pos" & !spec %in% c("scm", "scm_ctrl") &
        !is.na(est) & !is.na(p)]
BX[, sig1 := ifelse(est > 0 & p < 0.10, "Significant (one-sided p<0.05)", "Not significant")]
pts <- BX[sample(.N, min(.N, 5000))]                                  # sample for the overlay
p3 <- ggplot(BX, aes(hyp, est)) +
  geom_hline(yintercept = 0, colour = "grey60") +
  geom_jitter(data = pts, aes(colour = sig1), width = 0.28, height = 0, size = 0.5, alpha = 0.45) +
  geom_boxplot(outlier.shape = NA, fill = NA, colour = "black", width = 0.45, linewidth = 0.6) +
  scale_colour_manual(values = c("Significant (one-sided p<0.05)" = BLUE, "Not significant" = RED)) +
  labs(x = "Hypothesis", y = "Treatment estimate", colour = NULL,
       title = "Coefficient distribution by hypothesis, across all sweeps",
       subtitle = "Box = full grid distribution (all specs/cells). Points sampled; blue = one-sided p<0.05, red = not.") +
  theme_pub + guides(colour = guide_legend(override.aes = list(size = 3, alpha = 1)))
ggsave(file.path(SC, "fig_coef_box.pdf"), p3, width = 8, height = 6)

## ---- (4) H1 audience-control comparison ------------------------------------
AUD <- g[hyp == "H1" & set %in% c("Russia", "Combined") & metric == "pos" &
         spec %in% c("simple", "ctrl") & !is.na(est)]
AUD[, control := ifelse(spec == "simple", "No audience control (full sample)", "With audience control")]
AUD[, panel := paste0(set, " positivity")]
p4 <- ggplot(AUD, aes(est, fill = control)) +
  geom_vline(xintercept = 0, colour = "grey50") + geom_density(alpha = 0.5, colour = NA) +
  facet_wrap(~ panel, scales = "free", nrow = 1) +
  scale_fill_manual(values = c("No audience control (full sample)" = "grey55", "With audience control" = ACCENT)) +
  labs(x = "H1 estimate (pre-payment Tenet gap in positivity)", y = "Density across grid", fill = NULL,
       title = "H1 selection effect: robust with or without the audience control",
       subtitle = "Audience control drops ~26% of show-months (37 of 189 shows have no audience data).") +
  theme_pub
ggsave(file.path(SC, "fig_audience_h1.pdf"), p4, width = 9, height = 4.5)

cat("\nWROTE grid_summary_h1h2.csv + fig_prob_sweep / fig_measurement / fig_coef_box / fig_audience_h1 .pdf\n")
cat("DONE_17\n")
