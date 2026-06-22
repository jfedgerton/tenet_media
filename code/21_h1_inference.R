###############################################################################
# 27_h1_inference.R  --  design-based / few-cluster-robust inference for H1.
# The grid showed H1 is "never null"; with only 3 treated clusters the analytic
# cluster-robust p-values are likely too small, so we use design-based inference:
#
#   RANDOMIZATION INFERENCE: re-assign the treated label to random sets of
#       control shows (same size as the real treated set), re-estimate the H1 OLS
#       coefficient B times, and compare the real coefficient to that null.
#       p_RI = (1 + #{|placebo| >= |real|}) / (1 + B).  No distributional assumptions.
#
# Model (pre-payment): y ~ tenet + t + t^2 + log_aud, clusters = show.
# Outcomes: Russia score/pos/net + Combined score (headline). Treated = 3 units
# (benny, rubin, tim_pool) from baseline_panel.csv. Treatment 2023-10-01.
# Output: master_h1_inference.csv   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(fixest) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); MINMENT <- 5; B_RI <- 2000
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month - minm)/30.4375))]; P[, t2 := t^2]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s){ v <- aud[key == norm(s), mean_audience]; if(length(v)) v[1] else NA_real_ }
units <- unique(P$unit)
ua <- vapply(units, function(u) if(u=="tim_pool") sum(sapply(TIM, al), na.rm=TRUE) else al(u), numeric(1))
um <- data.table(unit = units, log_aud = log(ua)); P <- merge(P, um, by = "unit", all.x = TRUE)

outcomes <- list(c("Russia","score","r_score","n_ment_r"), c("Russia","pos","r_pos","n_ment_r"), c("Russia","net","r_net","n_ment_r"),
                 c("Combined","score","c_score","n_ment_r"), c("Combined","pos","c_pos","n_ment_r"), c("Combined","net","c_net","n_ment_r"))
ctrl_units <- setdiff(units, TRU); nT <- length(TRU)
RES <- list()
for(o in outcomes){
  set <- o[1]; met <- o[2]; col <- o[3]; mf <- o[4]
  d <- P[get(mf) >= MINMENT & !is.na(log_aud) & !is.na(get(col)) & month < TREAT]
  if(set=="Combined") d <- d[n_ment_u >= MINMENT]
  d[, tenet := as.integer(unit %in% TRU)]
  real <- coef(feols(as.formula(paste(col, "~ tenet + t + t2 + log_aud")), d, cluster=~unit))["tenet"]
  # (A) randomization inference
  ph <- numeric(B_RI)
  for(b_ in seq_len(B_RI)){
    fake <- sample(ctrl_units, nT)
    d[, tn := as.integer(unit %in% fake)]
    ph[b_] <- tryCatch(coef(feols(as.formula(paste(col, "~ tn + t + t2 + log_aud")), d[unit %in% c(ctrl_units)]))["tn"], error=function(e) NA)
  }
  ph <- ph[!is.na(ph)]; p_ri <- (1 + sum(abs(ph) >= abs(real))) / (1 + length(ph))
  RES[[length(RES)+1]] <- data.table(set=set, metric=met, estimate=as.numeric(real),
      p_randomization=p_ri, n_placebo=length(ph),
      ri_null_q95=as.numeric(quantile(abs(ph),0.95)))
}
fin <- rbindlist(RES)
fwrite(fin, file.path(SC, "master_h1_inference.csv"))
print(fin); cat("DONE_H1_INFERENCE\n")
