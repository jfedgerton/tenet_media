###############################################################################
# 15_main_h4.R  --  MAIN H4 (agenda divergence) with EVERY model written out
# explicitly (no loop, no helper-per-measure): each model is its own named object.
#
# Divergence panel from 14_h4_topic_model.py; MAIN spec rows only:
#   topicset = all, reference = contemp, rare = rare. One row per unit-month.
# Measures: jsd (headline), kl_sm, cosine.
# Controls ("ctrl" specs) = time-varying monthly audience (log_aud_m) + total words
# (log_words). "simple" specs have no controls.
#
# H4a  pre-payment LEVEL (treated already more divergent): month FE | mfac, SE two-way
#      clustered by month + unit.   <m>_simple / _simpleM / _ctrl / _ctrlM
# H4b  post-payment DiD (treated diverge MORE after payment): unit+month FE, SE two-way
#      clustered by unit + month.   <m>_twfe / _twfe_ctrl / _twfeM / _twfeM_ctrl
#                                    <m>_scm / _scm_ctrl (SCM on control-residualized outcome)
# Treatment 2023-10-01. Treated = tim_pool, benny, rubin. Seed 123. PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); SCM_WIN <- as.Date("2021-01-01")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- divergence panel (MAIN spec only) + controls ---------------------------
D <- fread(file.path(SC, "h4_divergence_panel.csv"))
D <- D[topicset == "all" & reference == "contemp" & rare == "rare"]
D[, month := as.Date(month)]; D[, mfac := factor(month)]; D[, tenet := as.integer(unit %in% TRU)]
D[, post := as.integer(month >= TREAT)]; D[, tp := tenet * post]; D[, log_n := log(n_sentences)]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
D <- merge(D, Vunit, by = c("unit", "month"), all.x = TRUE); D[, log_words := log(n_words)]
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
D <- merge(D, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); D[, log_aud_m := log(aud_mid)]

## ---- matching on time-varying audience + words (pre-payment means) ----------
covs <- D[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

## ---- SCM helper (weights by n_sentences) ; extractors for the tables ---------
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); M <- t(Y0p) %*% Y0p + diag(1e-8, n); dv <- as.vector(t(Y0p) %*% y1p)
  A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n)); tryCatch(solve.QP(M, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(pan, col){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(n_sentences, 1))), by = month]; mo <- sort(unique(dd$month)); pre <- mo < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp[match(mo, comp$month)]$y
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]; dm <- as.matrix(don[, -1])
  good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0); if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre); rs <- c()
  for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }
gx <- function(m, term){ ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA)); round(as.numeric(ct[term, c("Estimate", "Pr(>|t|)")]), 4) }
r1 <- function(lbl, a, b, c, d) data.table(measure = lbl,
        est_simple = gx(a,"tenet")[1], p_simple = gx(a,"tenet")[2], est_simpleM = gx(b,"tenet")[1], p_simpleM = gx(b,"tenet")[2],
        est_ctrl = gx(c,"tenet")[1], p_ctrl = gx(c,"tenet")[2], est_ctrlM = gx(d,"tenet")[1], p_ctrlM = gx(d,"tenet")[2])
r2 <- function(lbl, tw, twc, twm, twmc, sc, scc) data.table(measure = lbl,
        est_twfe = gx(tw,"tp")[1], p_twfe = gx(tw,"tp")[2], est_twfe_ctrl = gx(twc,"tp")[1], p_twfe_ctrl = gx(twc,"tp")[2],
        est_twfeM = gx(twm,"tp")[1], p_twfeM = gx(twm,"tp")[2], est_twfeM_ctrl = gx(twmc,"tp")[1], p_twfeM_ctrl = gx(twmc,"tp")[2],
        est_scm = round(sc[1],4), p_scm = round(sc[2],4), est_scm_ctrl = round(scc[1],4), p_scm_ctrl = round(scc[2],4))

###############################################################################
## H4a -- pre-payment LEVEL.  month FE | mfac ; two-way cluster (month + unit)
###############################################################################
# ---- JSD ----
a_j <- D[month<TREAT & is.finite(jsd) & is.finite(log_words)]; am_j <- a_j[unit %in% matched_units]
h4a_jsd_simple  <- feols(jsd ~ tenet | mfac, a_j,  cluster=~mfac+unit)
h4a_jsd_simpleM <- feols(jsd ~ tenet | mfac, am_j, cluster=~mfac+unit)
h4a_jsd_ctrl    <- feols(jsd ~ tenet + log_words + log_aud_m | mfac, a_j,  cluster=~mfac+unit)
h4a_jsd_ctrlM   <- feols(jsd ~ tenet + log_words + log_aud_m | mfac, am_j, cluster=~mfac+unit)
# ---- KL ----
a_k <- D[month<TREAT & is.finite(kl_sm) & is.finite(log_words)]; am_k <- a_k[unit %in% matched_units]
h4a_kl_simple  <- feols(kl_sm ~ tenet | mfac, a_k,  cluster=~mfac+unit)
h4a_kl_simpleM <- feols(kl_sm ~ tenet | mfac, am_k, cluster=~mfac+unit)
h4a_kl_ctrl    <- feols(kl_sm ~ tenet + log_words + log_aud_m | mfac, a_k,  cluster=~mfac+unit)
h4a_kl_ctrlM   <- feols(kl_sm ~ tenet + log_words + log_aud_m | mfac, am_k, cluster=~mfac+unit)
# ---- cosine ----
a_c <- D[month<TREAT & is.finite(cosine) & is.finite(log_words)]; am_c <- a_c[unit %in% matched_units]
h4a_cos_simple  <- feols(cosine ~ tenet | mfac, a_c,  cluster=~mfac+unit)
h4a_cos_simpleM <- feols(cosine ~ tenet | mfac, am_c, cluster=~mfac+unit)
h4a_cos_ctrl    <- feols(cosine ~ tenet + log_words + log_aud_m | mfac, a_c,  cluster=~mfac+unit)
h4a_cos_ctrlM   <- feols(cosine ~ tenet + log_words + log_aud_m | mfac, am_c, cluster=~mfac+unit)

H4a <- rbindlist(list(
  r1("JSD",    h4a_jsd_simple, h4a_jsd_simpleM, h4a_jsd_ctrl, h4a_jsd_ctrlM),
  r1("KL",     h4a_kl_simple,  h4a_kl_simpleM,  h4a_kl_ctrl,  h4a_kl_ctrlM),
  r1("cosine", h4a_cos_simple, h4a_cos_simpleM, h4a_cos_ctrl, h4a_cos_ctrlM)))

###############################################################################
## H4b -- post-payment DiD.  | unit + month ; two-way cluster (unit + month)
###############################################################################
# ---- JSD ----
b_j <- D[is.finite(jsd) & is.finite(log_words)]; bm_j <- b_j[unit %in% matched_units]
h4b_jsd_twfe       <- feols(jsd ~ tp | unit+month, b_j,  cluster=~unit+month)
h4b_jsd_twfe_ctrl  <- feols(jsd ~ tp + log_words + log_aud_m | unit+month, b_j,  cluster=~unit+month)
h4b_jsd_twfeM      <- feols(jsd ~ tp | unit+month, bm_j, cluster=~unit+month)
h4b_jsd_twfeM_ctrl <- feols(jsd ~ tp + log_words + log_aud_m | unit+month, bm_j, cluster=~unit+month)
b_j[, jsd_res := jsd - predict(feols(jsd ~ log_words + log_aud_m | unit+month, b_j), newdata=b_j)]
h4b_jsd_scm      <- scm(b_j, "jsd")
h4b_jsd_scm_ctrl <- scm(b_j, "jsd_res")
# ---- KL ----
b_k <- D[is.finite(kl_sm) & is.finite(log_words)]; bm_k <- b_k[unit %in% matched_units]
h4b_kl_twfe       <- feols(kl_sm ~ tp | unit+month, b_k,  cluster=~unit+month)
h4b_kl_twfe_ctrl  <- feols(kl_sm ~ tp + log_words + log_aud_m | unit+month, b_k,  cluster=~unit+month)
h4b_kl_twfeM      <- feols(kl_sm ~ tp | unit+month, bm_k, cluster=~unit+month)
h4b_kl_twfeM_ctrl <- feols(kl_sm ~ tp + log_words + log_aud_m | unit+month, bm_k, cluster=~unit+month)
b_k[, kl_res := kl_sm - predict(feols(kl_sm ~ log_words + log_aud_m | unit+month, b_k), newdata=b_k)]
h4b_kl_scm      <- scm(b_k, "kl_sm")
h4b_kl_scm_ctrl <- scm(b_k, "kl_res")
# ---- cosine ----
b_c <- D[is.finite(cosine) & is.finite(log_words)]; bm_c <- b_c[unit %in% matched_units]
h4b_cos_twfe       <- feols(cosine ~ tp | unit+month, b_c,  cluster=~unit+month)
h4b_cos_twfe_ctrl  <- feols(cosine ~ tp + log_words + log_aud_m | unit+month, b_c,  cluster=~unit+month)
h4b_cos_twfeM      <- feols(cosine ~ tp | unit+month, bm_c, cluster=~unit+month)
h4b_cos_twfeM_ctrl <- feols(cosine ~ tp + log_words + log_aud_m | unit+month, bm_c, cluster=~unit+month)
b_c[, cos_res := cosine - predict(feols(cosine ~ log_words + log_aud_m | unit+month, b_c), newdata=b_c)]
h4b_cos_scm      <- scm(b_c, "cosine")
h4b_cos_scm_ctrl <- scm(b_c, "cos_res")

H4b <- rbindlist(list(
  r2("JSD",    h4b_jsd_twfe, h4b_jsd_twfe_ctrl, h4b_jsd_twfeM, h4b_jsd_twfeM_ctrl, h4b_jsd_scm, h4b_jsd_scm_ctrl),
  r2("KL",     h4b_kl_twfe,  h4b_kl_twfe_ctrl,  h4b_kl_twfeM,  h4b_kl_twfeM_ctrl,  h4b_kl_scm,  h4b_kl_scm_ctrl),
  r2("cosine", h4b_cos_twfe, h4b_cos_twfe_ctrl, h4b_cos_twfeM, h4b_cos_twfeM_ctrl, h4b_cos_scm, h4b_cos_scm_ctrl)))

## ---- show & save ------------------------------------------------------------
cat("\n===== H4a (pre-payment divergence level) =====\n"); print(H4a)
cat("\n===== H4b (post-payment divergence DiD) =====\n"); print(H4b)
fwrite(H4a, file.path(SC, "main_h4a.csv")); fwrite(H4b, file.path(SC, "main_h4b.csv"))

## ---- SAVE every fitted model + the summary tables + panel --------------------
## load(file.path(SC, "main_h4_models.RData")) later to reuse any h4a_*/h4b_* object.
mods_h4a <- mget(ls(pattern = "^h4a_"))    # 3 measures x 4 specs
mods_h4b <- mget(ls(pattern = "^h4b_"))    # 3 measures x (4 feols + 2 scm vectors)
saveRDS(list(H4a = H4a, H4b = H4b, models = c(mods_h4a, mods_h4b)),
        file.path(SC, "main_h4_models.rds"))
save.image(file = file.path(SC, "main_h4_models.RData"))
cat("\nSaved", length(mods_h4a) + length(mods_h4b),
    "model objects + tables -> main_h4_models.{rds,RData}\n")
