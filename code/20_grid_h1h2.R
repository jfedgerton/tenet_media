###############################################################################
# 19_probshift_grid.R  --  probability mass-transfer robustness grid for H1 & H2,
# now swept over multiple candidate TREATMENT DATES and all five specifications.
#
# Probability perturbation (per sentence, 4-class softmax): move mass `s` from a
# source class to a destination class (clipped, sum stays 1), re-argmax, recompute
# score=p_pos-p_neg. 12 ops + identity, crossed Russia x Ukraine x s in
# seq(.10,.15,.01) = 13 x 13 x 6 = 1014 mass cells.
#
# TREATMENT-DATE SWEEP (3 event-anchored dates from the DOJ indictment timeline):
#   2022-12-01  Russia begins the Tenet relationship (Chen <-> RT persona "Grigoriann")
#   2023-10-01  first payments to influencers (paid Oct 2023 - Aug 2024)
#   2023-11-01  podcasters join / Tenet public launch (Nov 8, 2023)
# Window truncated at the INDICTMENT (2024-09-04 -> month < 2024-09): public
# acknowledgement is expected to halt any effect.
#
# Specs per (mass cell x treat date x outcome):
#   H1_OLS      y ~ tenet + t + t^2 + log_aud           (pre-period, cluster show)
#   H1_matched  same, Mahalanobis-matched control set
#   H2_TWFE     y ~ tp + post:log_aud | unit + month    (cluster show)
#   H2_matched  same TWFE on matched control set
#   H2_SCM      composite treated vs donor pool, quadprog weights + in-space placebo
#
# Outcomes (9): metric in {score, pos, net(=pos-neg diff)} x set in
#   {Russia, Ukraine, Combined = Russia - Ukraine}  (anti-Ukraine == pro-Russia).
#
# Input : data/sc_results/probs_4class.csv   Output: master_probshift_coefs.csv
# Treated units = the_benny_show, the_rubin_report, tim_pool (3 feeds pooled).
# PI: Jared Edgerton (PSU). Seed 123.
###############################################################################

suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(parallel) })
set.seed(123)
setDTthreads(1)
NC <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "8"))

COLLAB <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(COLLAB, "data", "sc_results")
TREAT_DATES <- as.Date(c("2022-12-01","2023-10-01","2023-11-01"))
START <- as.Date("2018-01-01"); TRUNC <- as.Date("2024-09-01")   # truncate at indictment
MINMENT <- 5; SCM_WIN <- as.Date("2021-01-01")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

## ---- load sentence-level 4-class probs ----
S <- fread(file.path(SC, "probs_4class.csv"))
S[, date := as.Date(date)]
S <- S[!is.na(date) & date >= START & date < TRUNC]
S[, month := as.Date(format(date, "%Y-%m-01"))]
S[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Rpp <- S$russia_p_pos; Rpn <- S$russia_p_neg; Rpu <- S$russia_p_neu; Rpx <- S$russia_p_unment
Upp <- S$ukraine_p_pos; Upn <- S$ukraine_p_neg; Upu <- S$ukraine_p_neu; Upx <- S$ukraine_p_unment
unit_v <- S$unit; month_v <- S$month
MINM <- min(S$month)

## ---- audience control + matched donor set ----
aud <- fread(file.path(COLLAB, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s) { v <- aud[key == norm(s), mean_audience]; if (length(v) == 0) NA_real_ else v[1] }
units <- unique(S$unit)
ua <- vapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u), numeric(1))
umeta <- data.table(unit = units, mean_audience = ua); umeta[, log_aud := log(mean_audience)]
umeta[, treated := as.integer(unit %in% TRU)]

cov <- aud[, .(key, mean_audience, episodes_per_week, weeks_active)]
uc <- rbindlist(lapply(units, function(u) {
  if (u == "tim_pool") { x <- cov[key %in% norm(TIM)]; data.table(unit = u, a = sum(x$mean_audience, na.rm = T), e = mean(x$episodes_per_week, na.rm = T), w = max(x$weeks_active, na.rm = T)) }
  else { x <- cov[key == norm(u)]; if (nrow(x) == 0) return(NULL); data.table(unit = u, a = x$mean_audience[1], e = x$episodes_per_week[1], w = x$weeks_active[1]) }
}), fill = TRUE)
uc[, tenet := as.integer(unit %in% TRU)]; uc <- uc[is.finite(log(a))]
X <- as.matrix(uc[, .(la = log(a), e, w)]); X[is.na(X)] <- 0
mo <- Match(Tr = uc$tenet, X = X, M = 3, replace = TRUE)
MU <- unique(c(uc$unit[mo$index.treated], uc$unit[mo$index.control]))

## ---- mass-transfer op ----
apply_op <- function(pp, pn, pu, px, op, s) {
  if (op == 1L)      { m <- pmin(s, pp); pp <- pp - m; pu <- pu + m }
  else if (op == 2L) { m <- pmin(s, pn); pn <- pn - m; pu <- pu + m }
  else if (op == 3L) { m <- pmin(s, pu); pu <- pu - m; pp <- pp + m }
  else if (op == 4L) { m <- pmin(s, pu); pu <- pu - m; pn <- pn + m }
  else if (op == 5L) { m <- pmin(s, pu); pu <- pu - m; pp <- pp + m/2; pn <- pn + m/2 }
  else if (op == 6L) { ma <- pmin(s, pp); mb <- pmin(s, pn); pp <- pp - ma; pn <- pn - mb; pu <- pu + ma + mb }
  else if (op == 7L) { m <- pmin(s, pp); pp <- pp - m; px <- px + m }
  else if (op == 8L) { m <- pmin(s, pn); pn <- pn - m; px <- px + m }
  else if (op == 9L) { m <- pmin(s, px); px <- px - m; pp <- pp + m }
  else if (op == 10L){ m <- pmin(s, px); px <- px - m; pn <- pn + m }
  else if (op == 11L){ m <- pmin(s, px); px <- px - m; pp <- pp + m/2; pn <- pn + m/2 }
  else if (op == 12L){ ma <- pmin(s, pp); mb <- pmin(s, pn); pp <- pp - ma; pn <- pn - mb; px <- px + ma + mb }
  list(pp, pn, pu, px)
}
OPNAME <- c("none","Pos>Neu","Neg>Neu","Neu>Pos","Neu>Neg","Neu>NegPos","NegPos>Neu",
            "Pos>Unm","Neg>Unm","Unm>Pos","Unm>Neg","Unm>NegPos","NegPos>Unm")
grabT <- function(m, term) { ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA, NA)); as.numeric(ct[term, c("Estimate", "Std. Error", "Pr(>|t|)")]) }

## ---- SCM (quadprog simplex + in-space placebo), treat date is a parameter ----
scm_weights <- function(Y0pre, y1pre) { n <- ncol(Y0pre); Dmat <- t(Y0pre) %*% Y0pre + diag(1e-8, n); dvec <- as.vector(t(Y0pre) %*% y1pre); Amat <- cbind(rep(1, n), diag(n)); bvec <- c(1, rep(0, n)); tryCatch(solve.QP(Dmat, dvec, Amat, bvec, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm_one <- function(y1, Y0, pre) { w <- scm_weights(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w); list(ratio = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm_outcome <- function(pan, col, wcol, treat) {
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[treated == 1]; if (nrow(tr) == 0) return(c(NA, NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]
  months <- sort(unique(dd$month)); pre <- months < treat
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA, NA))
  y1 <- comp[match(months, comp$month)]$y
  don <- dcast(dd[treated == 0], month ~ unit, value.var = col); don <- don[match(months, don$month)]; dm <- as.matrix(don[, -1])
  good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0); if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA, NA))
  Y0 <- dm[, good, drop = FALSE]; main <- scm_one(y1, Y0, pre)
  ratios <- c(); for (j in seq_len(ncol(Y0))) { o <- scm_one(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$ratio)) ratios <- c(ratios, o$ratio) }
  pval <- if (length(ratios)) (sum(ratios >= main$ratio) + 1) / (length(ratios) + 1) else NA
  c(main$gap, main$ratio, pval)
}
stance <- list(c("Russia","score","r_score"), c("Russia","pos","r_pos"), c("Russia","net","r_net"),
               c("Ukraine","score","u_score"), c("Ukraine","pos","u_pos"), c("Ukraine","net","u_net"),
               c("Combined","score","c_score"), c("Combined","pos","c_pos"), c("Combined","net","c_net"))

run_cell <- function(ro, uo, s) {
  R <- apply_op(Rpp, Rpn, Rpu, Rpx, ro, s)
  U <- apply_op(Upp, Upn, Upu, Upx, uo, s)
  Rm <- max.col(cbind(R[[1]], R[[2]], R[[3]], R[[4]]), ties.method = "first")
  Um <- max.col(cbind(U[[1]], U[[2]], U[[3]], U[[4]]), ties.method = "first")
  sd <- data.table(unit = unit_v, month = month_v,
                   r_ment = Rm != 4L, r_sc = R[[1]] - R[[2]], r_p = Rm == 1L, r_o = c(1L,-1L,0L,0L)[Rm],
                   u_ment = Um != 4L, u_sc = U[[1]] - U[[2]], u_p = Um == 1L, u_o = c(1L,-1L,0L,0L)[Um])
  aggR <- sd[r_ment == TRUE, .(n_ment_r = .N, r_score = mean(r_sc), r_pos = mean(r_p), r_net = mean(r_o)), by = .(unit, month)]
  aggU <- sd[u_ment == TRUE, .(n_ment_u = .N, u_score = mean(u_sc), u_pos = mean(u_p), u_net = mean(u_o)), by = .(unit, month)]
  pan <- merge(aggR, aggU, by = c("unit", "month"), all = TRUE)
  pan <- merge(pan, umeta[, .(unit, log_aud, treated)], by = "unit", all.x = TRUE)
  pan[, t := as.integer(round(as.numeric(month - MINM) / 30.4375))]; pan[, t2 := t^2]; pan[, tenet := treated]
  pan[, c_score := r_score - u_score]; pan[, c_pos := r_pos - u_pos]; pan[, c_net := r_net - u_net]
  out <- vector("list", length(TREAT_DATES) * length(stance) * 5L); k <- 0L
  for (td in TREAT_DATES) {
    pan[, post := as.integer(month >= td)]; pan[, tp := tenet * post]
    for (o in stance) {
      set <- o[1]; metric <- o[2]; col <- o[3]
      if (set == "Combined") d <- pan[n_ment_r >= MINMENT & n_ment_u >= MINMENT & !is.na(log_aud) & !is.na(get(col))]
      else if (set == "Russia") d <- pan[n_ment_r >= MINMENT & !is.na(log_aud) & !is.na(get(col))]
      else d <- pan[n_ment_u >= MINMENT & !is.na(log_aud) & !is.na(get(col))]
      pre <- d[post == 0]; prem <- pre[unit %in% MU]; dmU <- d[unit %in% MU]
      f1 <- as.formula(paste(col, "~ tenet + t + t2 + log_aud"))
      ftw <- as.formula(paste(col, "~ tp + post:log_aud | unit + month"))
      wcol <- if (set == "Ukraine") "n_ment_u" else "n_ment_r"
      add <- function(spec, v) { k <<- k + 1L; out[[k]] <<- data.table(rus_op = ro, ukr_op = uo, shift = s, treat_date = as.character(td), set = set, metric = metric, spec = spec, estimate = v[1], se = v[2], p = v[3]) }
      add("H1_OLS",     grabT(tryCatch(feols(f1, pre, cluster = ~unit), error = function(e) NULL), "tenet"))
      add("H1_matched", grabT(tryCatch(feols(f1, prem, cluster = ~unit), error = function(e) NULL), "tenet"))
      add("H2_TWFE",    grabT(tryCatch(feols(ftw, d, cluster = ~unit), error = function(e) NULL), "tp"))
      add("H2_matched", grabT(tryCatch(feols(ftw, dmU, cluster = ~unit), error = function(e) NULL), "tp"))
      sc <- tryCatch(scm_outcome(d, col, wcol, td), error = function(e) c(NA, NA, NA))
      add("H2_SCM", c(sc[1], NA_real_, sc[3]))
    }
  }
  rbindlist(out)
}

grid <- as.data.table(expand.grid(rus_op = 0:12, ukr_op = 0:12, s = seq(0.10, 0.15, 0.01), KEEP.OUT.ATTRS = FALSE))
cat("CELLS", nrow(grid), "DATES", length(TREAT_DATES), "CORES", NC, "\n")
res <- mclapply(seq_len(nrow(grid)), function(i) run_cell(grid$rus_op[i], grid$ukr_op[i], grid$s[i]), mc.cores = NC)
fin <- rbindlist(res, fill = TRUE)
fin[, rus_op_name := OPNAME[rus_op + 1L]]; fin[, ukr_op_name := OPNAME[ukr_op + 1L]]
fin[, sig := fifelse(is.na(p), "NA", fifelse(p < 0.01, "***", fifelse(p < 0.05, "**", fifelse(p < 0.1, "*", "ns"))))]
setcolorder(fin, c("rus_op","rus_op_name","ukr_op","ukr_op_name","shift","treat_date","set","metric","spec","estimate","se","p","sig"))
fwrite(fin, file.path(SC, "master_probshift_coefs.csv"))
cat("ROWS", nrow(fin), "DONE_PROBSHIFT\n")
