###############################################################################
# 29_figures.R  --  publication figures, built from the SAME panel as 13.
#
#   fig1_predicted.pdf   MAIN: model-predicted outcome for a Tenet vs a non-Tenet
#                        show (pre-payment H1, controls held at sample means).
#   figA_forest.pdf      APPENDIX: forest of H1 coefficients, all 9 outcomes.
#   figB_eventstudy.pdf  APPENDIX: dynamic DiD (leads/lags) = parallel-trends check.
#   figC_sc_trajectory.pdf APPENDIX: treated composite vs synthetic control path.
#
# Underlying numbers also dumped as fig*_data.csv. Seed 123. PI: Jared Edgerton.
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(ggplot2) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); SCM_WIN <- as.Date("2021-01-01")
MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- panel build (identical to 13_main_h1h3.R) ------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
P[, mfac := factor(month)]; P[, tenet := as.integer(unit %in% TRU)]
P[, post := as.integer(month >= TREAT)]; P[, tp := tenet * post]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit", "month"), all.x = TRUE); P[, log_words := log(n_words)]
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
P <- merge(P, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); P[, log_aud_m := log(aud_mid)]
P[, prop_rus := n_ment_r / n_words]; P[, prop_ukr := n_ment_u / n_words]; P[, prop_comb := (n_ment_r + n_ment_u) / n_words]

## matched donor set (same Mahalanobis match as 13)
covs <- P[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

theme_pub <- theme_bw(base_size = 12) +
  theme(panel.grid.minor = element_blank(),
        axis.text.x = element_text(angle = 0, hjust = 0.5),   # Jared: x labels NOT angled
        strip.background = element_rect(fill = "grey92", colour = NA),
        legend.position = "bottom")

###############################################################################
## FIGURE 1 (MAIN): model-predicted outcome, Tenet vs non-Tenet (pre-payment H1)
##   Fit the H1 control model; predict the conditional mean with tenet=0 vs
##   tenet=1, averaging month FE and holding controls at observed values, so the
##   gap = the Tenet coefficient and the CI comes from its clustered SE.
###############################################################################
HEAD <- list(c("r_score", "Russia stance score"),
             c("r_pos",   "Russia positive rate"),
             c("c_score", "Combined stance score (R - U)"))
pred_rows <- list()
for (h in HEAD){ y <- h[1]; lbl <- h[2]
  d <- P[month < TREAT & n_ment_r >= MINMENT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  m <- feols(as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac")), d, cluster = ~ mfac + unit)
  d0 <- copy(d); d0[, tenet := 0]; d1 <- copy(d); d1[, tenet := 1]
  muC <- mean(predict(m, newdata = d0)); muT <- mean(predict(m, newdata = d1))
  ct <- coeftable(m)["tenet", ]; b <- ct["Estimate"]; se <- ct["Std. Error"]
  pred_rows[[length(pred_rows) + 1]] <- data.table(
    outcome = lbl,
    group   = c("Non-Tenet control", "Tenet show"),
    pred    = c(muC, muT),
    lo      = c(muC, muC + (b - 1.96 * se)),
    hi      = c(muC, muC + (b + 1.96 * se)),
    p       = ct["Pr(>|t|)"])
}
F1 <- rbindlist(pred_rows); F1[, outcome := factor(outcome, levels = sapply(HEAD, `[`, 2))]
fwrite(F1, file.path(SC, "fig1_predicted_data.csv"))
p1 <- ggplot(F1, aes(group, pred, colour = group)) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey60") +
  geom_point(size = 3) +
  geom_errorbar(aes(ymin = lo, ymax = hi), width = 0.15, linewidth = 0.7) +
  facet_wrap(~ outcome, scales = "free_y", nrow = 1) +
  scale_colour_manual(values = c("Non-Tenet control" = "grey45", "Tenet show" = "#b2182b")) +
  scale_x_discrete(labels = function(x) gsub(" ", "\n", x)) +    # break x labels onto 2 lines, unangled
  labs(x = NULL, y = "Predicted outcome", colour = NULL,
       title = "Predicted pre-payment stance: Tenet vs. non-Tenet shows",
       subtitle = "H1 model; controls (log words, log audience) at observed values. Bars = 95% CI on the Tenet gap.") +
  theme_pub
ggsave(file.path(SC, "fig1_predicted.pdf"), p1, width = 9, height = 4)

###############################################################################
## FIGURE A (APPENDIX): forest of H1 coefficients, all 9 outcomes (control spec)
###############################################################################
OUT9 <- list(c("r_score","Russia: score"), c("r_pos","Russia: pos rate"), c("r_net","Russia: net"),
             c("u_score","Ukraine: score"), c("u_pos","Ukraine: pos rate"), c("u_net","Ukraine: net"),
             c("c_score","Combined: score"), c("c_pos","Combined: pos rate"), c("c_net","Combined: net"))
fr <- list()
for (o in OUT9){ y <- o[1]
  d <- P[month < TREAT & n_ment_r >= MINMENT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  m <- feols(as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac")), d, cluster = ~ mfac + unit)
  ct <- coeftable(m)["tenet", ]
  fr[[length(fr) + 1]] <- data.table(outcome = o[2], est = ct["Estimate"], se = ct["Std. Error"],
                                     target = sub(":.*", "", o[2]))
}
FA <- rbindlist(fr); FA[, `:=`(lo = est - 1.96 * se, hi = est + 1.96 * se)]
FA[, sig := factor(ifelse(lo > 0 | hi < 0, "95% CI excludes 0", "n.s."))]
FA[, outcome := factor(outcome, levels = rev(sapply(OUT9, `[`, 2)))]
fwrite(FA, file.path(SC, "figA_forest_data.csv"))
pA <- ggplot(FA, aes(est, outcome, colour = sig)) +
  geom_vline(xintercept = 0, linetype = 2, colour = "grey55") +
  geom_point(size = 2.4) + geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0.25) +
  scale_colour_manual(values = c("95% CI excludes 0" = "#b2182b", "n.s." = "grey55")) +
  labs(x = "Tenet pre-payment level difference (coef.)", y = NULL, colour = NULL,
       title = "H1 selection effects across all stance outcomes") +
  theme_pub
ggsave(file.path(SC, "figA_forest.pdf"), pA, width = 8, height = 5)

###############################################################################
## FIGURE B (APPENDIX): dynamic DiD / event study = PARALLEL-TRENDS check.
##   6-month relative-time bins; reference = the bin just before treatment.
##   Flat, ~0 pre-treatment leads => treated & control move in parallel; the
##   absence of a post jump is what makes the null credible.
###############################################################################
es_one <- function(ycol, ylab){
  d <- P[is.finite(get(ycol)) & is.finite(log_words) & is.finite(log_aud_m) & n_ment_r >= 1 & month >= SCM_WIN]
  d[, rel := as.integer(round(as.numeric(month - TREAT) / 30.4375))]
  d[, bin := floor(rel / 6) * 6]                         # 6-month buckets
  d[, bin := factor(bin)]; d[, bin := relevel(bin, ref = "-6")]   # ref = [-6,0) pre-treat
  m <- feols(as.formula(paste0(ycol, " ~ i(bin, tenet, ref = '-6') + log_words + log_aud_m | unit + month")),
             d, cluster = ~ unit + month)
  ct <- as.data.table(coeftable(m), keep.rownames = "term")[grepl("^bin::", term)]
  ct[, bin := as.integer(sub("bin::(-?\\d+):tenet", "\\1", term))]
  rbind(data.table(bin = -6, Estimate = 0, `Std. Error` = 0),
        ct[, .(bin, Estimate, `Std. Error`)], fill = TRUE)[, outcome := ylab][]
}
FB <- rbind(es_one("r_pos", "Russia positive rate"), es_one("c_score", "Combined stance score"))
setnames(FB, "Std. Error", "se"); FB[, `:=`(lo = Estimate - 1.96 * se, hi = Estimate + 1.96 * se)]
fwrite(FB, file.path(SC, "figB_eventstudy_data.csv"))
pB <- ggplot(FB, aes(bin, Estimate)) +
  geom_hline(yintercept = 0, colour = "grey60") +
  geom_vline(xintercept = 0, linetype = 2, colour = "#b2182b") +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.15) +
  geom_line() + geom_point(size = 1.8) +
  facet_wrap(~ outcome, scales = "free_y", nrow = 1) +
  labs(x = "Months relative to payment (6-month bins, 0 = Oct 2023)", y = "Tenet x period (coef.)",
       title = "Event study: pre-payment parallel trends and post-payment (non-)effect") +
  theme_pub
ggsave(file.path(SC, "figB_eventstudy.pdf"), pB, width = 9, height = 4)

###############################################################################
## FIGURE C (APPENDIX): synthetic-control trajectory (treated vs synthetic).
##   Good pre-period overlap = the SC counterfactual is credible; post gap = effect.
###############################################################################
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); D <- t(Y0p) %*% Y0p + diag(1e-8, n); dv <- as.vector(t(Y0p) %*% y1p)
  A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n)); tryCatch(solve.QP(D, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm_path <- function(pan, col, wcol){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(NULL)
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]; mo <- sort(comp$month); pre <- mo < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(NULL); y1 <- comp$y[match(mo, comp$month)]
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]; dm <- as.matrix(don[, -1])
  for (j in seq_len(ncol(dm))){ v <- dm[, j]; if (anyNA(v)) { v[is.na(v)] <- mean(v, na.rm = TRUE); dm[, j] <- v } }
  good <- which(apply(dm, 2, function(x) all(is.finite(x)) & sd(x) > 0)); if (length(good) < 5 || anyNA(y1)) return(NULL)
  Y0 <- dm[, good, drop = FALSE]; w <- scm_w(Y0[pre, , drop = FALSE], y1[pre])
  data.table(month = mo, treated = y1, synth = as.vector(Y0 %*% w))
}
scC <- rbind(
  if (!is.null(x <- scm_path(P, "r_pos", "n_ment_r")))  x[, outcome := "Russia positive rate"],
  if (!is.null(x <- scm_path(P, "c_score", "n_ment_r"))) x[, outcome := "Combined stance score"],
  fill = TRUE)
if (!is.null(scC) && nrow(scC)){
  FC <- melt(scC, id.vars = c("month", "outcome"), measure.vars = c("treated", "synth"),
             variable.name = "series", value.name = "value")
  FC[, series := factor(series, labels = c("Treated (Tenet)", "Synthetic control"))]
  fwrite(FC, file.path(SC, "figC_sc_trajectory_data.csv"))
  pC <- ggplot(FC, aes(month, value, colour = series, linetype = series)) +
    geom_vline(xintercept = as.numeric(TREAT), linetype = 2, colour = "grey55") +
    geom_line(linewidth = 0.7) +
    facet_wrap(~ outcome, scales = "free_y", nrow = 1) +
    scale_colour_manual(values = c("Treated (Tenet)" = "#b2182b", "Synthetic control" = "grey35")) +
    scale_x_date(date_labels = "%Y") +
    labs(x = NULL, y = "Outcome", colour = NULL, linetype = NULL,
         title = "Synthetic-control fit: treated composite vs. synthetic counterfactual") +
    theme_pub
  ggsave(file.path(SC, "figC_sc_trajectory.pdf"), pC, width = 9, height = 4)
}
cat("WROTE fig1_predicted / figA_forest / figB_eventstudy / figC_sc_trajectory (.pdf + _data.csv)\n")
