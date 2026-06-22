###############################################################################
# 15_main_h4.R  --  MAIN analysis for H4 (agenda divergence), in its own script,
# written sequentially (no loop; small helpers called explicitly per measure).
#
# H4: the Tenet hosts run a more DIVERGENT overall agenda than control conservative
# podcasts. Divergence = distance between a show-month's topic mix and the
# CONTEMPORANEOUS control-pool mix. Built by 14_h4_topic_model.py -> h4_divergence_panel.csv.
#
# MAIN spec selected here: topicset = all, reference = contemp, rare = rare.
# THREE operationalizations of divergence: jsd (headline), kl_sm, cosine.
# TWO specs per measure:
#   H4a (pre-payment level):  (a) OLS  tenet + t + t2 + log_n, SE clustered by unit
#                             (b) matched donor set + same model
#   H4b (post-payment DiD):   (a) TWFE  tp + post:log_n | unit + month, SE clustered by unit
#                             (b) synthetic control (in-space placebo p-value)
#
# Treatment 2023-10-01 (first payment). Treated = tim_pool, benny, rubin. Seed 123.
# Output: main_h4.csv.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)

CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); SCM_WIN <- as.Date("2021-01-01")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

## ---- divergence panel; keep the MAIN spec cells only ------------------------
D <- fread(file.path(SC, "h4_divergence_panel.csv"))
D <- D[topicset == "all" & reference == "contemp" & rare == "rare"]
D[, month := as.Date(month)]
minm <- min(D$month); D[, t := as.integer(round(as.numeric(month - minm)/30.4375))]; D[, t2 := t^2]
D[, mfac := factor(month)]; D[, tenet := as.integer(unit %in% TRU)]
D[, post := as.integer(month >= TREAT)]; D[, tp := tenet * post]
D[, log_n := log(n_sentences)]

## ---- Mahalanobis matching on log audience + mean pre-period volume ----------
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s){ v <- aud[key == norm(s), mean_audience]; if (length(v)) v[1] else NA_real_ }
units <- unique(D$unit)
unit_aud <- sapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u))
covs <- data.table(unit = units, laud = log(unit_aud))
covs <- merge(covs, D[month < TREAT, .(mlogn = mean(log_n)), by = unit], by = "unit")
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogn)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogn)]), M = 3, replace = TRUE, ties = FALSE)
matched_units <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

## ---- synthetic control helper (simplex weights + in-space placebo) ----------
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); Dm <- t(Y0p) %*% Y0p + diag(1e-8, n)
  dv <- as.vector(t(Y0p) %*% y1p); A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n))
  tryCatch(solve.QP(Dm, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(col){
  dd <- D[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(n_sentences, 1))), by = month]
  mo <- sort(unique(dd$month)); pre <- mo < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp[match(mo, comp$month)]$y
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]
  dm <- as.matrix(don[, -1]); good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0)
  if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre)
  rs <- c(); for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }

## ---- helpers: one call per divergence measure -------------------------------
# H4a: pre-payment level (OLS + matched), SE clustered by unit.
fit_h4a <- function(col, label){
  d <- D[month < TREAT & is.finite(get(col))]; dm <- d[unit %in% matched_units]
  ols <- feols(as.formula(paste0(col, " ~ tenet + t + t2 + log_n")), d,  cluster = ~unit)
  mt  <- feols(as.formula(paste0(col, " ~ tenet + t + t2 + log_n")), dm, cluster = ~unit)
  data.table(hyp = "H4a", measure = label,
    est_OLS = round(coef(ols)["tenet"], 4), p_OLS = round(pvalue(ols)["tenet"], 4),
    est_matched = round(coef(mt)["tenet"], 4), p_matched = round(pvalue(mt)["tenet"], 4)) }
# H4b: post-payment DiD (TWFE + SCM).
fit_h4b <- function(col, label){
  d <- D[is.finite(get(col))]
  tw <- feols(as.formula(paste0(col, " ~ tp + post:log_n | unit + month")), d, cluster = ~unit)
  sc <- scm(col)
  data.table(hyp = "H4b", measure = label,
    est_TWFE = round(coef(tw)["tp"], 4), p_TWFE = round(pvalue(tw)["tp"], 4),
    est_SCM = round(sc[1], 4), p_SCM = round(sc[2], 4)) }

## ---- explicit calls: jsd (headline), kl_sm, cosine --------------------------
H4a <- rbindlist(list(
  fit_h4a("jsd",    "JSD"),
  fit_h4a("kl_sm",  "KL"),
  fit_h4a("cosine", "cosine")))
H4b <- rbindlist(list(
  fit_h4b("jsd",    "JSD"),
  fit_h4b("kl_sm",  "KL"),
  fit_h4b("cosine", "cosine")))

cat("\n===== H4a (pre-payment divergence level) =====\n"); print(H4a)
cat("\n===== H4b (post-payment divergence DiD) =====\n");  print(H4b)
fwrite(H4a, file.path(SC, "main_h4a.csv"))
fwrite(H4b, file.path(SC, "main_h4b.csv"))
