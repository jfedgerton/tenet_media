###############################################################################
# 26_min_mention_sweep.R  --  robustness sweep over the MINIMUM-MENTIONS inclusion
# threshold, crossed with the unmentioned-coding choice, to produce a DISTRIBUTION
# of H1/H2 coefficients instead of betting on one threshold. Pure R, interactive.
#
# Swept parameters:
#   min_ment in {0, 1, 3, 5, 10, 20}   include a show-month only at/above this many mentions
#   coding   in {conditional, zero}     conditional = mean over MENTIONED sentences (drop
#                                        unmentioned); zero = unmentioned coded 0/neutral,
#                                        mean over ALL topic-78/79 sentences (= conditional
#                                        value x mention rate). For `zero`, the threshold is
#                                        applied to total volume n_total.
#
# Outcomes (9): Russia / Ukraine / Combined  x  score / pos / net.
# Specs: H1 (pre-payment level: month-FE + log_words, cluster unit) and
#        H2 (TWFE: tp + post:log_words | unit + month, cluster unit).
# Treatment 2023-10-01. Output: master_minment_sweep.csv.  Seed 123.
# PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest) })
set.seed(123)

CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

## ---- panel + total-words control --------------------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
P[, tenet := as.integer(unit %in% TRU)]; P[, mfac := factor(month)]
P[, t := as.integer(round(as.numeric(month - min(month))/30.4375))]; P[, t2 := t^2]
P[, post := as.integer(month >= TREAT)]; P[, tp := tenet * post]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit","month"), all.x = TRUE); P[, log_words := log(n_words)]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]

## ---- unmentioned-as-0 versions (conditional value x mention rate) -----------
zc <- function(val, nment) fifelse(nment > 0, val * nment / P$n_total, 0)
P[, r_score0 := zc(r_score, n_ment_r)]; P[, r_pos0 := zc(r_pos, n_ment_r)]; P[, r_net0 := zc(r_net, n_ment_r)]
P[, u_score0 := zc(u_score, n_ment_u)]; P[, u_pos0 := zc(u_pos, n_ment_u)]; P[, u_net0 := zc(u_net, n_ment_u)]
P[, c_score0 := r_score0 - u_score0]; P[, c_pos0 := r_pos0 - u_pos0]; P[, c_net0 := r_net0 - u_net0]

## outcome map: set, metric, conditional column, zero column, mention column
OUT <- list(
  c("Russia","score","r_score","r_score0","n_ment_r"), c("Russia","pos","r_pos","r_pos0","n_ment_r"), c("Russia","net","r_net","r_net0","n_ment_r"),
  c("Ukraine","score","u_score","u_score0","n_ment_u"), c("Ukraine","pos","u_pos","u_pos0","n_ment_u"), c("Ukraine","net","u_net","u_net0","n_ment_u"),
  c("Combined","score","c_score","c_score0","n_ment_r"), c("Combined","pos","c_pos","c_pos0","n_ment_r"), c("Combined","net","c_net","c_net0","n_ment_r"))

gT <- function(m, term) if (is.null(m)) c(NA,NA) else { ct <- coeftable(m); if (term %in% rownames(ct)) ct[term, c("Estimate","Pr(>|t|)")] else c(NA,NA) }

## ---- one (min_ment, coding) combination across the 9 outcomes ---------------
run_combo <- function(min_ment, coding) {
  rows <- list()
  for (o in OUT) {
    set <- o[1]; met <- o[2]; col <- if (coding == "zero") o[4] else o[3]; mc <- o[5]
    if (coding == "zero") {
      d <- P[n_total >= min_ment & is.finite(get(col)) & is.finite(log_words)]
    } else if (set == "Combined") {
      d <- P[n_ment_r >= min_ment & n_ment_u >= min_ment & is.finite(get(col)) & is.finite(log_words)]
    } else {
      d <- P[get(mc) >= min_ment & is.finite(get(col)) & is.finite(log_words)]
    }
    pre <- d[post == 0]
    h1 <- tryCatch(feols(as.formula(paste(col, "~ tenet + log_words | mfac")), pre, cluster = ~unit), error = function(e) NULL)
    h2 <- tryCatch(feols(as.formula(paste(col, "~ tp + post:log_words | unit + month")), d, cluster = ~unit), error = function(e) NULL)
    v1 <- gT(h1, "tenet"); v2 <- gT(h2, "tp")
    rows[[length(rows)+1]] <- data.table(min_ment = min_ment, coding = coding, set = set, metric = met,
      n_obs = nrow(d), H1_est = v1[1], H1_p = v1[2], H2_est = v2[1], H2_p = v2[2])
  }
  rbindlist(rows)
}

## ---- sweep: thresholds x coding ---------------------------------------------
sweep <- CJ(min_ment = c(0, 1, 3, 5, 10, 20), coding = c("conditional", "zero"))
fin <- rbindlist(lapply(seq_len(nrow(sweep)), function(i) run_combo(sweep$min_ment[i], sweep$coding[i])))
fin[, sig := fifelse(is.na(H2_p), "NA", fifelse(H2_p < 0.05, "*", "ns"))]
fwrite(fin, file.path(SC, "master_minment_sweep.csv"))
print(fin); cat("DONE_MINMENT_SWEEP", nrow(fin), "rows\n")
