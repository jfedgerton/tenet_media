###############################################################################
# 18_power_analysis.R  --  minimum-detectable-effect / power for the post-payment
# nulls (H2 stance, H3 agenda, H4 divergence). Turns "we found nothing" into
# "we can rule out anything larger than X".
#
# For each main outcome we fit the SAME main DiD as 13/29
#   y ~ treated*post + log_words + log_aud_m | unit + month   (two-way clustered)
# and report, from the estimated SE:
#   - estimate + 95% CI
#   - MDE at 80% power (two-sided 0.05 and one-sided 0.05)
#   - the MDE in control-SD units, and relative to the H1 selection gap
# Outputs: power_mde_h2h4.csv, fig_mde.pdf (estimate+CI vs MDE band),
#          fig_power_curve.pdf (power vs true effect, 80% + MDE marked).
# PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(ggplot2) })
set.seed(123); setFixest_notes(FALSE)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01")
MM <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny
z975 <- qnorm(0.975); z95 <- qnorm(0.95); z80 <- qnorm(0.80)

## ---- panels (identical construction to 13/29) ------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
P[, mfac := factor(month)]; P[, tenet := as.integer(unit %in% TRU)]
P[, post := as.integer(month >= TREAT)]; P[, tp := tenet * post]
P[, c_pos := r_pos - u_pos]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", fifelse(show %in% BEN, "the_benny_show", show))]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit", "month"), all.x = TRUE); P[, log_words := log(n_words)]
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
P <- merge(P, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); P[, log_aud_m := log(aud_mid)]
P[, prop_comb := (n_ment_r + n_ment_u) / n_words]

H <- fread(file.path(SC, "h4_divergence_panel.csv")); H[, month := as.Date(month)]
H <- H[topicset == "all" & reference == "contemp" & rare == "rare"]
H[, unit := fifelse(unit %in% TIM, "tim_pool", fifelse(unit %in% BEN, "the_benny_show", unit))]
H[, mfac := factor(month)]; H[, tenet := as.integer(unit %in% TRU)]
H[, post := as.integer(month >= TREAT)]; H[, tp := tenet * post]
H <- merge(H, Vunit, by = c("unit", "month"), all.x = TRUE); H[, log_words := log(n_words)]
H <- merge(H, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); H[, log_aud_m := log(aud_mid)]

## ---- outcome list: panel, column, label, mention-filter, hypothesis --------
OUT <- list(
  list(P, "r_pos",     "H2: Russia positive",        quote(n_ment_r >= MM),                "H2"),
  list(P, "c_pos",     "H2: Combined positive",      quote(n_ment_r >= MM & n_ment_u >= MM), "H2"),
  list(P, "prop_comb", "H3: Combined topic prop.",   quote(rep(TRUE, .N)),                  "H3"),
  list(H, "jsd",       "H4: JS divergence",          quote(rep(TRUE, .N)),                  "H4"))

mde_row <- function(o){
  dat <- o[[1]]; y <- o[[2]]; lab <- o[[3]]; flt <- o[[4]]; hyp <- o[[5]]
  d <- dat[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  d <- d[eval(flt, d)]
  m  <- feols(as.formula(paste0(y, " ~ tp + log_words + log_aud_m | unit + month")), d, cluster = ~ unit + month)
  ct <- coeftable(m)["tp", ]; est <- as.numeric(ct["Estimate"]); se <- as.numeric(ct["Std. Error"])
  ## H1 selection gap (same outcome, pre-period level) for a yardstick
  dpre <- d[post == 0]
  msel <- tryCatch(feols(as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac")), dpre, cluster = ~ mfac + unit),
                   error = function(e) NULL)
  sel <- if (is.null(msel)) NA_real_ else as.numeric(coeftable(msel)["tenet", "Estimate"])
  csd <- sd(d[post == 1 & tenet == 0][[y]], na.rm = TRUE)
  data.table(hyp = hyp, outcome = lab, n = nrow(d), est = est, se = se,
             ci_lo = est - z975*se, ci_hi = est + z975*se,
             mde80_2 = (z975 + z80)*se, mde80_1 = (z95 + z80)*se,
             ctrl_sd = csd, mde_sd = (z975 + z80)*se / csd, sel_gap = sel)
}
R <- rbindlist(lapply(OUT, mde_row))
R[, mde_vs_sel := mde80_2 / abs(sel_gap)]
fwrite(R, file.path(SC, "power_mde_h2h4.csv"))
cat("\n=== MDE / POWER (post-payment nulls) ===\n")
print(R[, .(outcome, est = round(est, 4), ci_lo = round(ci_lo, 4), ci_hi = round(ci_hi, 4),
            mde80_2 = round(mde80_2, 4), mde_sd = round(mde_sd, 2), sel_gap = round(sel_gap, 4),
            mde_vs_sel = round(mde_vs_sel, 2))])

## ---- (A) estimate + 95% CI vs the MDE band ---------------------------------
R[, outcome := factor(outcome, levels = R$outcome)]
pA <- ggplot(R, aes(est, outcome)) +
  geom_vline(xintercept = 0, colour = "grey55") +
  geom_rect(aes(xmin = -mde80_2, xmax = mde80_2, ymin = as.numeric(outcome) - 0.4, ymax = as.numeric(outcome) + 0.4),
            fill = "grey85", alpha = 0.5) +
  geom_errorbarh(aes(xmin = ci_lo, xmax = ci_hi), height = 0.18, colour = "#0072B2") +
  geom_point(size = 2.4, colour = "#0072B2") +
  geom_point(aes(x = sel_gap), shape = 18, size = 3, colour = "#D95F02") +
  labs(x = "Treatment effect (estimate, 95% CI)", y = NULL,
       title = "Post-payment effects vs. the minimum detectable effect",
       subtitle = "Grey band = +/- MDE at 80% power. Blue = DiD estimate + 95% CI. Orange diamond = H1 selection gap.") +
  theme_bw(base_size = 12) + theme(panel.grid.minor = element_blank(), axis.text.x = element_text(angle = 0, hjust = 0.5))
ggsave(file.path(SC, "fig_mde.pdf"), pA, width = 9, height = 5)

## ---- (B) power curves ------------------------------------------------------
PC <- rbindlist(lapply(seq_len(nrow(R)), function(i){
  se <- R$se[i]; gmax <- max(R$mde80_2[i] * 1.8, abs(R$sel_gap[i]), na.rm = TRUE)
  d  <- seq(0, gmax, length.out = 200)
  data.table(outcome = R$outcome[i], delta = d,
             power = pnorm(d/se - z975) + pnorm(-d/se - z975)) }))
mde_pts <- R[, .(outcome, mde80_2)]
pB <- ggplot(PC, aes(delta, power)) +
  geom_hline(yintercept = 0.8, linetype = 2, colour = "grey55") +
  geom_line(colour = "#0072B2", linewidth = 0.8) +
  geom_vline(data = mde_pts, aes(xintercept = mde80_2), linetype = 3, colour = "#D95F02") +
  facet_wrap(~ outcome, scales = "free_x", nrow = 2) +
  scale_y_continuous(limits = c(0, 1)) +
  labs(x = "True treatment effect", y = "Power (two-sided, 0.05)",
       title = "Power to detect a post-payment effect, by outcome",
       subtitle = "Dashed = 80% power; dotted orange = the corresponding minimum detectable effect.") +
  theme_bw(base_size = 12) + theme(panel.grid.minor = element_blank(), axis.text.x = element_text(angle = 0, hjust = 0.5))
ggsave(file.path(SC, "fig_power_curve.pdf"), pB, width = 9, height = 7)

cat("\nWROTE power_mde_h2h4.csv + fig_mde.pdf + fig_power_curve.pdf\n")
cat("DONE_18\n")
