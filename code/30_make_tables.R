###############################################################################
# 30_make_tables.R  --  manuscript tables (LaTeX) from the panels.
#   table1_summary.tex   Summary statistics: every IV and DV used in H1-H4.
#   table2_h1.tex        H1 (selection) across the 4 model specifications
#                        (Simple | Simple matched | + Controls | + Controls matched).
#   table3_did_all.tex   Omnibus DiD: H2/H3/H4 headline outcomes in one table
#                        (add outcome/hypothesis subheaders in the manuscript).
#   tab_h2_{combined,russia}.tex, tab_h3.tex, tab_h4.tex
#                        per-hypothesis DiD breakdowns (Full/Matched x outcomes).
# Standard regression-table style via fixest::etable (rows = variables incl.
# controls; columns = specification x dependent variable). Seed 123. PI: Jared Edgerton.
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); SCM_WIN <- as.Date("2021-01-01"); MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- panels (identical construction to 13/15/29) ----------------------------
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
H <- fread(file.path(SC, "h4_divergence_panel.csv")); H[, month := as.Date(month)]
H <- H[topicset == "all" & reference == "contemp" & rare == "rare"]
H[, unit := fifelse(unit %in% TIM, "tim_pool", unit)]
H[, tenet := as.integer(unit %in% TRU)]; H[, post := as.integer(month >= TREAT)]; H[, tp := tenet * post]
H <- merge(H, Vunit, by = c("unit", "month"), all.x = TRUE); H[, log_words := log(n_words)]
H <- merge(H, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); H[, log_aud_m := log(aud_mid)]

covs <- P[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
MU <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

###############################################################################
## TABLE 1 -- summary statistics (manual booktabs; N, mean, SD, min, max) ------
###############################################################################
f3 <- function(x) ifelse(is.na(x), "", formatC(x, format = "f", digits = 3))
fN <- function(x) formatC(x, format = "d", big.mark = ",")
srow <- function(lbl, x){ x <- x[is.finite(x)]
  paste(lbl, fN(length(x)), f3(mean(x)), f3(sd(x)), f3(min(x)), f3(max(x)), sep = " & ") }
GRP <- function(g) paste0("\\addlinespace[2pt]\\multicolumn{6}{l}{\\textit{", g, "}} \\\\")
body1 <- c(
  GRP("Dependent variables (main outcomes)"),
  srow("\\quad Russia positive rate",      P$r_pos),
  srow("\\quad Combined positive rate",    P$c_pos),
  srow("\\quad Combined topic proportion", P$prop_comb),
  srow("\\quad JS divergence",             H$jsd),
  GRP("Independent variables"),
  srow("\\quad Treated (Tenet)", P$tenet), srow("\\quad Post-payment", P$post),
  srow("\\quad Log words", P$log_words), srow("\\quad Log audience", P$log_aud_m))
body1 <- paste0(body1, ifelse(grepl("multicolumn", body1), "", " \\\\"))
tab1 <- c("% requires \\usepackage{booktabs}", "\\begin{table}[!ht]\\centering",
  "\\caption{Summary statistics for all dependent and independent variables (show-month observations).}",
  "\\label{tab:summary}", "\\small", "\\begin{tabular}{l rrrrr}", "\\toprule",
  "Variable & $N$ & Mean & SD & Min & Max \\\\", "\\midrule", body1, "\\bottomrule", "\\end{tabular}", "\\end{table}")
writeLines(tab1, file.path(SC, "table1_summary.tex"))

###############################################################################
## model fitters --------------------------------------------------------------
###############################################################################
ALL <- quote(TRUE); RUS <- quote(n_ment_r >= MINMENT); BOTH <- quote(n_ment_r >= MINMENT & n_ment_u >= MINMENT)
DICT <- c(tenet = "Treated (Tenet)", tp = "Treated $\\times$ Post", log_words = "Log words",
          log_aud_m = "Log audience", mfac = "Month", unit = "Unit", month = "Month")
SIG  <- c("***" = 0.01, "**" = 0.05, "*" = 0.10)
NOTE <- "Coefficients with clustered SE below. *** p<.01, ** p<.05, * p<.10."
etx  <- function(models, headers, title, lab, file)
  etable(models, tex = TRUE, file = file.path(SC, file), replace = TRUE, depvar = FALSE,
         dict = DICT, headers = headers, fitstat = ~ n + r2, signif.code = SIG,
         digits = 3, digits.stats = 3, title = title, label = lab, notes = NOTE)

h1specs <- function(y, mfilt){                       # H1: 4 specs for one outcome
  d <- P[month < TREAT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]; d <- d[eval(mfilt, d)]
  dm <- d[unit %in% MU]; fs <- paste0(y, " ~ tenet | mfac"); fc <- paste0(y, " ~ tenet + log_words + log_aud_m | mfac")
  list(feols(as.formula(fs), d, cluster = ~ mfac + unit), feols(as.formula(fs), dm, cluster = ~ mfac + unit),
       feols(as.formula(fc), d, cluster = ~ mfac + unit), feols(as.formula(fc), dm, cluster = ~ mfac + unit)) }
lvlm <- function(y, mfilt){                          # H1 level, controls spec, full + matched
  d <- P[month < TREAT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]; d <- d[eval(mfilt, d)]
  f <- paste0(y, " ~ tenet + log_words + log_aud_m | mfac")
  list(full = feols(as.formula(f), d, cluster = ~ mfac + unit), matched = feols(as.formula(f), d[unit %in% MU], cluster = ~ mfac + unit)) }
didm <- function(y, dat, mfilt){                     # DiD controls spec, full + matched
  d <- dat[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]; d <- d[eval(mfilt, d)]
  f <- paste0(y, " ~ tp + log_words + log_aud_m | unit + month")
  list(full = feols(as.formula(f), d, cluster = ~ unit + month), matched = feols(as.formula(f), d[unit %in% MU], cluster = ~ unit + month)) }
didf <- function(y, dat, mfilt) didm(y, dat, mfilt)$full

###############################################################################
## TABLE 2 -- H1 (selection) by model specification. MAIN outcomes only:
##   Russia positive rate + Combined positive rate, each across the 4 specs.
###############################################################################
SP4 <- c("Simple", "Simple (M)", "+ Controls", "+ Controls (M)")
etx(c(h1specs("r_pos", RUS), h1specs("c_pos", BOTH)),
    list("^Outcome" = c("Russia positive rate" = 4, "Combined positive rate" = 4),
         "^Specification" = c(SP4, SP4)),
    "H1 (selection): pre-payment level on the positive-rate outcomes, across model specifications. Month FE; SE clustered by month and unit.",
    "tab:h1", "table2_h1.tex")

###############################################################################
## TABLE 3 -- DiD across SPECIFICATIONS (TWFE / Matched / Synthetic control)
##   to show the post-payment effect is null and inconsistent across estimators.
##   Main outcomes: H2 Russia+, H2 Combined+, H3 Combined topic share, H4 JSD.
###############################################################################
scm_w <- function(Y0p, y1p){ n <- ncol(Y0p); D <- t(Y0p) %*% Y0p + diag(1e-8, n); dv <- as.vector(t(Y0p) %*% y1p)
  A <- cbind(rep(1, n), diag(n)); b <- c(1, rep(0, n)); tryCatch(solve.QP(D, dv, A, b, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm1 <- function(y1, Y0, pre){ w <- scm_w(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w)
  list(r = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm <- function(pan, col, wcol){
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (!nrow(tr)) return(c(NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(get(wcol), 1))), by = month]; mo <- sort(comp$month); pre <- mo < TREAT
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA)); y1 <- comp$y[match(mo, comp$month)]
  don <- dcast(dd[tenet == 0], month ~ unit, value.var = col); don <- don[match(mo, don$month)]; dm <- as.matrix(don[, -1])
  for (j in seq_len(ncol(dm))){ v <- dm[, j]; if (anyNA(v)) { v[is.na(v)] <- mean(v, na.rm = TRUE); dm[, j] <- v } }
  good <- which(apply(dm, 2, function(x) all(is.finite(x)) & sd(x) > 0)); if (length(good) < 5 || anyNA(y1)) return(c(NA, NA))
  Y0 <- dm[, good, drop = FALSE]; m <- scm1(y1, Y0, pre); rs <- c()
  for (j in seq_len(ncol(Y0))){ o <- scm1(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$r)) rs <- c(rs, o$r) }
  c(m$gap, if (length(rs)) (sum(rs >= m$r) + 1) / (length(rs) + 1) else NA) }
gtp <- function(m){ ct <- coeftable(m); if ("tp" %in% rownames(ct)) as.numeric(ct["tp", c("Estimate", "Pr(>|t|)")]) else c(NA, NA) }

star <- function(p) ifelse(is.na(p), "", ifelse(p < .01, "***", ifelse(p < .05, "**", ifelse(p < .10, "*", ""))))
OUTS <- list(list("r_pos", P, RUS, "n_ment_r"), list("c_pos", P, BOTH, "n_ment_r"),
             list("prop_comb", P, ALL, "n_words"), list("jsd", H, ALL, "n_sentences"))
m3 <- list(); scmg <- character(0)                          # 8 feols (4 outcomes x TWFE/Matched) + SCM gaps
for (o in OUTS){ mm <- didm(o[[1]], o[[2]], o[[3]]); m3 <- c(m3, list(mm$full, mm$matched))
  sc <- scm(o[[2]][eval(o[[3]], o[[2]])], o[[1]], o[[4]])
  scmg <- c(scmg, ifelse(is.na(sc[1]), "", sprintf("%.3f%s", sc[1], star(sc[2]))), "") }   # gap under each outcome's first col
etable(m3, tex = TRUE, file = file.path(SC, "table3_did_all.tex"), replace = TRUE, depvar = FALSE,
       dict = DICT, fitstat = ~ n + r2, signif.code = SIG, digits = 3, digits.stats = 3,
       headers = list("^Outcome" = c("Russia positive" = 2, "Combined positive" = 2, "Combined topic share" = 2, "JS divergence" = 2),
                      "^Specification" = c("TWFE", "Matched", "TWFE", "Matched", "TWFE", "Matched", "TWFE", "Matched")),
       extralines = list("Synthetic control (gap)" = scmg),
       title = "Post-payment difference-in-differences across estimators, main outcomes (H2-H4). Treated $\\times$ Post; TWFE and Matched include log words and log audience, unit and month fixed effects, SE clustered by unit and month. The synthetic-control gap (in-space placebo $p$) is reported in the bottom row. Effects are small and lose significance across specifications.",
       label = "tab:did_main", notes = NOTE)

###############################################################################
## APPENDIX -- full outcome breakdowns (score/pos/net, Ukraine, KL/Cosine) ----
###############################################################################
hdr6 <- function(o3) list("^Sample" = c("Full sample" = 3, "Matched" = 3), "^Outcome" = c(o3, o3))
ap_h1c <- list(lvlm("r_score",RUS)$full, lvlm("r_pos",RUS)$full, lvlm("r_net",RUS)$full,
               lvlm("r_score",RUS)$matched, lvlm("r_pos",RUS)$matched, lvlm("r_net",RUS)$matched)
etx(ap_h1c, hdr6(c("Score","Positive","Net")), "H1 (appendix): Russia stance, all operationalizations.", "tab:ah1r", "tabA_h1_russia.tex")
ap_h1cc <- list(lvlm("c_score",BOTH)$full, lvlm("c_pos",BOTH)$full, lvlm("c_net",BOTH)$full,
                lvlm("c_score",BOTH)$matched, lvlm("c_pos",BOTH)$matched, lvlm("c_net",BOTH)$matched)
etx(ap_h1cc, hdr6(c("Score","Positive","Net")), "H1 (appendix): Combined stance, all operationalizations.", "tab:ah1c", "tabA_h1_combined.tex")
m_h2c <- list(didm("c_score",P,BOTH)$full, didm("c_pos",P,BOTH)$full, didm("c_net",P,BOTH)$full,
              didm("c_score",P,BOTH)$matched, didm("c_pos",P,BOTH)$matched, didm("c_net",P,BOTH)$matched)
etx(m_h2c, hdr6(c("Score","Positive","Net")), "H2 (appendix): Combined stance DiD.", "tab:ah2c", "tabA_h2_combined.tex")
m_h2r <- list(didm("r_score",P,RUS)$full, didm("r_pos",P,RUS)$full, didm("r_net",P,RUS)$full,
              didm("r_score",P,RUS)$matched, didm("r_pos",P,RUS)$matched, didm("r_net",P,RUS)$matched)
etx(m_h2r, hdr6(c("Score","Positive","Net")), "H2 (appendix): Russia stance DiD.", "tab:ah2r", "tabA_h2_russia.tex")
m_h3 <- list(didm("prop_rus",P,ALL)$full, didm("prop_ukr",P,ALL)$full, didm("prop_comb",P,ALL)$full,
             didm("prop_rus",P,ALL)$matched, didm("prop_ukr",P,ALL)$matched, didm("prop_comb",P,ALL)$matched)
etx(m_h3, hdr6(c("Russia","Ukraine","Combined")), "H3 (appendix): topic-proportion DiD.", "tab:ah3", "tabA_h3.tex")
m_h4 <- list(didm("jsd",H,ALL)$full, didm("kl_sm",H,ALL)$full, didm("cosine",H,ALL)$full,
             didm("jsd",H,ALL)$matched, didm("kl_sm",H,ALL)$matched, didm("cosine",H,ALL)$matched)
etx(m_h4, hdr6(c("JSD","KL","Cosine")), "H4 (appendix): agenda-divergence DiD.", "tab:ah4", "tabA_h4.tex")

cat("WROTE table1_summary, table2_h1, table3_did_all + appendix tabA_h1/h2/h3/h4 (.tex)\n")
