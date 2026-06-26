###############################################################################
# 16_grid_h1h2.R  --  MASTER robustness grid for H1 (pre-payment level) and
# H2 (post-payment DiD), one-factor-at-a-time off the MAIN spec (13_main_h1h3.R).
# Supersedes the old probshift-only 16 AND 26_min_mention_sweep.R (folded in here).
#
# SAME BASIS AS 13/15:  time-varying monthly audience (log_aud_m) + total words
# (log_words), month FE, TWO-WAY clustering (H1: month+unit ; H2: unit+month).
#
# Spec set per outcome (mirrors 13 exactly):
#   H1: simple | simpleM | ctrl | ctrlM            (term = tenet; pre-period, |mfac)
#   H2: twfe | twfe_ctrl | twfeM | twfeM_ctrl | scm | scm_ctrl   (term = tp; |unit+month)
#   "simple/twfe"  = NO CONTROLS (the cell the old grid was missing)
#   "ctrl"         = + log_words + log_aud_m
#   "M"            = Mahalanobis-matched donor set (pre-period audience+words, per date)
#   "scm_ctrl"     = SCM on the outcome residualized on log_words | unit+month
#
# Outcomes (15): {score, pos, net} x {Russia, Ukraine, Combined}  PLUS
#                {vol_pos, vol_posneg} x {Russia, Ukraine, Combined}.
#
# AXES SWEPT (each perturbed off baseline = shift 0 / min_ment 5 / conditional):
#   (A) PROB MASS-TRANSFER : 13 Russia ops x 13 Ukraine ops x shift seq(0,0.30,0.025)
#   (B) MIN-MENTION        : {0,1,3,5,10,20}
#   (C) MISSING->0 CODING  : {conditional, zero}   (B x C crossed; A holds at 5/conditional)
#   (D) TREATMENT DATE     : {2022-12-01 RT-relationship, 2023-10-01 first-payment,
#                             2023-11-01 join/launch}  -- swept in BOTH A and B.
#
# Input : data/sc_results/probs_4class.csv  (+ audience_monthly.csv, loso_volume.csv)
# Output: data/sc_results/master_grid_h1h2.csv   Seed 123.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(parallel) })
set.seed(123); setDTthreads(1); setFixest_notes(FALSE)   # quiet singleton/NA note flood
## Execution notes: mclapply uses mc.preschedule=FALSE (fresh fork per cell -> load
## balancing + per-cell memory release), gc(FALSE) per cell, per-cell progress markers
## ([cellA i/N] / [cellB i/N]), and incremental checkpoints after each axis.
NC <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "8"))
SCM_IN_SHIFT <- FALSE       # SCM is fully swept in axis B (dates x min_ment x coding);
                            # set TRUE to ALSO run it under every label-noise cell (very heavy).

CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT_DATES <- as.Date(c("2022-12-01", "2023-10-01", "2023-11-01"))
START <- as.Date("2018-01-01"); TRUNC <- as.Date("2024-09-01"); SCM_WIN <- as.Date("2021-01-01")
MINMENT_BASE <- 5; MINMENT_GRID <- c(0, 1, 3, 5, 10, 20)
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- sentence-level 4-class probs (for the mass-transfer axis) --------------
S <- fread(file.path(SC, "probs_4class.csv")); S[, date := as.Date(date)]
S <- S[!is.na(date) & date >= START & date < TRUNC]
S[, month := as.Date(format(date, "%Y-%m-01"))]; S[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Rpp <- S$russia_p_pos; Rpn <- S$russia_p_neg; Rpu <- S$russia_p_neu; Rpx <- S$russia_p_unment
Upp <- S$ukraine_p_pos; Upn <- S$ukraine_p_neg; Upu <- S$ukraine_p_neu; Upx <- S$ukraine_p_unment
unit_v <- S$unit; month_v <- S$month
rm(S); gc(FALSE)   # drop the big sentence-level table once its columns are extracted

## ---- time-varying controls (same sources as 13) ----------------------------
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
AM <- AM[, .(unit, month, log_aud_m = log(aud_mid))]
V  <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
VOL <- V[, .(log_words = log(mean(n_sent_total))), by = .(unit, month)]

## ---- mass-transfer op (identity = op 0) ------------------------------------
apply_op <- function(pp, pn, pu, px, op, s) {
  if (op == 0L) {} else
  if (op == 1L) { m <- pmin(s, pp); pp <- pp - m; pu <- pu + m } else
  if (op == 2L) { m <- pmin(s, pn); pn <- pn - m; pu <- pu + m } else
  if (op == 3L) { m <- pmin(s, pu); pu <- pu - m; pp <- pp + m } else
  if (op == 4L) { m <- pmin(s, pu); pu <- pu - m; pn <- pn + m } else
  if (op == 5L) { m <- pmin(s, pu); pu <- pu - m; pp <- pp + m/2; pn <- pn + m/2 } else
  if (op == 6L) { ma <- pmin(s, pp); mb <- pmin(s, pn); pp <- pp - ma; pn <- pn - mb; pu <- pu + ma + mb } else
  if (op == 7L) { m <- pmin(s, pp); pp <- pp - m; px <- px + m } else
  if (op == 8L) { m <- pmin(s, pn); pn <- pn - m; px <- px + m } else
  if (op == 9L) { m <- pmin(s, px); px <- px - m; pp <- pp + m } else
  if (op == 10L){ m <- pmin(s, px); px <- px - m; pn <- pn + m } else
  if (op == 11L){ m <- pmin(s, px); px <- px - m; pp <- pp + m/2; pn <- pn + m/2 } else
  if (op == 12L){ ma <- pmin(s, pp); mb <- pmin(s, pn); pp <- pp - ma; pn <- pn - mb; px <- px + ma + mb }
  list(pp, pn, pu, px)
}
OPNAME <- c("none","Pos>Neu","Neg>Neu","Neu>Pos","Neu>Neg","Neu>NegPos","NegPos>Neu",
            "Pos>Unm","Neg>Unm","Unm>Pos","Unm>Neg","Unm>NegPos","NegPos>Unm")

## ---- build a unit-month panel for a given (rus_op, ukr_op, shift) -----------
## Produces conditional outcomes (r_score..c_net), volume outcomes, AND zero-coded
## (unmentioned=0) versions, plus n_ment_r/u, n_total, log_aud_m, log_words.
build_panel <- function(ro, uo, s) {
  ## Process Russia then Ukraine ops sequentially and free each big sentence-level
  ## intermediate immediately, so 48 parallel workers don't balloon RAM (the per-cell
  ## peak stays low). Holds ~4 sentence vectors + sd instead of ~10.
  R <- apply_op(Rpp, Rpn, Rpu, Rpx, ro, s)
  Rm <- max.col(cbind(R[[1]], R[[2]], R[[3]], R[[4]]), ties.method = "first"); r_sc <- R[[1]] - R[[2]]; rm(R)
  U <- apply_op(Upp, Upn, Upu, Upx, uo, s)
  Um <- max.col(cbind(U[[1]], U[[2]], U[[3]], U[[4]]), ties.method = "first"); u_sc <- U[[1]] - U[[2]]; rm(U); gc(FALSE)
  sd <- data.table(unit = unit_v, month = month_v,
    r_ment = Rm != 4L, r_sc = r_sc, r_p = Rm == 1L, r_neg = Rm == 2L, r_o = c(1L,-1L,0L,0L)[Rm],
    u_ment = Um != 4L, u_sc = u_sc, u_p = Um == 1L, u_neg = Um == 2L, u_o = c(1L,-1L,0L,0L)[Um])
  rm(Rm, Um, r_sc, u_sc); gc(FALSE)
  aggR <- sd[r_ment == TRUE, .(n_ment_r = .N, r_score = mean(r_sc), r_pos = mean(r_p), r_net = mean(r_o)), by = .(unit, month)]
  aggU <- sd[u_ment == TRUE, .(n_ment_u = .N, u_score = mean(u_sc), u_pos = mean(u_p), u_net = mean(u_o)), by = .(unit, month)]
  aggV <- sd[, .(n_total = .N, vol_pos_r = sum(r_p), vol_neg_r = sum(r_neg), vol_pos_u = sum(u_p), vol_neg_u = sum(u_neg)), by = .(unit, month)]
  rm(sd); gc(FALSE)
  pan <- merge(merge(aggV, aggR, by = c("unit","month"), all.x = TRUE), aggU, by = c("unit","month"), all.x = TRUE)
  for (cc in c("n_ment_r","n_ment_u","vol_pos_r","vol_neg_r","vol_pos_u","vol_neg_u")) pan[is.na(get(cc)), (cc) := 0L]
  pan[, tenet := as.integer(unit %in% TRU)]
  pan[, c_score := r_score - u_score]; pan[, c_pos := r_pos - u_pos]; pan[, c_net := r_net - u_net]
  pan[, vol_posneg_r := vol_pos_r - vol_neg_r]; pan[, vol_posneg_u := vol_pos_u - vol_neg_u]
  pan[, vol_pos_c := vol_pos_r - vol_pos_u]; pan[, vol_posneg_c := vol_posneg_r - vol_posneg_u]
  # zero-coded (unmentioned -> 0): conditional value x mention-rate; missing month -> 0
  z <- function(val, nm) fifelse(nm > 0 & is.finite(val), val * nm / pan$n_total, 0)
  pan[, r_score0 := z(r_score, n_ment_r)]; pan[, r_pos0 := z(r_pos, n_ment_r)]; pan[, r_net0 := z(r_net, n_ment_r)]
  pan[, u_score0 := z(u_score, n_ment_u)]; pan[, u_pos0 := z(u_pos, n_ment_u)]; pan[, u_net0 := z(u_net, n_ment_u)]
  pan[, c_score0 := r_score0 - u_score0]; pan[, c_pos0 := r_pos0 - u_pos0]; pan[, c_net0 := r_net0 - u_net0]
  pan <- merge(pan, AM,  by = c("unit","month"), all.x = TRUE)
  pan <- merge(pan, VOL, by = c("unit","month"), all.x = TRUE)
  pan[, mfac := factor(month)]
  pan[]
}

## ---- SCM helper (identical to 13: gap-fill donors + in-space placebo p) -----
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); D <- t(Y0p) %*% Y0p + diag(1e-8, n); dv <- as.vector(t(Y0p) %*% y1p)
  A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n)); tryCatch(solve.QP(D, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(pan, col, wcol, td){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]; mo <- sort(comp$month); pre <- mo < td
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp$y[match(mo, comp$month)]
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]; dm <- as.matrix(don[, -1])
  for (j in seq_len(ncol(dm))){ v <- dm[, j]; if (anyNA(v)) { v[is.na(v)] <- mean(v, na.rm = TRUE); dm[, j] <- v } }
  good <- which(apply(dm, 2, function(x) all(is.finite(x)) & sd(x) > 0)); if (length(good) < 5 || anyNA(y1)) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre); rs <- c()
  for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }

gx <- function(m, term){ ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA, NA)); as.numeric(ct[term, c("Estimate","Std. Error","Pr(>|t|)")]) }

## ---- matched donor set per treatment date (pre-date audience+words means) ----
PAN0 <- build_panel(0L, 0L, 0)                    # baseline panel (identity, used for axis B + matching)
MU_by_date <- lapply(TREAT_DATES, function(td){
  covs <- PAN0[month < td, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
  covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
  mo <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
  unique(c(covs$unit[mo$index.treated], covs$unit[mo$index.control])) })
names(MU_by_date) <- as.character(TREAT_DATES)

## ---- outcomes: set, metric, conditional col, zero col, mention col ----------
OUT <- list(
  c("Russia","score","r_score","r_score0","n_ment_r"), c("Russia","pos","r_pos","r_pos0","n_ment_r"), c("Russia","net","r_net","r_net0","n_ment_r"),
  c("Ukraine","score","u_score","u_score0","n_ment_u"),c("Ukraine","pos","u_pos","u_pos0","n_ment_u"),c("Ukraine","net","u_net","u_net0","n_ment_u"),
  c("Combined","score","c_score","c_score0","n_ment_r"),c("Combined","pos","c_pos","c_pos0","n_ment_r"),c("Combined","net","c_net","c_net0","n_ment_r"),
  c("Russia","vol_pos","vol_pos_r","vol_pos_r","n_total"), c("Russia","vol_posneg","vol_posneg_r","vol_posneg_r","n_total"),
  c("Ukraine","vol_pos","vol_pos_u","vol_pos_u","n_total"),c("Ukraine","vol_posneg","vol_posneg_u","vol_posneg_u","n_total"),
  c("Combined","vol_pos","vol_pos_c","vol_pos_c","n_total"),c("Combined","vol_posneg","vol_posneg_c","vol_posneg_c","n_total"))

## ---- fit the full 10-spec set for one (panel, date, min_ment, coding, outcome) ----
fit_outcome <- function(pan, o, td, min_ment, coding, MU, do_scm) {
  set <- o[1]; metric <- o[2]; ycol <- if (coding == "zero" && !grepl("^vol", metric)) o[4] else o[3]; mc <- o[5]
  pan[, post := as.integer(month >= td)]; pan[, tp := tenet * post]
  if (coding == "zero" || grepl("^vol", metric))      base <- pan[n_total  >= min_ment & is.finite(get(ycol)) & is.finite(log_words)]
  else if (set == "Combined")                          base <- pan[n_ment_r >= min_ment & n_ment_u >= min_ment & is.finite(get(ycol)) & is.finite(log_words)]
  else if (set == "Russia")                            base <- pan[n_ment_r >= min_ment & is.finite(get(ycol)) & is.finite(log_words)]
  else                                                 base <- pan[n_ment_u >= min_ment & is.finite(get(ycol)) & is.finite(log_words)]
  pre <- base[post == 0]; preM <- pre[unit %in% MU]; baseM <- base[unit %in% MU]
  wcol <- if (grepl("^vol", metric)) "n_total" else if (set == "Ukraine") "n_ment_u" else "n_ment_r"
  f1s <- as.formula(paste(ycol, "~ tenet | mfac"));                          f1c <- as.formula(paste(ycol, "~ tenet + log_words + log_aud_m | mfac"))
  f2s <- as.formula(paste(ycol, "~ tp | unit+month"));                       f2c <- as.formula(paste(ycol, "~ tp + log_words + log_aud_m | unit+month"))
  ff  <- function(f, d) tryCatch(feols(f, d, cluster = ~ mfac + unit), error = function(e) NULL)   # H1: two-way month+unit
  fd  <- function(f, d) tryCatch(feols(f, d, cluster = ~ unit + month), error = function(e) NULL)  # H2: two-way unit+month
  rows <- list(); k <- 0L
  add <- function(spec, hyp, v) { k <<- k + 1L; rows[[k]] <<- data.table(set = set, metric = metric, hyp = hyp, spec = spec, est = v[1], se = v[2], p = v[3]) }
  add("simple",  "H1", gx(ff(f1s, pre),   "tenet")); add("simpleM", "H1", gx(ff(f1s, preM), "tenet"))
  add("ctrl",    "H1", gx(ff(f1c, pre),   "tenet")); add("ctrlM",   "H1", gx(ff(f1c, preM), "tenet"))
  add("twfe",    "H2", gx(fd(f2s, base),  "tp"));    add("twfe_ctrl",  "H2", gx(fd(f2c, base),  "tp"))
  add("twfeM",   "H2", gx(fd(f2s, baseM), "tp"));    add("twfeM_ctrl", "H2", gx(fd(f2c, baseM), "tp"))
  if (do_scm) {
    sc  <- scm(base, ycol, wcol, td)
    base[, yres := get(ycol) - tryCatch(predict(feols(as.formula(paste(ycol, "~ log_words | unit+month")), base), newdata = base), error = function(e) NA_real_)]
    scc <- scm(base, "yres", wcol, td)
    add("scm",      "H2", c(sc[1],  NA, sc[2])); add("scm_ctrl", "H2", c(scc[1], NA, scc[2]))
  } else { add("scm", "H2", c(NA,NA,NA)); add("scm_ctrl", "H2", c(NA,NA,NA)) }
  rbindlist(rows)
}

fit_cell <- function(pan, td, min_ment, coding, do_scm) {
  MU <- MU_by_date[[as.character(td)]]
  rbindlist(lapply(OUT, function(o) fit_outcome(pan, o, td, min_ment, coding, MU, do_scm)))
}

###############################################################################
## AXIS A -- probability mass-transfer (min_ment=5, conditional), all 3 dates
###############################################################################
gridA <- as.data.table(expand.grid(rus_op = 0:12, ukr_op = 0:12, shift = seq(0, 0.30, 0.025), KEEP.OUT.ATTRS = FALSE))
cat("AXIS A cells", nrow(gridA), "x dates", length(TREAT_DATES), "cores", NC, "\n")
runA <- function(i) {
  pan <- build_panel(gridA$rus_op[i], gridA$ukr_op[i], gridA$shift[i])
  res <- rbindlist(lapply(TREAT_DATES, function(td)
    cbind(axis = "probshift", rus_op = gridA$rus_op[i], ukr_op = gridA$ukr_op[i], shift = gridA$shift[i],
          min_ment = MINMENT_BASE, coding = "conditional", treat_date = as.character(td),
          fit_cell(pan, td, MINMENT_BASE, "conditional", SCM_IN_SHIFT))))
  rm(pan); gc(FALSE)
  cat(sprintf("[cellA %d/%d]\n", i, nrow(gridA)))
  res
}
resA <- rbindlist(mclapply(seq_len(nrow(gridA)), runA, mc.cores = NC, mc.preschedule = FALSE), fill = TRUE)
fwrite(resA, file.path(SC, "master_grid_axisA.csv"))         # checkpoint
cat("AXIS A rows", nrow(resA), "-> master_grid_axisA.csv (checkpoint)\n")

###############################################################################
## AXIS B/C -- min-mention {0,1,3,5,10,20} x coding {conditional,zero}, shift 0,
##             all 3 dates, full spec set incl. SCM. (folds in old 26.)
###############################################################################
gridB <- CJ(min_ment = MINMENT_GRID, coding = c("conditional", "zero"), td = TREAT_DATES, sorted = FALSE)
runB <- function(i) {
  res <- cbind(axis = "minment", rus_op = 0L, ukr_op = 0L, shift = 0,
               min_ment = gridB$min_ment[i], coding = gridB$coding[i], treat_date = as.character(gridB$td[i]),
               fit_cell(PAN0, gridB$td[i], gridB$min_ment[i], gridB$coding[i], TRUE))
  gc(FALSE); cat(sprintf("[cellB %d/%d]\n", i, nrow(gridB)))
  res
}
resB <- rbindlist(mclapply(seq_len(nrow(gridB)), runB, mc.cores = NC, mc.preschedule = FALSE), fill = TRUE)
fwrite(resB, file.path(SC, "master_grid_axisB.csv"))         # checkpoint
cat("AXIS B rows", nrow(resB), "-> master_grid_axisB.csv (checkpoint)\n")

###############################################################################
## combine + label + write
###############################################################################
fin <- rbind(resA, resB, fill = TRUE)
fin[, rus_op_name := OPNAME[rus_op + 1L]]; fin[, ukr_op_name := OPNAME[ukr_op + 1L]]
fin[, sig := fifelse(is.na(p), "NA", fifelse(p < 0.01, "***", fifelse(p < 0.05, "**", fifelse(p < 0.1, "*", "ns"))))]
setcolorder(fin, c("axis","treat_date","min_ment","coding","rus_op","rus_op_name","ukr_op","ukr_op_name","shift","set","metric","hyp","spec","est","se","p","sig"))
fwrite(fin, file.path(SC, "master_grid_h1h2.csv"))
cat("ROWS", nrow(fin), "-> master_grid_h1h2.csv  DONE_GRID\n")
