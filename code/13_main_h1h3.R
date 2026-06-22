###############################################################################
# 13_main_h1h3.R  --  MAIN analyses for H1, H2, H3 in ONE script, fully SEQUENTIAL
# (no outcome for-loop; small spec helpers are called explicitly once per measure,
# the readable style from 29/30). Supersedes the looped 15_main_analyses.R.
#
# NINE measures for H1 & H2: (Russia, Ukraine, Combined) x (score, pos, net).
#   score = p_pos - p_neg ; pos = positive rate ; net = ordinal mean ; Combined = R - U.
# THREE measures for H3 (Russia share of the whole agenda): Russia, Ukraine,
#   Combined (= R + U war-topic share).
#
# SPECIFICATIONS
#   H1 (pre-payment level):   (a) month-FE, SE clustered by month
#                             (b) matched donor set + month-FE, SE clustered by month
#   H2 (post-payment DiD):    (a) TWFE (unit + month FE), SE clustered by host (unit)
#                             (b) synthetic control (in-space placebo p-value)
#   H3 (agenda proportion):   (a) TWFE,  (b) synthetic control
#
# TREATMENT DATE = 2023-10-01 = first RT payment to Tenet (Oct 2023), ~1 month
# before Tenet's public Nov-2023 launch (DOJ indictment: wires Oct 2023-Aug 2024).
# Window truncated at the Sep-2024 indictment. Treated = tim_pool, benny, rubin.
# Seed 123.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)

CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT   <- as.Date("2023-10-01")   # first payment (pre-launch)
TRUNC   <- as.Date("2024-09-01")   # indictment
SCM_WIN <- as.Date("2021-01-01")   # donor window start for synthetic control
MINMENT <- 5; MINTOT <- 10
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

## ---- panel + derived variables ----------------------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]
P <- P[month < TRUNC]
minm <- min(P$month)
P[, t := as.integer(round(as.numeric(month - minm)/30.4375))]; P[, t2 := t^2]
P[, year := as.integer(format(month, "%Y"))]; P[, mfac := factor(month)]
P[, tenet := as.integer(unit %in% TRU)]
P[, post  := as.integer(month >= TREAT)]; P[, tp := tenet * post]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]

## total-words control (time-varying); Tim = mean words across his three feeds
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit", "month"), all.x = TRUE)
P[, log_words := log(n_words)]

## H3 agenda shares (Russia/Ukraine/Combined mentions over ALL sentences that month)
P[, prop_rus  := n_ment_r / n_words]
P[, prop_ukr  := n_ment_u / n_words]
P[, prop_comb := (n_ment_r + n_ment_u) / n_words]

## ---- static listenership only for Mahalanobis matching covariates -----------
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s){ v <- aud[key == norm(s), mean_audience]; if (length(v)) v[1] else NA_real_ }
units <- unique(P$unit)
unit_aud <- sapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u))
covs <- data.table(unit = units, laud = log(unit_aud))
covs <- merge(covs, P[, .(mlogw = mean(log_words, na.rm = TRUE)), by = unit], by = "unit")
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

## ---- synthetic-control helper (hand-rolled simplex weights + in-space placebo) ----
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); D <- t(Y0p) %*% Y0p + diag(1e-8, n)
  dv <- as.vector(t(Y0p) %*% y1p); A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n))
  tryCatch(solve.QP(D, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(pan, col, wcol){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]
  mo <- sort(unique(dd$month)); pre <- mo < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp[match(mo, comp$month)]$y
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]
  dm <- as.matrix(don[, -1]); good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0)
  if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre)
  rs <- c(); for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }

## ---- three small spec helpers (one call each, no outcome loop) ---------------
# H1: pre-payment level. (a) month-FE clustered by month; (b) matched + month-FE.
fit_h1 <- function(ycol, mentcol, label, combined = FALSE){
  d <- P[month < TREAT & get(mentcol) >= MINMENT & is.finite(get(ycol)) & is.finite(log_words)]
  if (combined) d <- d[n_ment_u >= MINMENT]
  dm <- d[unit %in% matched_units]
  fe  <- feols(as.formula(paste0(ycol, " ~ tenet + log_words | mfac")), d,  cluster = ~mfac)
  mt  <- feols(as.formula(paste0(ycol, " ~ tenet + log_words | mfac")), dm, cluster = ~mfac)
  data.table(hyp = "H1", outcome = label,
    est_FE = round(coef(fe)["tenet"], 4),       p_FE = round(pvalue(fe)["tenet"], 4),
    est_matchFE = round(coef(mt)["tenet"], 4),  p_matchFE = round(pvalue(mt)["tenet"], 4)) }

# H2: post-payment DiD. (a) TWFE clustered by host; (b) synthetic control.
fit_h2 <- function(ycol, wcol, label, combined = FALSE){
  d <- P[get(wcol) >= MINMENT & is.finite(get(ycol)) & is.finite(log_words)]
  if (combined) d <- d[n_ment_u >= MINMENT]
  tw <- feols(as.formula(paste0(ycol, " ~ tp + post:log_words | unit + month")), d, cluster = ~unit)
  sc <- scm(d, ycol, wcol)
  data.table(hyp = "H2", outcome = label,
    est_TWFE = round(coef(tw)["tp"], 4),  p_TWFE = round(pvalue(tw)["tp"], 4),
    est_SCM  = round(sc[1], 4),           p_SCM  = round(sc[2], 4)) }

# H3: agenda proportion. (a) TWFE; (b) synthetic control.
fit_h3 <- function(propcol, label){
  d <- P[n_words >= MINTOT & is.finite(get(propcol)) & is.finite(log_words)]
  tw <- feols(as.formula(paste0(propcol, " ~ tp + post:log_words | unit + month")), d, cluster = ~unit)
  sc <- scm(d, propcol, "n_words")
  data.table(hyp = "H3", outcome = label,
    est_TWFE = round(coef(tw)["tp"], 4),  p_TWFE = round(pvalue(tw)["tp"], 4),
    est_SCM  = round(sc[1], 4),           p_SCM  = round(sc[2], 4)) }

## =============================================================================
## H1  --  pre-payment level (9 measures, explicit calls)
## =============================================================================
H1 <- rbindlist(list(
  fit_h1("r_score", "n_ment_r", "Russia score"),
  fit_h1("r_pos",   "n_ment_r", "Russia pos"),
  fit_h1("r_net",   "n_ment_r", "Russia net"),
  fit_h1("u_score", "n_ment_u", "Ukraine score"),
  fit_h1("u_pos",   "n_ment_u", "Ukraine pos"),
  fit_h1("u_net",   "n_ment_u", "Ukraine net"),
  fit_h1("c_score", "n_ment_r", "Combined score", combined = TRUE),
  fit_h1("c_pos",   "n_ment_r", "Combined pos",   combined = TRUE),
  fit_h1("c_net",   "n_ment_r", "Combined net",   combined = TRUE)))

## =============================================================================
## H2  --  post-payment stance DiD (9 measures, explicit calls)
## =============================================================================
H2 <- rbindlist(list(
  fit_h2("r_score", "n_ment_r", "Russia score"),
  fit_h2("r_pos",   "n_ment_r", "Russia pos"),
  fit_h2("r_net",   "n_ment_r", "Russia net"),
  fit_h2("u_score", "n_ment_u", "Ukraine score"),
  fit_h2("u_pos",   "n_ment_u", "Ukraine pos"),
  fit_h2("u_net",   "n_ment_u", "Ukraine net"),
  fit_h2("c_score", "n_ment_r", "Combined score", combined = TRUE),
  fit_h2("c_pos",   "n_ment_r", "Combined pos",   combined = TRUE),
  fit_h2("c_net",   "n_ment_r", "Combined net",   combined = TRUE)))

## =============================================================================
## H3  --  agenda proportion DiD (3 measures, explicit calls)
## =============================================================================
H3 <- rbindlist(list(
  fit_h3("prop_rus",  "Russia share"),
  fit_h3("prop_ukr",  "Ukraine share"),
  fit_h3("prop_comb", "Combined share")))

## ---- show & save ------------------------------------------------------------
cat("\n===== H1 (pre-payment level) =====\n"); print(H1)
cat("\n===== H2 (post-payment stance DiD) =====\n"); print(H2)
cat("\n===== H3 (agenda proportion DiD) =====\n"); print(H3)
fwrite(H1, file.path(SC, "main_h1.csv"))
fwrite(H2, file.path(SC, "main_h2.csv"))
fwrite(H3, file.path(SC, "main_h3.csv"))
