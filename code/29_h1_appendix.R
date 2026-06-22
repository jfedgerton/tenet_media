###############################################################################
# 27c_h1_appendix.R  --  appendix series of H1 (pre-payment "more pro-Russia") models,
# varying the volume/exposure control set and the fixed-effects structure. Built on the
# pooled baseline_panel (3 treated units: tim_pool, benny, rubin) to match the main spec.
#
# Volume control "total words": time-varying total sentence count per unit-month (proxy
# for words), from loso_volume.csv. For tim_pool it is the MEAN monthly volume across his
# three feeds (not the sum), so the pooled host is not artificially inflated.
#
# Specs (all clustered by unit, pre-period month < 2023-10-01):
#   S1 none        y ~ tenet + t + t2
#   S2 listen      + log_aud (static listenership)
#   S3 words       + log_words (time-varying total words)   <- preferred control
#   S4 both        + log_aud + log_words
#   S5 monthFE     y ~ tenet + log_words | month
#   S6 yearFE      y ~ tenet + log_words | year
# Each reported with analytic p AND permutation (randomization-inference) p.
# Outcomes: Russia score/pos/net + Combined score/pos/net.
# Output: master_h1_appendix.csv   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(fixest) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); MINMENT <- 5; B_RI <- 2000
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month-minm)/30.4375))]; P[, t2 := t^2]
P[, year := as.integer(format(month, "%Y"))]; P[, c_score := r_score-u_score]; P[, c_pos := r_pos-u_pos]; P[, c_net := r_net-u_net]
# listenership (static)
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s){ v <- aud[key == norm(s), mean_audience]; if(length(v)) v[1] else NA_real_ }
ua <- function(u) if(u=="tim_pool") sum(sapply(TIM, al), na.rm=TRUE) else al(u)
P[, log_aud := log(sapply(unit, ua))]
# total-words (time-varying); tim_pool = MEAN monthly volume across the three feeds
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
vt <- V[show %in% TIM, .(n_sent_total = mean(n_sent_total)), by = month][, unit := "tim_pool"]
vo <- V[!(show %in% TIM), .(unit = show, month, n_sent_total)]
VV <- rbind(vt[, .(unit, month, n_sent_total)], vo)
P <- merge(P, VV, by = c("unit","month"), all.x = TRUE); P[, log_words := log(n_sent_total)]

outcomes <- list(c("Russia","score","r_score"),c("Russia","pos","r_pos"),c("Russia","net","r_net"),
                 c("Combined","score","c_score"),c("Combined","pos","c_pos"),c("Combined","net","c_net"))
fit <- function(d, col, sp){
  if(sp=="none")        feols(as.formula(paste(col,"~ tenet + t + t2")), d, cluster=~unit)
  else if(sp=="listen") feols(as.formula(paste(col,"~ tenet + t + t2 + log_aud")), d, cluster=~unit)
  else if(sp=="words")  feols(as.formula(paste(col,"~ tenet + t + t2 + log_words")), d, cluster=~unit)
  else if(sp=="both")   feols(as.formula(paste(col,"~ tenet + t + t2 + log_aud + log_words")), d, cluster=~unit)
  else if(sp=="monthFE")feols(as.formula(paste(col,"~ tenet + log_words | month")), d, cluster=~unit)
  else                  feols(as.formula(paste(col,"~ tenet + log_words | year")), d, cluster=~unit)
}
getb <- function(m) tryCatch(as.numeric(coef(m)["tenet"]), error=function(e) NA_real_)
getp <- function(m) tryCatch(as.numeric(coeftable(m)["tenet","Pr(>|t|)"]), error=function(e) NA_real_)
ctrl <- setdiff(unique(P$unit), TRU); nT <- length(TRU); specs <- c("none","listen","words","both","monthFE","yearFE")
RES <- list()
for(o in outcomes){
  set<-o[1]; met<-o[2]; col<-o[3]
  d <- P[n_ment_r >= MINMENT & !is.na(get(col)) & month < TREAT & !is.na(log_words) & !is.na(log_aud)]
  if(set=="Combined") d <- d[n_ment_u >= MINMENT]
  d[, tenet := as.integer(unit %in% TRU)]
  for(sp in specs){
    m <- tryCatch(fit(d, col, sp), error=function(e) NULL); b <- getb(m); pa <- getp(m)
    ph <- numeric(B_RI)
    for(k in seq_len(B_RI)){ fake <- sample(ctrl, nT); dd <- d[unit %in% ctrl]; dd[, tenet := as.integer(unit %in% fake)]
      mk <- tryCatch(fit(dd, col, sp), error=function(e) NULL); ph[k] <- getb(mk) }
    ph <- ph[!is.na(ph)]; p_perm <- if(length(ph)) (1+sum(abs(ph)>=abs(b)))/(1+length(ph)) else NA
    RES[[length(RES)+1]] <- data.table(set=set, metric=met, spec=sp, estimate=b, p_analytic=pa, p_permutation=p_perm)
  }
}
fin <- rbindlist(RES)
fin[, sig := fifelse(is.na(p_analytic),"NA",fifelse(p_analytic<0.01,"***",fifelse(p_analytic<0.05,"**",fifelse(p_analytic<0.1,"*","ns"))))]
fwrite(fin, file.path(SC, "master_h1_appendix.csv")); print(fin); cat("DONE_H1_APPENDIX\n")
