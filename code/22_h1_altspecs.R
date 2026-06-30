###############################################################################
# 27b_h1_altspecs.R  --  alternative H1 (pre-payment "more pro-Russia") specs that
# (1) drop the static listenership control [mean_audience is invariant per show, so
#     it adds nothing under FE and is a cross-sectional nuisance under OLS],
# (2) add month-FE and year-FE variants, and
# (3) cluster by SHOW HOST (Tim Pool's three feeds collapse to one host cluster),
# each reported with an analytic p AND a permutation (randomization-inference) p.
#
# Uses the PER-FEED panel (loso_stance_panel.csv) so host clustering is meaningful.
# Hosts: tim feeds -> "host_tim"; benny -> "host_benny"; rubin -> "host_rubin";
#        each control show is its own host. Treated hosts = {benny, rubin, tim}.
# Pre-period only (month < 2023-10-01). Outcomes: Russia score/pos/net + Combined score.
# Output: master_h1_altspecs.csv   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(fixest) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); MINMENT <- 5; B_RI <- 2000
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny
HOSTS_TREAT <- c("host_benny", "host_rubin", "host_tim")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "loso_stance_panel.csv")); P[, month := as.Date(month)]
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month-minm)/30.4375))]; P[, t2 := t^2]
P[, year := as.integer(format(month, "%Y"))]; P[, mfac := as.factor(month)]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]
P[, host := fifelse(show %in% TIM, "host_tim",
              fifelse(show %in% BEN, "host_benny",
              fifelse(show == "the_rubin_report", "host_rubin", show)))]
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s){ v <- aud[key == norm(s), mean_audience]; if(length(v)) v[1] else NA_real_ }
P[, log_aud := log(sapply(show, al))]

outcomes <- list(c("Russia","score","r_score","n_ment_r"), c("Russia","pos","r_pos","n_ment_r"), c("Russia","net","r_net","n_ment_r"),
                 c("Combined","score","c_score","n_ment_r"), c("Combined","pos","c_pos","n_ment_r"), c("Combined","net","c_net","n_ment_r"))
ctrl_hosts <- setdiff(unique(P$host), HOSTS_TREAT); nT <- length(HOSTS_TREAT)
getp <- function(m) tryCatch(as.numeric(coeftable(m)["tenet","Pr(>|t|)"]), error=function(e) NA_real_)
getb <- function(m) tryCatch(as.numeric(coef(m)["tenet"]), error=function(e) NA_real_)

specs <- c("base_listen", "no_listen", "monthFE_hostclust", "yearFE_hostclust")
fitspec <- function(d, col, sp){
  if(sp=="base_listen")        feols(as.formula(paste(col,"~ tenet + t + t2 + log_aud")), d, cluster=~host)
  else if(sp=="no_listen")     feols(as.formula(paste(col,"~ tenet + t + t2")),           d, cluster=~host)
  else if(sp=="monthFE_hostclust") feols(as.formula(paste(col,"~ tenet | mfac")),          d, cluster=~host)
  else                          feols(as.formula(paste(col,"~ tenet | year")),             d, cluster=~host)
}
RES <- list()
for(o in outcomes){
  set<-o[1]; met<-o[2]; col<-o[3]; mf<-o[4]
  d <- P[get(mf) >= MINMENT & !is.na(get(col)) & month < TREAT & !is.na(log_aud)]
  if(set=="Combined") d <- d[n_ment_u >= MINMENT]
  d[, tenet := as.integer(host %in% HOSTS_TREAT)]
  for(sp in specs){
    m <- tryCatch(fitspec(d, col, sp), error=function(e) NULL)
    b <- if(is.null(m)) NA else getb(m); pa <- if(is.null(m)) NA else getp(m)
    # permutation / randomization-inference p (reassign treated to random control hosts)
    ph <- numeric(B_RI)
    for(k in seq_len(B_RI)){
      fake <- sample(ctrl_hosts, nT); dd <- d[host %in% c(ctrl_hosts)]; dd[, tenet := as.integer(host %in% fake)]
      mk <- tryCatch(fitspec(dd, col, sp), error=function(e) NULL); ph[k] <- if(is.null(mk)) NA else getb(mk)
    }
    ph <- ph[!is.na(ph)]; p_perm <- if(length(ph)) (1+sum(abs(ph)>=abs(b)))/(1+length(ph)) else NA
    RES[[length(RES)+1]] <- data.table(set=set, metric=met, spec=sp, estimate=b, p_analytic=pa, p_permutation=p_perm)
  }
}
fin <- rbindlist(RES)
fin[, sig := fifelse(is.na(p_analytic),"NA",fifelse(p_analytic<0.01,"***",fifelse(p_analytic<0.05,"**",fifelse(p_analytic<0.1,"*","ns"))))]
fwrite(fin, file.path(SC, "master_h1_altspecs.csv"))
print(fin); cat("DONE_H1_ALTSPECS\n")
