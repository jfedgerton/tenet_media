###############################################################################
# grid_sweep.R  --  perturbation-robustness sweep for H1 and H2 (NOT H3).
#
# Sweeps the 20 deterministic relabeling rules (R0 baseline .. G5) applied to the
# c0 faithful labels, re-estimating H1 and H2 for all 9 stance outcomes.
#   H1  OLS:      y ~ tenet + t + t^2 + log_aud        (pre-period, cluster show)
#   H1  matched:  same, Mahalanobis-matched controls
#   H2  TWFE:     y ~ tp + post:log_aud | unit + month (cluster show)
#   H2  SCM:      composite treated vs donors, quadprog weights + placebo p
# Outcomes (9): score/pos/net x {Russia, Ukraine, Combined = R - U}.
# NOTE: `score` (prob-based) is invariant to relabeling by construction; `pos`/`net`
# are the metrics that move across rules.
#
# Input: perturb_panels_all.csv (built by build_h_panels.py).
# PI: Jared Edgerton (PSU). Seed 123.
###############################################################################

suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)
COLLAB <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(COLLAB, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); MINMENT <- 5; SCM_WIN <- as.Date("2021-01-01")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "perturb_panels_all.csv")); P[, month := as.Date(month)]
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month - minm) / 30.4375))]; P[, t2 := t^2]
P[, tenet := as.integer(unit %in% TRU)]; P[, post := as.integer(month >= TREAT)]; P[, tp := tenet * post]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]

aud <- fread(file.path(COLLAB, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s) { v <- aud[key == norm(s), mean_audience]; if (length(v) == 0) NA_real_ else v[1] }
units <- unique(P$unit)
ua <- vapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u), numeric(1))
am <- data.table(unit = units, mean_audience = ua); am[, log_aud := log(mean_audience)]; P <- merge(P, am, by = "unit", all.x = TRUE)

cov <- aud[, .(key, mean_audience, episodes_per_week, weeks_active)]
uc <- rbindlist(lapply(units, function(u) {
  if (u == "tim_pool") { s <- cov[key %in% norm(TIM)]; data.table(unit = u, a = sum(s$mean_audience, na.rm = T), e = mean(s$episodes_per_week, na.rm = T), w = max(s$weeks_active, na.rm = T)) }
  else { s <- cov[key == norm(u)]; if (nrow(s) == 0) return(NULL); data.table(unit = u, a = s$mean_audience[1], e = s$episodes_per_week[1], w = s$weeks_active[1]) }
}), fill = TRUE)
uc[, tenet := as.integer(unit %in% TRU)]; uc <- uc[is.finite(log(a))]
X <- as.matrix(uc[, .(la = log(a), e, w)]); X[is.na(X)] <- 0
mo <- Match(Tr = uc$tenet, X = X, M = 3, replace = TRUE)
MU <- unique(c(uc$unit[mo$index.treated], uc$unit[mo$index.control]))

scm_weights <- function(Y0pre, y1pre) { n <- ncol(Y0pre); Dmat <- t(Y0pre) %*% Y0pre + diag(1e-8, n); dvec <- as.vector(t(Y0pre) %*% y1pre); Amat <- cbind(rep(1, n), diag(n)); bvec <- c(1, rep(0, n)); tryCatch(solve.QP(Dmat, dvec, Amat, bvec, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm_one <- function(y1, Y0, pre) { w <- scm_weights(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w); list(ratio = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm_outcome <- function(pan, col, wcol) {
  d <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- d[treated == 1]; if (nrow(tr) == 0) return(c(NA, NA, NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]
  months <- sort(unique(d$month)); pre <- months < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA, NA, NA))
  y1 <- comp[match(months, comp$month)]$y
  don <- dcast(d[treated == 0], month ~ unit, value.var = col); don <- don[match(months, don$month)]; dm <- as.matrix(don[, -1])
  good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0); if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA, NA, length(good)))
  Y0 <- dm[, good, drop = FALSE]; main <- scm_one(y1, Y0, pre)
  ratios <- c(); for (j in seq_len(ncol(Y0))) { o <- scm_one(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$ratio)) ratios <- c(ratios, o$ratio) }
  pval <- if (length(ratios)) (sum(ratios >= main$ratio) + 1) / (length(ratios) + 1) else NA
  c(main$gap, main$ratio, pval, length(good))
}
grabT <- function(m, term) { ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA, NA)); as.numeric(ct[term, c("Estimate", "Std. Error", "Pr(>|t|)")]) }

stance <- list(c("Russia","score","r_score","n_ment_r"), c("Russia","pos","r_pos","n_ment_r"), c("Russia","net","r_net","n_ment_r"),
               c("Ukraine","score","u_score","n_ment_u"), c("Ukraine","pos","u_pos","n_ment_u"), c("Ukraine","net","u_net","n_ment_u"),
               c("Combined","score","c_score","BOTH"), c("Combined","pos","c_pos","BOTH"), c("Combined","net","c_net","BOTH"))
RES <- list()
for (rl in unique(P$rule)) {
  d0 <- P[rule == rl]
  for (o in stance) {
    set <- o[1]; metric <- o[2]; col <- o[3]; mf <- o[4]
    d <- if (mf == "BOTH") d0[n_ment_r >= MINMENT & n_ment_u >= MINMENT & !is.na(log_aud)] else d0[get(mf) >= MINMENT & !is.na(log_aud)]
    d <- d[!is.na(get(col))]; pre <- d[post == 0]; prem <- pre[unit %in% MU]
    f1 <- as.formula(paste(col, "~ tenet + t + t2 + log_aud")); wc <- if (set == "Ukraine") "n_ment_u" else "n_ment_r"
    v <- grabT(feols(f1, pre, cluster = ~unit), "tenet"); RES[[length(RES)+1]] <- data.table(rule = rl, set = set, metric = metric, spec = "H1_OLS", estimate = v[1], se = v[2], p = v[3], note = "")
    v <- grabT(feols(f1, prem, cluster = ~unit), "tenet"); RES[[length(RES)+1]] <- data.table(rule = rl, set = set, metric = metric, spec = "H1_matched", estimate = v[1], se = v[2], p = v[3], note = "")
    v <- grabT(feols(as.formula(paste(col, "~ tp + post:log_aud | unit + month")), d, cluster = ~unit), "tp"); RES[[length(RES)+1]] <- data.table(rule = rl, set = set, metric = metric, spec = "H2_TWFE", estimate = v[1], se = v[2], p = v[3], note = "")
    sc <- scm_outcome(d, col, wc); RES[[length(RES)+1]] <- data.table(rule = rl, set = set, metric = metric, spec = "H2_SCM", estimate = sc[1], se = NA, p = sc[3], note = paste0("rmspe_ratio=", round(sc[2], 3)))
  }
}
fin <- rbindlist(RES, fill = TRUE)
fin[, sig := fifelse(is.na(p), "NA", fifelse(p < 0.01, "***", fifelse(p < 0.05, "**", fifelse(p < 0.1, "*", "ns"))))]
fwrite(fin, file.path(SC, "master_sweep_coefs.csv"))
cat("ROWS", nrow(fin), "DONE_SWEEP\n")
