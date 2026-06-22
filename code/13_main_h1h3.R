###############################################################################
# 13_main_h1h3.R  --  MAIN H1/H2/H3 with EVERY model written out explicitly
# (no outcome for-loop, no per-outcome helper): each model is its own named object
# so you can inspect them one at a time, e.g. summary(h1_rs_ctrl), h2_rs_scm.
#
# Controls (the "ctrl" specs) = time-varying monthly audience (log_aud_m) + total
# words (log_words). "simple" specs have no controls.
#
# H1  pre-payment LEVEL, month FE, SE two-way clustered by month + unit. Per outcome:
#     <o>_simple   tenet | mfac                         (full)
#     <o>_simpleM  tenet | mfac                         (matched)
#     <o>_ctrl     tenet + log_words + log_aud_m | mfac (full)
#     <o>_ctrlM    tenet + log_words + log_aud_m | mfac (matched)
# H2  post-payment DiD, unit+month FE, SE two-way clustered by unit + month:
#     <o>_twfe / <o>_twfe_ctrl / <o>_twfeM / <o>_twfeM_ctrl
#     <o>_scm  (synthetic control)  /  <o>_scm_ctrl (SCM on outcome residualized on controls)
# H3  agenda proportion: same model set as H2 on prop_rus / prop_ukr / prop_comb.
#
# Outcomes: Russia/Ukraine/Combined x score/pos/net (H1,H2); R/U/Combined share (H3).
# Treatment 2023-10-01; window < 2024-09. Treated = tim_pool, benny, rubin. Seed 123.
# PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); SCM_WIN <- as.Date("2021-01-01")
MINMENT <- 5; MINTOT <- 10
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- panel + derived variables ----------------------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month - minm)/30.4375))]; P[, t2 := t^2]
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

## ---- Mahalanobis matching on time-varying audience + words (pre-payment means) ----
covs <- P[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

## ---- synthetic-control helper (called explicitly per outcome) ----------------
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); D <- t(Y0p) %*% Y0p + diag(1e-8, n); dv <- as.vector(t(Y0p) %*% y1p)
  A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n)); tryCatch(solve.QP(D, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(pan, col, wcol){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]; mo <- sort(comp$month); pre <- mo < TREAT  # treated-observed months
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp$y[match(mo, comp$month)]
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]; dm <- as.matrix(don[, -1])
  for (j in seq_len(ncol(dm))){ v <- dm[, j]; if (anyNA(v)) { v[is.na(v)] <- mean(v, na.rm = TRUE); dm[, j] <- v } }   # gap-fill donors w/ own mean
  good <- which(apply(dm, 2, function(x) all(is.finite(x)) & sd(x) > 0)); if (length(good) < 5 || anyNA(y1)) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre); rs <- c()
  for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }

## small extractors for the summary tables (the MODELS below are all explicit) ----
gx  <- function(m, term){ ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA)); round(as.numeric(ct[term, c("Estimate", "Pr(>|t|)")]), 4) }
r1  <- function(lbl, a, b, c, d) data.table(outcome = lbl,
        est_simple = gx(a,"tenet")[1], p_simple = gx(a,"tenet")[2], est_simpleM = gx(b,"tenet")[1], p_simpleM = gx(b,"tenet")[2],
        est_ctrl = gx(c,"tenet")[1], p_ctrl = gx(c,"tenet")[2], est_ctrlM = gx(d,"tenet")[1], p_ctrlM = gx(d,"tenet")[2])
r2  <- function(lbl, tw, twc, twm, twmc, sc, scc) data.table(outcome = lbl,
        est_twfe = gx(tw,"tp")[1], p_twfe = gx(tw,"tp")[2], est_twfe_ctrl = gx(twc,"tp")[1], p_twfe_ctrl = gx(twc,"tp")[2],
        est_twfeM = gx(twm,"tp")[1], p_twfeM = gx(twm,"tp")[2], est_twfeM_ctrl = gx(twmc,"tp")[1], p_twfeM_ctrl = gx(twmc,"tp")[2],
        est_scm = round(sc[1],4), p_scm = round(sc[2],4), est_scm_ctrl = round(scc[1],4), p_scm_ctrl = round(scc[2],4))

###############################################################################
## H1 -- pre-payment LEVEL.  month FE | mfac ; two-way cluster (month + unit)
###############################################################################
# ---- Russia score ----
d_rs <- P[month<TREAT & n_ment_r>=MINMENT & is.finite(r_score) & is.finite(log_words)]; dm_rs <- d_rs[unit %in% matched_units]
h1_rs_simple  <- feols(r_score ~ tenet | mfac, d_rs,  cluster=~mfac+unit)
h1_rs_simpleM <- feols(r_score ~ tenet | mfac, dm_rs, cluster=~mfac+unit)
h1_rs_ctrl    <- feols(r_score ~ tenet + log_words + log_aud_m | mfac, d_rs,  cluster=~mfac+unit)
h1_rs_ctrlM   <- feols(r_score ~ tenet + log_words + log_aud_m | mfac, dm_rs, cluster=~mfac+unit)
# ---- Russia pos ----
d_rp <- P[month<TREAT & n_ment_r>=MINMENT & is.finite(r_pos) & is.finite(log_words)]; dm_rp <- d_rp[unit %in% matched_units]
h1_rp_simple  <- feols(r_pos ~ tenet | mfac, d_rp,  cluster=~mfac+unit)
h1_rp_simpleM <- feols(r_pos ~ tenet | mfac, dm_rp, cluster=~mfac+unit)
h1_rp_ctrl    <- feols(r_pos ~ tenet + log_words + log_aud_m | mfac, d_rp,  cluster=~mfac+unit)
h1_rp_ctrlM   <- feols(r_pos ~ tenet + log_words + log_aud_m | mfac, dm_rp, cluster=~mfac+unit)
# ---- Russia net ----
d_rn <- P[month<TREAT & n_ment_r>=MINMENT & is.finite(r_net) & is.finite(log_words)]; dm_rn <- d_rn[unit %in% matched_units]
h1_rn_simple  <- feols(r_net ~ tenet | mfac, d_rn,  cluster=~mfac+unit)
h1_rn_simpleM <- feols(r_net ~ tenet | mfac, dm_rn, cluster=~mfac+unit)
h1_rn_ctrl    <- feols(r_net ~ tenet + log_words + log_aud_m | mfac, d_rn,  cluster=~mfac+unit)
h1_rn_ctrlM   <- feols(r_net ~ tenet + log_words + log_aud_m | mfac, dm_rn, cluster=~mfac+unit)
# ---- Ukraine score ----
d_us <- P[month<TREAT & n_ment_u>=MINMENT & is.finite(u_score) & is.finite(log_words)]; dm_us <- d_us[unit %in% matched_units]
h1_us_simple  <- feols(u_score ~ tenet | mfac, d_us,  cluster=~mfac+unit)
h1_us_simpleM <- feols(u_score ~ tenet | mfac, dm_us, cluster=~mfac+unit)
h1_us_ctrl    <- feols(u_score ~ tenet + log_words + log_aud_m | mfac, d_us,  cluster=~mfac+unit)
h1_us_ctrlM   <- feols(u_score ~ tenet + log_words + log_aud_m | mfac, dm_us, cluster=~mfac+unit)
# ---- Ukraine pos ----
d_up <- P[month<TREAT & n_ment_u>=MINMENT & is.finite(u_pos) & is.finite(log_words)]; dm_up <- d_up[unit %in% matched_units]
h1_up_simple  <- feols(u_pos ~ tenet | mfac, d_up,  cluster=~mfac+unit)
h1_up_simpleM <- feols(u_pos ~ tenet | mfac, dm_up, cluster=~mfac+unit)
h1_up_ctrl    <- feols(u_pos ~ tenet + log_words + log_aud_m | mfac, d_up,  cluster=~mfac+unit)
h1_up_ctrlM   <- feols(u_pos ~ tenet + log_words + log_aud_m | mfac, dm_up, cluster=~mfac+unit)
# ---- Ukraine net ----
d_un <- P[month<TREAT & n_ment_u>=MINMENT & is.finite(u_net) & is.finite(log_words)]; dm_un <- d_un[unit %in% matched_units]
h1_un_simple  <- feols(u_net ~ tenet | mfac, d_un,  cluster=~mfac+unit)
h1_un_simpleM <- feols(u_net ~ tenet | mfac, dm_un, cluster=~mfac+unit)
h1_un_ctrl    <- feols(u_net ~ tenet + log_words + log_aud_m | mfac, d_un,  cluster=~mfac+unit)
h1_un_ctrlM   <- feols(u_net ~ tenet + log_words + log_aud_m | mfac, dm_un, cluster=~mfac+unit)
# ---- Combined score (require both targets mentioned) ----
d_cs <- P[month<TREAT & n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_score) & is.finite(log_words)]; dm_cs <- d_cs[unit %in% matched_units]
h1_cs_simple  <- feols(c_score ~ tenet | mfac, d_cs,  cluster=~mfac+unit)
h1_cs_simpleM <- feols(c_score ~ tenet | mfac, dm_cs, cluster=~mfac+unit)
h1_cs_ctrl    <- feols(c_score ~ tenet + log_words + log_aud_m | mfac, d_cs,  cluster=~mfac+unit)
h1_cs_ctrlM   <- feols(c_score ~ tenet + log_words + log_aud_m | mfac, dm_cs, cluster=~mfac+unit)
# ---- Combined pos ----
d_cp <- P[month<TREAT & n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_pos) & is.finite(log_words)]; dm_cp <- d_cp[unit %in% matched_units]
h1_cp_simple  <- feols(c_pos ~ tenet | mfac, d_cp,  cluster=~mfac+unit)
h1_cp_simpleM <- feols(c_pos ~ tenet | mfac, dm_cp, cluster=~mfac+unit)
h1_cp_ctrl    <- feols(c_pos ~ tenet + log_words + log_aud_m | mfac, d_cp,  cluster=~mfac+unit)
h1_cp_ctrlM   <- feols(c_pos ~ tenet + log_words + log_aud_m | mfac, dm_cp, cluster=~mfac+unit)
# ---- Combined net ----
d_cn <- P[month<TREAT & n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_net) & is.finite(log_words)]; dm_cn <- d_cn[unit %in% matched_units]
h1_cn_simple  <- feols(c_net ~ tenet | mfac, d_cn,  cluster=~mfac+unit)
h1_cn_simpleM <- feols(c_net ~ tenet | mfac, dm_cn, cluster=~mfac+unit)
h1_cn_ctrl    <- feols(c_net ~ tenet + log_words + log_aud_m | mfac, d_cn,  cluster=~mfac+unit)
h1_cn_ctrlM   <- feols(c_net ~ tenet + log_words + log_aud_m | mfac, dm_cn, cluster=~mfac+unit)

H1 <- rbindlist(list(
  r1("Russia score",   h1_rs_simple, h1_rs_simpleM, h1_rs_ctrl, h1_rs_ctrlM),
  r1("Russia pos",     h1_rp_simple, h1_rp_simpleM, h1_rp_ctrl, h1_rp_ctrlM),
  r1("Russia net",     h1_rn_simple, h1_rn_simpleM, h1_rn_ctrl, h1_rn_ctrlM),
  r1("Ukraine score",  h1_us_simple, h1_us_simpleM, h1_us_ctrl, h1_us_ctrlM),
  r1("Ukraine pos",    h1_up_simple, h1_up_simpleM, h1_up_ctrl, h1_up_ctrlM),
  r1("Ukraine net",    h1_un_simple, h1_un_simpleM, h1_un_ctrl, h1_un_ctrlM),
  r1("Combined score", h1_cs_simple, h1_cs_simpleM, h1_cs_ctrl, h1_cs_ctrlM),
  r1("Combined pos",   h1_cp_simple, h1_cp_simpleM, h1_cp_ctrl, h1_cp_ctrlM),
  r1("Combined net",   h1_cn_simple, h1_cn_simpleM, h1_cn_ctrl, h1_cn_ctrlM)))

###############################################################################
## H2 -- post-payment DiD.  | unit + month ; two-way cluster (unit + month)
##   twfe / twfe_ctrl / twfeM / twfeM_ctrl ; scm / scm_ctrl (residualized outcome)
###############################################################################
# ---- Russia score ----
e_rs <- P[n_ment_r>=MINMENT & is.finite(r_score) & is.finite(log_words)]; em_rs <- e_rs[unit %in% matched_units]
h2_rs_twfe       <- feols(r_score ~ tp | unit+month, e_rs,  cluster=~unit+month)
h2_rs_twfe_ctrl  <- feols(r_score ~ tp + log_words + log_aud_m | unit+month, e_rs,  cluster=~unit+month)
h2_rs_twfeM      <- feols(r_score ~ tp | unit+month, em_rs, cluster=~unit+month)
h2_rs_twfeM_ctrl <- feols(r_score ~ tp + log_words + log_aud_m | unit+month, em_rs, cluster=~unit+month)
e_rs[, r_score_res := r_score - predict(feols(r_score ~ log_words | unit+month,e_rs), newdata=e_rs)]
h2_rs_scm      <- scm(e_rs, "r_score",     "n_ment_r")
h2_rs_scm_ctrl <- scm(e_rs, "r_score_res", "n_ment_r")
# ---- Russia pos ----
e_rp <- P[n_ment_r>=MINMENT & is.finite(r_pos) & is.finite(log_words)]; em_rp <- e_rp[unit %in% matched_units]
h2_rp_twfe       <- feols(r_pos ~ tp | unit+month, e_rp,  cluster=~unit+month)
h2_rp_twfe_ctrl  <- feols(r_pos ~ tp + log_words + log_aud_m | unit+month, e_rp,  cluster=~unit+month)
h2_rp_twfeM      <- feols(r_pos ~ tp | unit+month, em_rp, cluster=~unit+month)
h2_rp_twfeM_ctrl <- feols(r_pos ~ tp + log_words + log_aud_m | unit+month, em_rp, cluster=~unit+month)
e_rp[, r_pos_res := r_pos - predict(feols(r_pos ~ log_words | unit+month,e_rp), newdata=e_rp)]
h2_rp_scm      <- scm(e_rp, "r_pos",     "n_ment_r")
h2_rp_scm_ctrl <- scm(e_rp, "r_pos_res", "n_ment_r")
# ---- Russia net ----
e_rn <- P[n_ment_r>=MINMENT & is.finite(r_net) & is.finite(log_words)]; em_rn <- e_rn[unit %in% matched_units]
h2_rn_twfe       <- feols(r_net ~ tp | unit+month, e_rn,  cluster=~unit+month)
h2_rn_twfe_ctrl  <- feols(r_net ~ tp + log_words + log_aud_m | unit+month, e_rn,  cluster=~unit+month)
h2_rn_twfeM      <- feols(r_net ~ tp | unit+month, em_rn, cluster=~unit+month)
h2_rn_twfeM_ctrl <- feols(r_net ~ tp + log_words + log_aud_m | unit+month, em_rn, cluster=~unit+month)
e_rn[, r_net_res := r_net - predict(feols(r_net ~ log_words | unit+month,e_rn), newdata=e_rn)]
h2_rn_scm      <- scm(e_rn, "r_net",     "n_ment_r")
h2_rn_scm_ctrl <- scm(e_rn, "r_net_res", "n_ment_r")
# ---- Ukraine score ----
e_us <- P[n_ment_u>=MINMENT & is.finite(u_score) & is.finite(log_words)]; em_us <- e_us[unit %in% matched_units]
h2_us_twfe       <- feols(u_score ~ tp | unit+month, e_us,  cluster=~unit+month)
h2_us_twfe_ctrl  <- feols(u_score ~ tp + log_words + log_aud_m | unit+month, e_us,  cluster=~unit+month)
h2_us_twfeM      <- feols(u_score ~ tp | unit+month, em_us, cluster=~unit+month)
h2_us_twfeM_ctrl <- feols(u_score ~ tp + log_words + log_aud_m | unit+month, em_us, cluster=~unit+month)
e_us[, u_score_res := u_score - predict(feols(u_score ~ log_words | unit+month,e_us), newdata=e_us)]
h2_us_scm      <- scm(e_us, "u_score",     "n_ment_u")
h2_us_scm_ctrl <- scm(e_us, "u_score_res", "n_ment_u")
# ---- Ukraine pos ----
e_up <- P[n_ment_u>=MINMENT & is.finite(u_pos) & is.finite(log_words)]; em_up <- e_up[unit %in% matched_units]
h2_up_twfe       <- feols(u_pos ~ tp | unit+month, e_up,  cluster=~unit+month)
h2_up_twfe_ctrl  <- feols(u_pos ~ tp + log_words + log_aud_m | unit+month, e_up,  cluster=~unit+month)
h2_up_twfeM      <- feols(u_pos ~ tp | unit+month, em_up, cluster=~unit+month)
h2_up_twfeM_ctrl <- feols(u_pos ~ tp + log_words + log_aud_m | unit+month, em_up, cluster=~unit+month)
e_up[, u_pos_res := u_pos - predict(feols(u_pos ~ log_words | unit+month,e_up), newdata=e_up)]
h2_up_scm      <- scm(e_up, "u_pos",     "n_ment_u")
h2_up_scm_ctrl <- scm(e_up, "u_pos_res", "n_ment_u")
# ---- Ukraine net ----
e_un <- P[n_ment_u>=MINMENT & is.finite(u_net) & is.finite(log_words)]; em_un <- e_un[unit %in% matched_units]
h2_un_twfe       <- feols(u_net ~ tp | unit+month, e_un,  cluster=~unit+month)
h2_un_twfe_ctrl  <- feols(u_net ~ tp + log_words + log_aud_m | unit+month, e_un,  cluster=~unit+month)
h2_un_twfeM      <- feols(u_net ~ tp | unit+month, em_un, cluster=~unit+month)
h2_un_twfeM_ctrl <- feols(u_net ~ tp + log_words + log_aud_m | unit+month, em_un, cluster=~unit+month)
e_un[, u_net_res := u_net - predict(feols(u_net ~ log_words | unit+month,e_un), newdata=e_un)]
h2_un_scm      <- scm(e_un, "u_net",     "n_ment_u")
h2_un_scm_ctrl <- scm(e_un, "u_net_res", "n_ment_u")
# ---- Combined score ----
e_cs <- P[n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_score) & is.finite(log_words)]; em_cs <- e_cs[unit %in% matched_units]
h2_cs_twfe       <- feols(c_score ~ tp | unit+month, e_cs,  cluster=~unit+month)
h2_cs_twfe_ctrl  <- feols(c_score ~ tp + log_words + log_aud_m | unit+month, e_cs,  cluster=~unit+month)
h2_cs_twfeM      <- feols(c_score ~ tp | unit+month, em_cs, cluster=~unit+month)
h2_cs_twfeM_ctrl <- feols(c_score ~ tp + log_words + log_aud_m | unit+month, em_cs, cluster=~unit+month)
e_cs[, c_score_res := c_score - predict(feols(c_score ~ log_words | unit+month,e_cs), newdata=e_cs)]
h2_cs_scm      <- scm(e_cs, "c_score",     "n_ment_r")
h2_cs_scm_ctrl <- scm(e_cs, "c_score_res", "n_ment_r")
# ---- Combined pos ----
e_cp <- P[n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_pos) & is.finite(log_words)]; em_cp <- e_cp[unit %in% matched_units]
h2_cp_twfe       <- feols(c_pos ~ tp | unit+month, e_cp,  cluster=~unit+month)
h2_cp_twfe_ctrl  <- feols(c_pos ~ tp + log_words + log_aud_m | unit+month, e_cp,  cluster=~unit+month)
h2_cp_twfeM      <- feols(c_pos ~ tp | unit+month, em_cp, cluster=~unit+month)
h2_cp_twfeM_ctrl <- feols(c_pos ~ tp + log_words + log_aud_m | unit+month, em_cp, cluster=~unit+month)
e_cp[, c_pos_res := c_pos - predict(feols(c_pos ~ log_words | unit+month,e_cp), newdata=e_cp)]
h2_cp_scm      <- scm(e_cp, "c_pos",     "n_ment_r")
h2_cp_scm_ctrl <- scm(e_cp, "c_pos_res", "n_ment_r")
# ---- Combined net ----
e_cn <- P[n_ment_r>=MINMENT & n_ment_u>=MINMENT & is.finite(c_net) & is.finite(log_words)]; em_cn <- e_cn[unit %in% matched_units]
h2_cn_twfe       <- feols(c_net ~ tp | unit+month, e_cn,  cluster=~unit+month)
h2_cn_twfe_ctrl  <- feols(c_net ~ tp + log_words + log_aud_m | unit+month, e_cn,  cluster=~unit+month)
h2_cn_twfeM      <- feols(c_net ~ tp | unit+month, em_cn, cluster=~unit+month)
h2_cn_twfeM_ctrl <- feols(c_net ~ tp + log_words + log_aud_m | unit+month, em_cn, cluster=~unit+month)
e_cn[, c_net_res := c_net - predict(feols(c_net ~ log_words | unit+month,e_cn), newdata=e_cn)]
h2_cn_scm      <- scm(e_cn, "c_net",     "n_ment_r")
h2_cn_scm_ctrl <- scm(e_cn, "c_net_res", "n_ment_r")

H2 <- rbindlist(list(
  r2("Russia score",   h2_rs_twfe, h2_rs_twfe_ctrl, h2_rs_twfeM, h2_rs_twfeM_ctrl, h2_rs_scm, h2_rs_scm_ctrl),
  r2("Russia pos",     h2_rp_twfe, h2_rp_twfe_ctrl, h2_rp_twfeM, h2_rp_twfeM_ctrl, h2_rp_scm, h2_rp_scm_ctrl),
  r2("Russia net",     h2_rn_twfe, h2_rn_twfe_ctrl, h2_rn_twfeM, h2_rn_twfeM_ctrl, h2_rn_scm, h2_rn_scm_ctrl),
  r2("Ukraine score",  h2_us_twfe, h2_us_twfe_ctrl, h2_us_twfeM, h2_us_twfeM_ctrl, h2_us_scm, h2_us_scm_ctrl),
  r2("Ukraine pos",    h2_up_twfe, h2_up_twfe_ctrl, h2_up_twfeM, h2_up_twfeM_ctrl, h2_up_scm, h2_up_scm_ctrl),
  r2("Ukraine net",    h2_un_twfe, h2_un_twfe_ctrl, h2_un_twfeM, h2_un_twfeM_ctrl, h2_un_scm, h2_un_scm_ctrl),
  r2("Combined score", h2_cs_twfe, h2_cs_twfe_ctrl, h2_cs_twfeM, h2_cs_twfeM_ctrl, h2_cs_scm, h2_cs_scm_ctrl),
  r2("Combined pos",   h2_cp_twfe, h2_cp_twfe_ctrl, h2_cp_twfeM, h2_cp_twfeM_ctrl, h2_cp_scm, h2_cp_scm_ctrl),
  r2("Combined net",   h2_cn_twfe, h2_cn_twfe_ctrl, h2_cn_twfeM, h2_cn_twfeM_ctrl, h2_cn_scm, h2_cn_scm_ctrl)))

###############################################################################
## H3 -- agenda PROPORTION DiD.  same model set as H2 on prop_rus/ukr/comb
###############################################################################
# ---- Russia share ----
f_rus <- P[n_words>=MINTOT & is.finite(prop_rus) & is.finite(log_words)]; fm_rus <- f_rus[unit %in% matched_units]
h3_rus_twfe       <- feols(prop_rus ~ tp | unit+month, f_rus,  cluster=~unit+month)
h3_rus_twfe_ctrl  <- feols(prop_rus ~ tp + log_words + log_aud_m | unit+month, f_rus,  cluster=~unit+month)
h3_rus_twfeM      <- feols(prop_rus ~ tp | unit+month, fm_rus, cluster=~unit+month)
h3_rus_twfeM_ctrl <- feols(prop_rus ~ tp + log_words + log_aud_m | unit+month, fm_rus, cluster=~unit+month)
f_rus[, prop_rus_res := prop_rus - predict(feols(prop_rus ~ log_words | unit+month,f_rus), newdata=f_rus)]
h3_rus_scm      <- scm(f_rus, "prop_rus",     "n_words")
h3_rus_scm_ctrl <- scm(f_rus, "prop_rus_res", "n_words")
# ---- Ukraine share ----
f_ukr <- P[n_words>=MINTOT & is.finite(prop_ukr) & is.finite(log_words)]; fm_ukr <- f_ukr[unit %in% matched_units]
h3_ukr_twfe       <- feols(prop_ukr ~ tp | unit+month, f_ukr,  cluster=~unit+month)
h3_ukr_twfe_ctrl  <- feols(prop_ukr ~ tp + log_words + log_aud_m | unit+month, f_ukr,  cluster=~unit+month)
h3_ukr_twfeM      <- feols(prop_ukr ~ tp | unit+month, fm_ukr, cluster=~unit+month)
h3_ukr_twfeM_ctrl <- feols(prop_ukr ~ tp + log_words + log_aud_m | unit+month, fm_ukr, cluster=~unit+month)
f_ukr[, prop_ukr_res := prop_ukr - predict(feols(prop_ukr ~ log_words | unit+month,f_ukr), newdata=f_ukr)]
h3_ukr_scm      <- scm(f_ukr, "prop_ukr",     "n_words")
h3_ukr_scm_ctrl <- scm(f_ukr, "prop_ukr_res", "n_words")
# ---- Combined share ----
f_comb <- P[n_words>=MINTOT & is.finite(prop_comb) & is.finite(log_words)]; fm_comb <- f_comb[unit %in% matched_units]
h3_comb_twfe       <- feols(prop_comb ~ tp | unit+month, f_comb,  cluster=~unit+month)
h3_comb_twfe_ctrl  <- feols(prop_comb ~ tp + log_words + log_aud_m | unit+month, f_comb,  cluster=~unit+month)
h3_comb_twfeM      <- feols(prop_comb ~ tp | unit+month, fm_comb, cluster=~unit+month)
h3_comb_twfeM_ctrl <- feols(prop_comb ~ tp + log_words + log_aud_m | unit+month, fm_comb, cluster=~unit+month)
f_comb[, prop_comb_res := prop_comb - predict(feols(prop_comb ~ log_words | unit+month,f_comb), newdata=f_comb)]
h3_comb_scm      <- scm(f_comb, "prop_comb",     "n_words")
h3_comb_scm_ctrl <- scm(f_comb, "prop_comb_res", "n_words")

H3 <- rbindlist(list(
  r2("Russia share",   h3_rus_twfe,  h3_rus_twfe_ctrl,  h3_rus_twfeM,  h3_rus_twfeM_ctrl,  h3_rus_scm,  h3_rus_scm_ctrl),
  r2("Ukraine share",  h3_ukr_twfe,  h3_ukr_twfe_ctrl,  h3_ukr_twfeM,  h3_ukr_twfeM_ctrl,  h3_ukr_scm,  h3_ukr_scm_ctrl),
  r2("Combined share", h3_comb_twfe, h3_comb_twfe_ctrl, h3_comb_twfeM, h3_comb_twfeM_ctrl, h3_comb_scm, h3_comb_scm_ctrl)))

###############################################################################
## RANDOMIZATION INFERENCE -- DISABLED (kept for reviewers only).
## The 3-treated-cluster permutation null is very wide (only C(n,3) reassignments,
## so the RI p's run ~0.24-0.70 even where the analytic clustered p < 0.01). We do
## NOT report it as the inference; clustered SEs are the headline. To re-enable for
## a revision, uncomment the block below -- it appends p_RI_ctrl to H1/H2/H3.
###############################################################################
# RI_B <- 999
# ri_lvl <- function(d, ycol){ d <- copy(d); u <- unique(d$unit); nt <- length(intersect(u, TRU))
#   f <- as.formula(paste0(ycol, " ~ tnt + log_words + log_aud_m | mfac"))
#   d[, tnt := as.integer(unit %in% TRU)]; real <- coef(feols(f, d))["tnt"]
#   bs <- replicate(RI_B, { d[, tnt := as.integer(unit %in% sample(u, nt))]; tryCatch(coef(feols(f, d))["tnt"], error = function(e) NA_real_) })
#   round((1 + sum(abs(bs) >= abs(real), na.rm = TRUE)) / (1 + sum(is.finite(bs))), 4) }
# ri_did <- function(d, ycol){ d <- copy(d); u <- unique(d$unit); nt <- length(intersect(u, TRU))
#   f <- as.formula(paste0(ycol, " ~ tnp + log_words + log_aud_m | unit+month"))
#   d[, tnp := as.integer(unit %in% TRU) * post]; real <- coef(feols(f, d))["tnp"]
#   bs <- replicate(RI_B, { d[, tnp := as.integer(unit %in% sample(u, nt)) * post]; tryCatch(coef(feols(f, d))["tnp"], error = function(e) NA_real_) })
#   round((1 + sum(abs(bs) >= abs(real), na.rm = TRUE)) / (1 + sum(is.finite(bs))), 4) }
# H1[, p_RI_ctrl := c(ri_lvl(d_rs,"r_score"), ri_lvl(d_rp,"r_pos"), ri_lvl(d_rn,"r_net"),
#                     ri_lvl(d_us,"u_score"), ri_lvl(d_up,"u_pos"), ri_lvl(d_un,"u_net"),
#                     ri_lvl(d_cs,"c_score"), ri_lvl(d_cp,"c_pos"), ri_lvl(d_cn,"c_net"))]
# H2[, p_RI_ctrl := c(ri_did(e_rs,"r_score"), ri_did(e_rp,"r_pos"), ri_did(e_rn,"r_net"),
#                     ri_did(e_us,"u_score"), ri_did(e_up,"u_pos"), ri_did(e_un,"u_net"),
#                     ri_did(e_cs,"c_score"), ri_did(e_cp,"c_pos"), ri_did(e_cn,"c_net"))]
# H3[, p_RI_ctrl := c(ri_did(f_rus,"prop_rus"), ri_did(f_ukr,"prop_ukr"), ri_did(f_comb,"prop_comb"))]

## ---- show & save ------------------------------------------------------------
cat("\n===== H1 (pre-payment level) =====\n"); print(H1)
cat("\n===== H2 (post-payment stance DiD) =====\n"); print(H2)
cat("\n===== H3 (agenda proportion DiD) =====\n"); print(H3)
fwrite(H1, file.path(SC, "main_h1.csv")); fwrite(H2, file.path(SC, "main_h2.csv")); fwrite(H3, file.path(SC, "main_h3.csv"))

## ---- SAVE every fitted model + the summary tables + panel --------------------
## load(file.path(SC, "main_h1h3_models.RData")) later to reuse any h1_*/h2_*/h3_* object.
mods_h1 <- mget(ls(pattern = "^h1_"))      # 9 outcomes x 4 specs
mods_h2 <- mget(ls(pattern = "^h2_"))      # 9 outcomes x (4 feols + 2 scm vectors)
mods_h3 <- mget(ls(pattern = "^h3_"))      # 3 outcomes x (4 feols + 2 scm vectors)
saveRDS(list(H1 = H1, H2 = H2, H3 = H3, models = c(mods_h1, mods_h2, mods_h3)),
        file.path(SC, "main_h1h3_models.rds"))
save.image(file = file.path(SC, "main_h1h3_models.RData"))
cat("\nSaved", length(mods_h1) + length(mods_h2) + length(mods_h3),
    "model objects + tables -> main_h1h3_models.{rds,RData}\n")
