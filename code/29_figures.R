###############################################################################
# 29_figures.R  --  publication figures for H1-H4, built from the same panels
# as 13/15.
#   fig1_predicted.pdf    MAIN: model-predicted headline outcome, Tenet vs
#                         non-Tenet, one panel per hypothesis (H1-H4).
#   figA_forest.pdf       APPENDIX: forest of all outcomes, faceted by hypothesis.
#   figB_eventstudy.pdf   APPENDIX: dynamic DiD (parallel-trends check), H2 & H4.
#   figC_sc_trajectory.pdf APPENDIX: treated vs synthetic-control path.
# Underlying numbers dumped as fig*_data.csv. Seed 123. PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(ggplot2) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); SCM_WIN <- as.Date("2021-01-01")
MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- stance/agenda panel (identical to 13) ----------------------------------
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

## ---- H4 divergence panel (main arm = all/contemp/rare) ----------------------
H <- fread(file.path(SC, "h4_divergence_panel.csv")); H[, month := as.Date(month)]
H <- H[topicset == "all" & reference == "contemp" & rare == "rare"]
H[, unit := fifelse(unit %in% TIM, "tim_pool", unit)]
H[, tenet := as.integer(unit %in% TRU)]; H[, post := as.integer(month >= TREAT)]; H[, tp := tenet * post]
H <- merge(H, Vunit, by = c("unit", "month"), all.x = TRUE); H[, log_words := log(n_words)]
H <- merge(H, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); H[, log_aud_m := log(aud_mid)]

## matched donor set (same Mahalanobis match as 13)
covs <- P[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

theme_pub <- theme_bw(base_size = 12) +
  theme(panel.grid.minor = element_blank(), axis.text.x = element_text(angle = 0, hjust = 0.5),
        strip.background = element_rect(fill = "grey92", colour = NA), legend.position = "bottom")

## clean show titles (no underscores) + colourblind-safe palette (Dark2) -------
nice_show <- function(u){
  m <- c(the_benny_show = "The Benny Show", the_rubin_report = "The Rubin Report",
         timcast_irl = "Timcast IRL", tim_pool_daily_news = "Tim Pool Daily News",
         the_culture_war_podcast_with_tim_pool = "The Culture War", tim_pool = "Tim Pool")
  unname(ifelse(u %in% names(m), m[u], tools::toTitleCase(gsub("_", " ", u)))) }
ACCENT  <- "#D95F02"; NEUTRAL <- "grey75"                                  # Dark2 orange vs grey
SHOWCOL <- c("The Benny Show" = "#1B9E77", "The Rubin Report" = "#D95F02", "Tim Pool" = "#7570B3")  # Dark2

## ---- predicted-contrast helpers ---------------------------------------------
pred_lvl <- function(d, y){                                  # H1: pre-payment level
  d <- d[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  m <- feols(as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac")), d, cluster = ~ mfac + unit)
  muC <- mean(d[tenet == 0][[y]], na.rm = TRUE); ct <- coeftable(m)["tenet", ]
  data.table(group = c("Non-Tenet", "Tenet"), pred = c(muC, muC + ct["Estimate"]),
             lo = c(muC, muC + ct["Estimate"] - 1.96*ct["Std. Error"]),
             hi = c(muC, muC + ct["Estimate"] + 1.96*ct["Std. Error"]), p = ct["Pr(>|t|)"]) }
pred_did <- function(d, y){                                  # H2/H3/H4: post-payment DiD
  d <- d[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  m <- feols(as.formula(paste0(y, " ~ tp + log_words + log_aud_m | unit + month")), d, cluster = ~ unit + month)
  muC <- mean(d[post == 1 & tenet == 0][[y]], na.rm = TRUE); ct <- coeftable(m)["tp", ]
  data.table(group = c("Non-Tenet", "Tenet"), pred = c(muC, muC + ct["Estimate"]),
             lo = c(muC, muC + ct["Estimate"] - 1.96*ct["Std. Error"]),
             hi = c(muC, muC + ct["Estimate"] + 1.96*ct["Std. Error"]), p = ct["Pr(>|t|)"]) }

###############################################################################
## FIGURE 1 (MAIN): predicted headline outcome, Tenet vs non-Tenet, per hypothesis
###############################################################################
F1 <- rbind(
  cbind(panel = "H1: Combined positive rate\n(pre-payment selection)", pred_lvl(P[month < TREAT & n_ment_r >= MINMENT & n_ment_u >= MINMENT], "c_pos")),
  cbind(panel = "H2: Combined positive rate\n(post-payment DiD)",      pred_did(P[n_ment_r >= MINMENT & n_ment_u >= MINMENT], "c_pos")),
  cbind(panel = "H3: Combined topic proportion\n(post-payment DiD)",   pred_did(P, "prop_comb")),
  cbind(panel = "H4: JS divergence\n(post-payment DiD)",               pred_did(H, "jsd")))
F1[, panel := factor(panel, levels = unique(panel))]
fwrite(F1, file.path(SC, "fig1_predicted_data.csv"))
p1 <- ggplot(F1, aes(group, pred, colour = group)) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey70") +
  geom_point(size = 3) + geom_errorbar(aes(ymin = lo, ymax = hi), width = 0.16, linewidth = 0.7) +
  facet_wrap(~ panel, scales = "free_y", nrow = 1) +
  scale_colour_manual(values = c("Non-Tenet" = "grey45", "Tenet" = ACCENT)) +
  labs(x = NULL, y = "Predicted outcome", colour = NULL,
       title = "Predicted outcome for a Tenet vs. non-Tenet show, by hypothesis",
       subtitle = "Controls held at observed values. Bars = 95% CI on the Tenet gap (H1 level; H2-H4 treated x post).") +
  theme_pub
ggsave(file.path(SC, "fig1_predicted.pdf"), p1, width = 12, height = 4)

###############################################################################
## FIGURE A (APPENDIX): forest of all outcomes, faceted by hypothesis
###############################################################################
fr_lvl <- function(y, lbl, hyp, dat = P){
  d <- dat[month < TREAT & n_ment_r >= MINMENT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  m <- feols(as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac")), d, cluster = ~ mfac + unit)
  ct <- coeftable(m)["tenet", ]; data.table(hyp = hyp, outcome = lbl, est = ct["Estimate"], se = ct["Std. Error"]) }
fr_did <- function(y, lbl, hyp, dat = P, mm = TRUE){
  d <- dat[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]; if (mm) d <- d[n_ment_r >= MINMENT]
  m <- feols(as.formula(paste0(y, " ~ tp + log_words + log_aud_m | unit + month")), d, cluster = ~ unit + month)
  ct <- coeftable(m)["tp", ]; data.table(hyp = hyp, outcome = lbl, est = ct["Estimate"], se = ct["Std. Error"]) }
FA <- rbindlist(list(
  fr_lvl("r_score","Russia: score","H1 selection"),  fr_lvl("r_pos","Russia: pos","H1 selection"),   fr_lvl("r_net","Russia: net","H1 selection"),
  fr_lvl("u_score","Ukraine: score","H1 selection"), fr_lvl("u_pos","Ukraine: pos","H1 selection"),  fr_lvl("u_net","Ukraine: net","H1 selection"),
  fr_lvl("c_score","Combined: score","H1 selection"),fr_lvl("c_pos","Combined: pos","H1 selection"), fr_lvl("c_net","Combined: net","H1 selection"),
  fr_did("r_score","Russia: score","H2 stance"),  fr_did("r_pos","Russia: pos","H2 stance"),   fr_did("r_net","Russia: net","H2 stance"),
  fr_did("u_score","Ukraine: score","H2 stance"), fr_did("u_pos","Ukraine: pos","H2 stance"),  fr_did("u_net","Ukraine: net","H2 stance"),
  fr_did("c_score","Combined: score","H2 stance"),fr_did("c_pos","Combined: pos","H2 stance"), fr_did("c_net","Combined: net","H2 stance"),
  fr_did("prop_rus","Russia share","H3 agenda", mm = FALSE), fr_did("prop_ukr","Ukraine share","H3 agenda", mm = FALSE), fr_did("prop_comb","Combined share","H3 agenda", mm = FALSE),
  fr_did("jsd","JSD","H4 divergence", dat = H, mm = FALSE), fr_did("kl_sm","KL","H4 divergence", dat = H, mm = FALSE), fr_did("cosine","Cosine dist.","H4 divergence", dat = H, mm = FALSE)))
FA[, `:=`(lo = est - 1.96*se, hi = est + 1.96*se)]
FA[, sig := factor(ifelse(lo > 0 | hi < 0, "95% CI excludes 0", "n.s."))]
FA[, hyp := factor(hyp, levels = c("H1 selection","H2 stance","H3 agenda","H4 divergence"))]
FA[, outcome := factor(outcome, levels = rev(unique(outcome)))]
fwrite(FA, file.path(SC, "figA_forest_data.csv"))
pA <- ggplot(FA, aes(est, outcome, colour = sig)) +
  geom_vline(xintercept = 0, linetype = 2, colour = "grey55") +
  geom_point(size = 2.2) + geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0.25) +
  facet_wrap(~ hyp, scales = "free", ncol = 2) +
  scale_colour_manual(values = c("95% CI excludes 0" = ACCENT, "n.s." = "grey55")) +
  labs(x = "Coefficient (H1: level; H2-H4: treated x post)", y = NULL, colour = NULL,
       title = "Treatment coefficients across all outcomes, by hypothesis") +
  theme_pub
ggsave(file.path(SC, "figA_forest.pdf"), pA, width = 10, height = 7)

###############################################################################
## FIGURE B (APPENDIX): event study (parallel-trends), H2 stance + H4 divergence
###############################################################################
es_one <- function(dat, ycol, ylab, mm = TRUE){
  d <- dat[is.finite(get(ycol)) & is.finite(log_words) & is.finite(log_aud_m) & month >= SCM_WIN]
  if (mm) d <- d[n_ment_r >= 1]
  d[, rel := as.integer(round(as.numeric(month - TREAT) / 30.4375))]; d[, bin := factor(floor(rel/6) * 6)]
  d[, bin := relevel(bin, ref = "-6")]
  m <- feols(as.formula(paste0(ycol, " ~ i(bin, tenet, ref = '-6') + log_words + log_aud_m | unit + month")), d, cluster = ~ unit + month)
  ct <- as.data.table(coeftable(m), keep.rownames = "term")[grepl("^bin::", term)]
  ct[, bin := as.integer(sub("bin::(-?\\d+):tenet", "\\1", term))]
  rbind(data.table(bin = -6, Estimate = 0, `Std. Error` = 0), ct[, .(bin, Estimate, `Std. Error`)], fill = TRUE)[, outcome := ylab][] }
FB <- rbind(es_one(P, "c_score", "H2: Combined stance score"),
            es_one(P, "prop_comb", "H3: Combined agenda share", mm = FALSE),
            es_one(H, "jsd", "H4: Agenda divergence (JSD)", mm = FALSE))
setnames(FB, "Std. Error", "se"); FB[, `:=`(lo = Estimate - 1.96*se, hi = Estimate + 1.96*se)]
fwrite(FB, file.path(SC, "figB_eventstudy_data.csv"))
pB <- ggplot(FB, aes(bin, Estimate)) +
  geom_hline(yintercept = 0, colour = "grey60") + geom_vline(xintercept = 0, linetype = 2, colour = ACCENT) +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.15) + geom_line() + geom_point(size = 1.8) +
  facet_wrap(~ outcome, scales = "free_y", nrow = 1) +
  labs(x = "Months relative to payment (6-month bins, 0 = Oct 2023)", y = "Tenet x period (coef.)",
       title = "Event study: pre-payment parallel trends and post-payment (non-)effect") +
  theme_pub
ggsave(file.path(SC, "figB_eventstudy.pdf"), pB, width = 12, height = 4)

###############################################################################
## FIGURE C (APPENDIX): synthetic-control trajectory (treated vs synthetic)
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
  data.table(month = mo, treated = y1, synth = as.vector(Y0 %*% w)) }
scC <- rbind(
  if (!is.null(x <- scm_path(P, "c_score", "n_ment_r"))) x[, outcome := "H2: Combined stance score"],
  if (!is.null(x <- scm_path(H, "jsd", "n_sentences"))) x[, outcome := "H4: Agenda divergence (JSD)"], fill = TRUE)
if (!is.null(scC) && nrow(scC)){
  FC <- melt(scC, id.vars = c("month", "outcome"), measure.vars = c("treated", "synth"), variable.name = "series", value.name = "value")
  FC[, series := factor(series, labels = c("Treated (Tenet)", "Synthetic control"))]
  fwrite(FC, file.path(SC, "figC_sc_trajectory_data.csv"))
  pC <- ggplot(FC, aes(month, value, colour = series, linetype = series)) +
    geom_vline(xintercept = as.numeric(TREAT), linetype = 2, colour = "grey55") + geom_line(linewidth = 0.7) +
    facet_wrap(~ outcome, scales = "free_y", nrow = 1) +
    scale_colour_manual(values = c("Treated (Tenet)" = ACCENT, "Synthetic control" = "grey35")) +
    scale_x_date(date_labels = "%Y") +
    labs(x = NULL, y = "Outcome", colour = NULL, linetype = NULL,
         title = "Synthetic-control fit: treated composite vs. synthetic counterfactual") + theme_pub
  ggsave(file.path(SC, "figC_sc_trajectory.pdf"), pC, width = 9, height = 4)
}

###############################################################################
## FIGURE I (APPENDIX): parallel trends across estimators -- 3 rows x 4 cols.
##   Rows = TWFE (all controls) / Matched controls / Synthetic control counterfactual
##   Cols = the four main outcomes. Each panel: treated composite vs counterfactual.
##   Pre-payment overlap supports parallel trends for each estimator.
###############################################################################
PTO <- list(
  list("Russia positive rate",      P, "r_pos",     "n_ment_r",    quote(n_ment_r >= MINMENT)),
  list("Combined positive rate",    P, "c_pos",     "n_ment_r",    quote(n_ment_r >= MINMENT & n_ment_u >= MINMENT)),
  list("Combined topic proportion", P, "prop_comb", "n_words",     quote(TRUE)),
  list("JS divergence",             H, "jsd",       "n_sentences", quote(TRUE)))
build_pt <- function(o){ lab <- o[[1]]; dat <- o[[2]]; y <- o[[3]]; w <- o[[4]]; flt <- o[[5]]
  d <- dat[eval(flt, dat) & is.finite(get(y)) & is.finite(get(w)) & month >= SCM_WIN]
  trt <- d[tenet == 1, .(Treated = weighted.mean(get(y), pmax(get(w), 1))), by = month]
  ctl <- d[tenet == 0, .(cf = weighted.mean(get(y), pmax(get(w), 1))), by = month]
  mch <- d[tenet == 0 & unit %in% matched_units, .(cf = weighted.mean(get(y), pmax(get(w), 1))), by = month]
  sp  <- scm_path(dat, y, w)
  mk <- function(cf, est){ m <- merge(trt, cf, by = "month", all = TRUE)
    melt(m, id.vars = "month", variable.name = "series", value.name = "value")[, `:=`(estimator = est, outcome = lab)][] }
  rbind(mk(ctl, "TWFE (all controls)"), mk(mch, "Matched controls"),
        if (!is.null(sp)) mk(sp[, .(month, cf = synth)], "Synthetic control")) }
FI <- rbindlist(lapply(PTO, build_pt))
FI[, series := factor(series, levels = c("Treated", "cf"), labels = c("Treated", "Counterfactual"))]
FI[, estimator := factor(estimator, levels = c("TWFE (all controls)", "Matched controls", "Synthetic control"))]
FI[, outcome := factor(outcome, levels = sapply(PTO, `[[`, 1))]
fwrite(FI, file.path(SC, "figI_parallel_data.csv"))
pI <- ggplot(FI, aes(month, value, colour = series, linetype = series)) +
  geom_vline(xintercept = as.numeric(TREAT), linetype = 2, colour = "grey55") +
  geom_line(linewidth = 0.6, na.rm = TRUE) +
  facet_wrap(~ estimator + outcome, nrow = 3, scales = "free_y", labeller = labeller(.multi_line = FALSE)) +
  scale_colour_manual(values = c("Treated" = ACCENT, "Counterfactual" = "#0072B2")) +
  scale_linetype_manual(values = c("Treated" = 1, "Counterfactual" = 2)) +
  scale_x_date(date_labels = "%y") +
  labs(x = NULL, y = "Outcome", colour = NULL, linetype = NULL,
       title = "Parallel trends: treated vs. counterfactual under TWFE, matching, and synthetic control",
       subtitle = "Rows = estimator, columns = outcome. Pre-payment overlap supports parallel trends (dashed line = Oct 2023).") +
  theme_pub
ggsave(file.path(SC, "figI_parallel.pdf"), pI, width = 13, height = 8)
###############################################################################
## EXPLORATORY (pick one for the manuscript): per-show Russia/Combined positivity
##   figD_lollipop    -- the 3 Tenet shows vs control reference levels (lollipop)
##   figE_timeseries  -- monthly trajectory, Tenet shows vs control mean + IQR band
##   figF_dumbbell    -- pre vs post per Tenet show (before/after payment)
## Shown for Russia positive rate and Combined stance score. x-axis numeric (no angle).
###############################################################################
EXO <- list(c("r_pos", "Russia positive rate"), c("c_score", "Combined stance score"))
shw <- P[n_ment_r >= MINMENT & is.finite(r_pos) & is.finite(c_score),
         .(r_pos = weighted.mean(r_pos, n_ment_r), c_score = weighted.mean(c_score, n_ment_r),
           w = sum(n_ment_r), tenet = tenet[1]), by = unit]

## (D) LOLLIPOP -- Tenet shows vs control reference (mean + 90th pct) ----------
Dl <- rbindlist(lapply(EXO, function(o){ col <- o[1]
  t <- shw[tenet == 1, .(label = nice_show(unit), val = get(col), kind = "Tenet show")]
  r <- shw[tenet == 0]; rr <- data.table(label = c("Control mean", "Control 90th pct"),
           val = c(weighted.mean(r[[col]], r$w), as.numeric(quantile(r[[col]], .9))), kind = "Reference")
  rbind(t, rr)[, outcome := o[2]][] }))
Dl[, label := factor(label, levels = rev(unique(label)))]
fwrite(Dl, file.path(SC, "figD_lollipop_data.csv"))
pD <- ggplot(Dl, aes(val, label, colour = kind)) +
  geom_segment(aes(x = 0, xend = val, yend = label), linewidth = 0.5) + geom_point(size = 3) +
  facet_wrap(~ outcome, scales = "free_x") +
  scale_colour_manual(values = c("Tenet show" = ACCENT, "Reference" = "grey45")) +
  labs(x = "Mention-weighted value", y = NULL, colour = NULL,
       title = "Per-show positivity: Tenet shows vs. control reference levels") + theme_pub
ggsave(file.path(SC, "figD_lollipop.pdf"), pD, width = 9, height = 4)

## (E) TIME SERIES -- monthly, Tenet shows vs control mean + IQR band ----------
## Three measures: Russia mention share (all months), Russia positive rate and
## Combined stance score (among >=5-mention months). Tenet shows = coloured lines.
TSMEAS <- list(c("prop_rus","Russia mention share","n_words","0"),
               c("r_pos","Russia positive rate","n_ment_r","1"),
               c("c_score","Combined stance score","n_ment_r","1"))
mk <- function(o){ col <- o[1]; lab <- o[2]; w <- o[3]; ment <- o[4] == "1"
  base <- if (ment) P[n_ment_r >= MINMENT & is.finite(get(col))] else P[is.finite(get(col))]
  con <- base[tenet == 0, .(m = weighted.mean(get(col), get(w)),
                            lo = as.numeric(quantile(get(col), .25, na.rm = TRUE)),
                            hi = as.numeric(quantile(get(col), .75, na.rm = TRUE))), by = month][, outcome := lab]
  tre <- base[tenet == 1, .(show = nice_show(unit), month, val = get(col))][, outcome := lab]
  list(con, tre) }
res <- lapply(TSMEAS, mk)
TS <- rbindlist(lapply(res, `[[`, 1)); TT <- rbindlist(lapply(res, `[[`, 2))
TS[, outcome := factor(outcome, levels = sapply(TSMEAS, `[`, 2))]; TT[, outcome := factor(outcome, levels = sapply(TSMEAS, `[`, 2))]
fwrite(TT, file.path(SC, "figE_timeseries_data.csv"))
pE <- ggplot() +
  geom_ribbon(data = TS, aes(month, ymin = lo, ymax = hi), fill = "grey80", alpha = .5) +
  geom_line(data = TS, aes(month, m), colour = "grey40") +
  geom_line(data = TT, aes(month, val, colour = show), linewidth = .6) +
  geom_vline(xintercept = as.numeric(TREAT), linetype = 2, colour = "grey30") +
  facet_wrap(~ outcome, scales = "free_y", nrow = 1) + scale_x_date(date_labels = "%Y") +
  scale_colour_manual(values = SHOWCOL) +
  labs(x = NULL, y = "Value", colour = "Tenet show",
       title = "Monthly Russia agenda & stance: Tenet shows vs. control mean (IQR band)",
       subtitle = "Dashed line = payment (Oct 2023). Grey = control mean and interquartile band.") + theme_pub
ggsave(file.path(SC, "figE_timeseries.pdf"), pE, width = 12, height = 4.5)

## (F) DUMBBELL -- pre vs post per Tenet show ----------------------------------
Df <- rbindlist(lapply(EXO, function(o){ col <- o[1]
  P[tenet == 1 & n_ment_r >= MINMENT & is.finite(get(col)),
    .(pre = weighted.mean(get(col)[post == 0], n_ment_r[post == 0]),
      post = weighted.mean(get(col)[post == 1], n_ment_r[post == 1])), by = unit][, outcome := o[2]] }))
Df <- melt(Df, id.vars = c("unit", "outcome"), variable.name = "period", value.name = "val")
Df[, show := nice_show(unit)]
fwrite(Df, file.path(SC, "figF_dumbbell_data.csv"))
pF <- ggplot(Df, aes(val, show)) +
  geom_line(aes(group = show), colour = "grey60") + geom_point(aes(colour = period), size = 3) +
  facet_wrap(~ outcome, scales = "free_x") +
  scale_colour_manual(values = c("pre" = "grey55", "post" = ACCENT)) +
  labs(x = "Mention-weighted value", y = NULL, colour = NULL,
       title = "Per-show change before vs. after payment (Tenet shows)") + theme_pub
ggsave(file.path(SC, "figF_dumbbell.pdf"), pF, width = 9, height = 4)

## (G) RANKED LOLLIPOP -- every program ranked; Tenet shows highlighted ---------
## The FOUR main-analysis outcomes: Russia positive rate, Combined positive rate,
## Combined topic proportion (H3), JS divergence (H4). All ~224 programs shown;
## the 3 Tenet shows are coloured (legend) and sorted within each panel.
aR <- P[n_ment_r >= MINMENT, .(r_pos = weighted.mean(r_pos, n_ment_r)), by = unit]
aC <- P[n_ment_r >= MINMENT & n_ment_u >= MINMENT, .(c_pos = weighted.mean(c_pos, n_ment_r)), by = unit]
aP <- P[is.finite(prop_comb), .(prop_comb = weighted.mean(prop_comb, n_words)), by = unit]
aJ <- H[is.finite(jsd), .(jsd = weighted.mean(jsd, n_sentences)), by = unit]
agg <- Reduce(function(a, b) merge(a, b, by = "unit", all = TRUE), list(aR, aC, aP, aJ))
agg[, tenet := as.integer(unit %in% TRU)]
G <- melt(agg, id.vars = c("unit", "tenet"), measure.vars = c("r_pos", "c_pos", "prop_comb", "jsd"),
          variable.name = "measure", value.name = "val")
G[, measure := factor(measure, levels = c("r_pos", "c_pos", "prop_comb", "jsd"),
                      labels = c("Russia positive rate", "Combined positive rate",
                                 "Combined topic proportion", "JS divergence"))]
G <- G[is.finite(val)]
G[, rk := frank(val, ties.method = "first"), by = measure]
G[, grp := factor(ifelse(unit %in% TRU, nice_show(unit), "Other program"),
                  levels = c("The Benny Show", "The Rubin Report", "Tim Pool", "Other program"))]
G <- rbind(G[grp == "Other program"], G[grp != "Other program"])          # draw Tenet shows on top
fwrite(G, file.path(SC, "figG_ranked_data.csv"))
GPAL <- c(SHOWCOL, "Other program" = "grey80")
GSZ  <- c("The Benny Show" = 2.6, "The Rubin Report" = 2.6, "Tim Pool" = 2.6, "Other program" = 0.7)
GLW  <- c("The Benny Show" = 0.8, "The Rubin Report" = 0.8, "Tim Pool" = 0.8, "Other program" = 0.3)
pG <- ggplot(G, aes(val, rk)) +
  geom_segment(aes(x = 0, xend = val, yend = rk, colour = grp, linewidth = grp), alpha = 0.8) +
  geom_point(aes(colour = grp, size = grp)) +
  facet_wrap(~ measure, scales = "free", nrow = 2) +
  scale_colour_manual(values = GPAL) +
  scale_size_manual(values = GSZ, guide = "none") + scale_linewidth_manual(values = GLW, guide = "none") +
  labs(x = "Value (programs ranked low to high)", y = NULL, colour = NULL,
       title = "Where the Tenet shows rank among all programs",
       subtitle = "Each lollipop is one program; the three Tenet shows are coloured.") +
  theme_pub + theme(axis.text.y = element_blank(), axis.ticks.y = element_blank()) +
  guides(colour = guide_legend(override.aes = list(size = 3)))
ggsave(file.path(SC, "figG_ranked.pdf"), pG, width = 9, height = 8)

cat("WROTE fig1_predicted / figA_forest / figB_eventstudy / figC_sc_trajectory + figD_lollipop / figE_timeseries / figF_dumbbell / figG_ranked\n")
