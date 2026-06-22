###############################################################################
# 23_h4_divergence_grid.R  --  H4 (agenda divergence): estimate H4a (pre-payment
# level) and H4b (post-payment DiD) across the operationalization grid built by
# 22_agenda_divergence_panel.py. Reuses the TWFE + SCM (in-space placebo) machinery.
#
# Outcome D[i,t] = divergence of show-month topic mix from a reference mix.
#   H4a  pre-period level:  D ~ tenet + t + t^2 + log_aud + log_n   (OLS + matched)
#                           -> treated already more divergent before payment?
#   H4b  DiD:               D ~ tp + post:log_aud + log_n | unit+month  (TWFE)
#                           + SCM (composite vs donors, quadprog + in-space placebo)
#                           -> treated diverge MORE post-payment?
#
# Grid: measure {jsd, kl_sm, cosine} x reference {contemp(MAIN), frozen, external}
#       x topicset {all(MAIN), drop7879, droprus} x rare {rare(MAIN), raw}.
#   MAIN spec = jsd / contemp / all / rare.  contemp ref => H4b is a conservative
#   lower bound (spillover attenuates it; frozen/external are the appendix robustness).
# Treatment dates: 2023-10-01, 2023-11-01.  log_n = log(n_sentences) finite-sample control.
# Output: data/sc_results/master_h4_coefs.csv   PI: Jared Edgerton (PSU). Seed 123.
###############################################################################

suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(parallel) })
set.seed(123); setDTthreads(1)
NC <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "8"))
COLLAB <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(COLLAB, "data", "sc_results")
TREAT_DATES <- as.Date(c("2023-10-01", "2023-11-01")); SCM_WIN <- as.Date("2021-01-01"); MINMON <- 6
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "h4_divergence_panel.csv")); P[, month := as.Date(month)]
P[, unit := fifelse(unit %in% TIM, "tim_pool", unit)]      # (already unit-level, defensive)
minm <- min(P$month); P[, t := as.integer(round(as.numeric(month - minm) / 30.4375))]; P[, t2 := t^2]
P[, tenet := as.integer(unit %in% TRU)]; P[, log_n := log(n_sentences)]

## audience + matched donor set (same as 19/21)
aud <- fread(file.path(COLLAB, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s) { v <- aud[key == norm(s), mean_audience]; if (length(v) == 0) NA_real_ else v[1] }
units <- unique(P$unit)
ua <- vapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u), numeric(1))
umeta <- data.table(unit = units, mean_audience = ua); umeta[, log_aud := log(mean_audience)]
P <- merge(P, umeta[, .(unit, log_aud)], by = "unit", all.x = TRUE)
cov <- aud[, .(key, mean_audience, episodes_per_week, weeks_active)]
uc <- rbindlist(lapply(units, function(u) {
  if (u == "tim_pool") { x <- cov[key %in% norm(TIM)]; data.table(unit = u, a = sum(x$mean_audience, na.rm=T), e = mean(x$episodes_per_week, na.rm=T), w = max(x$weeks_active, na.rm=T)) }
  else { x <- cov[key == norm(u)]; if (nrow(x)==0) return(NULL); data.table(unit=u, a=x$mean_audience[1], e=x$episodes_per_week[1], w=x$weeks_active[1]) }
}), fill = TRUE)
uc[, tenet := as.integer(unit %in% TRU)]; uc <- uc[is.finite(log(a))]
X <- as.matrix(uc[, .(la = log(a), e, w)]); X[is.na(X)] <- 0
mo <- Match(Tr = uc$tenet, X = X, M = 3, replace = TRUE)
MU <- unique(c(uc$unit[mo$index.treated], uc$unit[mo$index.control]))

## SCM (quadprog + in-space placebo); weight composite by n_sentences
scm_weights <- function(Y0pre, y1pre) { n <- ncol(Y0pre); Dmat <- t(Y0pre)%*%Y0pre + diag(1e-8,n); dvec <- as.vector(t(Y0pre)%*%y1pre); Amat <- cbind(rep(1,n), diag(n)); bvec <- c(1, rep(0,n)); tryCatch(solve.QP(Dmat,dvec,Amat,bvec,meq=1)$solution, error=function(e) rep(1/n,n)) }
scm_one <- function(y1, Y0, pre) { w <- scm_weights(Y0[pre,,drop=FALSE], y1[pre]); g <- y1 - as.vector(Y0%*%w); list(ratio = sqrt(mean(g[!pre]^2))/sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm_outcome <- function(pan, treat) {
  dd <- pan[!is.na(D) & month >= SCM_WIN]; tr <- dd[tenet == 1]; if (nrow(tr)==0) return(c(NA,NA,NA))
  comp <- tr[, .(y = weighted.mean(D, pmax(n_sentences,1))), by = month]
  months <- sort(unique(dd$month)); pre <- months < treat
  if (sum(pre) < MINMON || sum(!pre) < 2) return(c(NA,NA,NA))
  y1 <- comp[match(months, comp$month)]$y
  don <- dcast(dd[tenet==0], month ~ unit, value.var = "D"); don <- don[match(months, don$month)]; dm <- as.matrix(don[,-1])
  good <- which(colSums(is.na(dm))==0 & apply(dm,2,sd)>0); if (length(good) < 5 || any(is.na(y1))) return(c(NA,NA,NA))
  Y0 <- dm[, good, drop=FALSE]; main <- scm_one(y1, Y0, pre)
  ratios <- c(); for (j in seq_len(ncol(Y0))) { o <- scm_one(Y0[,j], Y0[,-j,drop=FALSE], pre); if (is.finite(o$ratio)) ratios <- c(ratios, o$ratio) }
  pval <- if (length(ratios)) (sum(ratios >= main$ratio) + 1)/(length(ratios)+1) else NA
  c(main$gap, main$ratio, pval)
}
grabT <- function(m, term) { ct <- tryCatch(coeftable(m), error=function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA,NA,NA)); as.numeric(ct[term, c("Estimate","Std. Error","Pr(>|t|)")]) }

MEAS <- c("jsd", "kl_sm", "cosine")
arms <- unique(P[, .(topicset, reference, rare)])
run_arm <- function(ts, rf, ra) {
  base <- P[topicset == ts & reference == rf & rare == ra]
  out <- list(); k <- 0L
  for (meas in MEAS) {
    d0 <- copy(base); d0[, D := get(meas)]; d0 <- d0[!is.na(D) & !is.na(log_aud)]
    for (td in TREAT_DATES) {
      d0[, post := as.integer(month >= td)]; d0[, tp := tenet * post]
      pre <- d0[post == 0]; prem <- pre[unit %in% MU]
      f1 <- D ~ tenet + t + t2 + log_aud + log_n
      ftw <- D ~ tp + post:log_aud + log_n | unit + month
      add <- function(spec, v) { k <<- k + 1L; out[[k]] <<- data.table(measure=meas, reference=rf, topicset=ts, rare=ra, treat_date=as.character(td), spec=spec, estimate=v[1], se=v[2], p=v[3]) }
      add("H4a_OLS",     grabT(tryCatch(feols(f1, pre,  cluster=~unit), error=function(e) NULL), "tenet"))
      add("H4a_matched", grabT(tryCatch(feols(f1, prem, cluster=~unit), error=function(e) NULL), "tenet"))
      add("H4b_TWFE",    grabT(tryCatch(feols(ftw, d0,  cluster=~unit), error=function(e) NULL), "tp"))
      sc <- tryCatch(scm_outcome(d0, td), error=function(e) c(NA,NA,NA))
      add("H4b_SCM", c(sc[1], NA_real_, sc[3]))
    }
  }
  rbindlist(out)
}
cat("ARMS", nrow(arms), "x MEAS", length(MEAS), "CORES", NC, "\n")
RES <- mclapply(seq_len(nrow(arms)), function(i) run_arm(arms$topicset[i], arms$reference[i], arms$rare[i]), mc.cores = NC)
fin <- rbindlist(RES, fill = TRUE)
fin[, main := as.integer(measure=="jsd" & reference=="contemp" & topicset=="all" & rare=="rare")]
fin[, sig := fifelse(is.na(p), "NA", fifelse(p<0.01,"***", fifelse(p<0.05,"**", fifelse(p<0.1,"*","ns"))))]
setcolorder(fin, c("main","measure","reference","topicset","rare","treat_date","spec","estimate","se","p","sig"))
fwrite(fin, file.path(SC, "master_h4_coefs.csv"))
cat("ROWS", nrow(fin), "DONE_H4\n")
