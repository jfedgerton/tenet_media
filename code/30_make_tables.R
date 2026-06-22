###############################################################################
# 30_make_tables.R  --  STANDARD manuscript regression tables via fixest::etable.
#   ROWS    = independent variables (Treatment + controls: log words, log audience)
#   COLUMNS = model specification (Full sample / Matched) x dependent variable
#   Coefficients with SE below; FE rows, N, R^2 reported. Stars *** .01 ** .05 * .10.
#
# Tables written to data/sc_results/ :
#   table1_h1_combined.tex  table1_h1_russia.tex   (H1 selection: score/pos/net)
#   table2_h2_combined.tex  table2_h2_russia.tex   (H2 amplification DiD: score/pos/net)
#   table3_h3.tex           (H3 agenda: Russia/Ukraine/Combined topic proportion)
#   table4_h4.tex           (H4 divergence: JSD/KL/Cosine)
# Seed 123. PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); MINMENT <- 5
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

## matched donor set (pre-payment audience + words; same Mahalanobis match as 13)
covs <- P[month < TREAT, .(laud = mean(log_aud_m, na.rm = TRUE), mlogw = mean(log_words, na.rm = TRUE)), by = unit]
covs[, tenet := as.integer(unit %in% TRU)]; covs <- covs[is.finite(laud) & is.finite(mlogw)]
mout <- Match(Tr = covs$tenet, X = as.matrix(covs[, .(laud, mlogw)]), M = 3, replace = TRUE, ties = FALSE)
MU <- unique(c(covs$unit[mout$index.treated], covs$unit[mout$index.control]))

## ---- model fitters (controls spec; full sample + matched) -------------------
lvl <- function(y, mfilt){                          # H1 pre-payment level | month FE
  d <- P[month < TREAT & is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  d <- d[eval(mfilt, d)]
  f <- as.formula(paste0(y, " ~ tenet + log_words + log_aud_m | mfac"))
  list(full = feols(f, d, cluster = ~ mfac + unit), matched = feols(f, d[unit %in% MU], cluster = ~ mfac + unit)) }
did <- function(y, dat, mfilt){                     # H2/H3/H4 DiD | unit + month FE
  d <- dat[is.finite(get(y)) & is.finite(log_words) & is.finite(log_aud_m)]
  d <- d[eval(mfilt, d)]
  f <- as.formula(paste0(y, " ~ tp + log_words + log_aud_m | unit + month"))
  list(full = feols(f, d, cluster = ~ unit + month), matched = feols(f, d[unit %in% MU], cluster = ~ unit + month)) }

ALL <- quote(TRUE); RUS <- quote(n_ment_r >= MINMENT); BOTH <- quote(n_ment_r >= MINMENT & n_ment_u >= MINMENT)
DICT <- c(tenet = "Treated (Tenet)", tp = "Treated $\\times$ Post",
          log_words = "Log words", log_aud_m = "Log audience")
SIG  <- c("***" = 0.01, "**" = 0.05, "*" = 0.10)
hdr  <- function(o3) list("^Sample" = c("Full sample" = 3, "Matched" = 3),
                          "^Outcome" = c(o3, o3))

write_tab <- function(models, headers, title, lab, file) {
  etable(models, tex = TRUE, file = file.path(SC, file), replace = TRUE,
         dict = DICT, headers = headers, fitstat = ~ n + r2,
         signif.code = SIG, digits = 3, digits.stats = 3,
         title = title, label = lab,
         notes = "Coefficients with clustered SE below. *** p<.01, ** p<.05, * p<.10.") }

## ---- TABLE 1: H1 selection (score / pos / net) ------------------------------
m1c <- list(lvl("c_score",BOTH)$full, lvl("c_pos",BOTH)$full, lvl("c_net",BOTH)$full,
            lvl("c_score",BOTH)$matched, lvl("c_pos",BOTH)$matched, lvl("c_net",BOTH)$matched)
write_tab(m1c, hdr(c("Score","Positive","Net")),
          "H1 (selection): pre-payment level, Combined stance (Russia $-$ Ukraine). Month FE; SE clustered by month and unit.",
          "tab:h1_combined", "table1_h1_combined.tex")
m1r <- list(lvl("r_score",RUS)$full, lvl("r_pos",RUS)$full, lvl("r_net",RUS)$full,
            lvl("r_score",RUS)$matched, lvl("r_pos",RUS)$matched, lvl("r_net",RUS)$matched)
write_tab(m1r, hdr(c("Score","Positive","Net")),
          "H1 (selection): pre-payment level, Russia stance. Month FE; SE clustered by month and unit.",
          "tab:h1_russia", "table1_h1_russia.tex")

## ---- TABLE 2: H2 amplification DiD (score / pos / net) ----------------------
m2c <- list(did("c_score",P,BOTH)$full, did("c_pos",P,BOTH)$full, did("c_net",P,BOTH)$full,
            did("c_score",P,BOTH)$matched, did("c_pos",P,BOTH)$matched, did("c_net",P,BOTH)$matched)
write_tab(m2c, hdr(c("Score","Positive","Net")),
          "H2 (amplification): post-payment DiD, Combined stance. Unit and month FE; SE clustered by unit and month.",
          "tab:h2_combined", "table2_h2_combined.tex")
m2r <- list(did("r_score",P,RUS)$full, did("r_pos",P,RUS)$full, did("r_net",P,RUS)$full,
            did("r_score",P,RUS)$matched, did("r_pos",P,RUS)$matched, did("r_net",P,RUS)$matched)
write_tab(m2r, hdr(c("Score","Positive","Net")),
          "H2 (amplification): post-payment DiD, Russia stance. Unit and month FE; SE clustered by unit and month.",
          "tab:h2_russia", "table2_h2_russia.tex")

## ---- TABLE 3: H3 agenda topic proportion (Russia / Ukraine / Combined) ------
m3 <- list(did("prop_rus",P,ALL)$full, did("prop_ukr",P,ALL)$full, did("prop_comb",P,ALL)$full,
           did("prop_rus",P,ALL)$matched, did("prop_ukr",P,ALL)$matched, did("prop_comb",P,ALL)$matched)
write_tab(m3, hdr(c("Russia","Ukraine","Combined")),
          "H3 (agenda): post-payment DiD on topic proportion. Unit and month FE; SE clustered by unit and month.",
          "tab:h3", "table3_h3.tex")

## ---- TABLE 4: H4 agenda divergence (JSD / KL / Cosine) ----------------------
m4 <- list(did("jsd",H,ALL)$full, did("kl_sm",H,ALL)$full, did("cosine",H,ALL)$full,
           did("jsd",H,ALL)$matched, did("kl_sm",H,ALL)$matched, did("cosine",H,ALL)$matched)
write_tab(m4, hdr(c("JSD","KL","Cosine")),
          "H4 (divergence): post-payment DiD on agenda divergence. Negative = treated converge. Unit and month FE; SE clustered by unit and month.",
          "tab:h4", "table4_h4.tex")

cat("WROTE table1_h1_{combined,russia}, table2_h2_{combined,russia}, table3_h3, table4_h4 (.tex)\n")
