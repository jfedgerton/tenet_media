###############################################################################
# 26_loso.R  --  leave-one-show-out / subset robustness. For every non-empty subset
# of the 5 Tenet feeds (31 configs), re-estimate the MAIN specs for H1-H4 and record
# the headline coefficient, to see whether any single host (or Tim feed) drives results.
#
# Treated = the config's feeds; controls = all non-Tenet analysis shows; Tenet feeds
# NOT in the config are dropped. Treatment date = 2023-10-01 (main). Per-feed panels
# from 25_loso_panel.py (Tim's 3 feeds kept separate).
#
# Specs: H1 {OLS, matched}; H2 {TWFE, SCM}; H3 {TWFE, SCM}; H4 {H4a_OLS, H4a_matched,
# H4b_TWFE, H4b_SCM}. Outcomes: stance score/pos/net x {Russia,Ukraine,Combined};
# H3 prop_{7879,78,79}; H4 jsd. Output: master_loso_coefs.csv
# PI: Jared Edgerton (PSU). Seed 123.
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(Matching); library(quadprog); library(parallel) })
set.seed(123); setDTthreads(1); NC <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "8"))
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); SCM_WIN <- as.Date("2021-01-01"); MINMENT <- 5; MINTOT <- 10
FEEDS <- c("the_benny_show", "the_rubin_report", "timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

P <- fread(file.path(SC, "loso_stance_panel.csv")); P[, month := as.Date(month)]
DV <- fread(file.path(SC, "loso_divergence.csv")); DV[, month := as.Date(month)]
minm <- min(P$month)
aud <- fread(file.path(CO, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
acov <- aud[, .(key, a = mean_audience, e = episodes_per_week, w = weeks_active)]
la <- function(s){ v <- acov[key == norm(s), a]; if(length(v)) log(v[1]) else NA_real_ }

scm_w <- function(Y0p,y1p){n<-ncol(Y0p);D<-t(Y0p)%*%Y0p+diag(1e-8,n);dv<-as.vector(t(Y0p)%*%y1p);A<-cbind(rep(1,n),diag(n));b<-c(1,rep(0,n));tryCatch(solve.QP(D,dv,A,b,meq=1)$solution,error=function(e)rep(1/n,n))}
scm1 <- function(y1,Y0,pre){w<-scm_w(Y0[pre,,drop=F],y1[pre]);g<-y1-as.vector(Y0%*%w);list(r=sqrt(mean(g[!pre]^2))/sqrt(mean(g[pre]^2)),gap=mean(g[!pre]))}
scm <- function(pan,col,wcol){
  dd<-pan[!is.na(get(col))&month>=SCM_WIN];tr<-dd[tenet==1];if(!nrow(tr))return(c(NA,NA))
  comp<-tr[,.(y=weighted.mean(get(col),pmax(get(wcol),1))),by=month];mo<-sort(unique(dd$month));pre<-mo<TREAT
  if(sum(pre)<6||sum(!pre)<2)return(c(NA,NA));y1<-comp[match(mo,comp$month)]$y
  don<-dcast(dd[tenet==0],month~show,value.var=col);don<-don[match(mo,don$month)];dm<-as.matrix(don[,-1])
  good<-which(colSums(is.na(dm))==0&apply(dm,2,sd)>0);if(length(good)<5||any(is.na(y1)))return(c(NA,NA))
  Y0<-dm[,good,drop=F];m<-scm1(y1,Y0,pre);rs<-c();for(j in seq_len(ncol(Y0))){o<-scm1(Y0[,j],Y0[,-j,drop=F],pre);if(is.finite(o$r))rs<-c(rs,o$r)}
  c(m$gap, if(length(rs))(sum(rs>=m$r)+1)/(length(rs)+1) else NA)
}
gT <- function(m,t){ct<-tryCatch(coeftable(m),error=function(e)NULL);if(is.null(ct)||!t%in%rownames(ct))return(c(NA,NA,NA));as.numeric(ct[t,c("Estimate","Std. Error","Pr(>|t|)")])}
stance <- list(c("Russia","score","r_score","n_ment_r"),c("Russia","pos","r_pos","n_ment_r"),c("Russia","net","r_net","n_ment_r"),
  c("Ukraine","score","u_score","n_ment_u"),c("Ukraine","pos","u_pos","n_ment_u"),c("Ukraine","net","u_net","n_ment_u"),
  c("Combined","score","c_score","n_ment_r"),c("Combined","pos","c_pos","n_ment_r"),c("Combined","net","c_net","n_ment_r"))

allshows <- unique(P$show); controls <- setdiff(allshows, FEEDS)
configs <- list(); for(i in 1:31){ sel <- FEEDS[as.logical(intToBits(i)[1:5])]; configs[[length(configs)+1]] <- sel }

run_cfg <- function(tr_feeds){
  cid <- paste(gsub("the_|_show|_report|_podcast_with_tim_pool|_pool_daily_news","",tr_feeds), collapse="+")
  keep <- c(controls, tr_feeds)
  p <- P[show %in% keep]; p[, tenet := as.integer(show %in% tr_feeds)]
  p[, t := as.integer(round(as.numeric(month-minm)/30.4375))]; p[, t2 := t^2]
  p[, post := as.integer(month>=TREAT)]; p[, tp := tenet*post]
  p[, log_aud := sapply(show, la)]
  p[, c_score := r_score-u_score]; p[, c_pos := r_pos-u_pos]; p[, c_net := r_net-u_net]
  p[, prop_7879 := n_ment_r/n_total]; p[, prop_78 := fifelse(n_total_78>0,n_ment_r_78/n_total_78,NA_real_)]; p[, prop_79 := fifelse(n_total_79>0,n_ment_r_79/n_total_79,NA_real_)]
  uc <- unique(p[, .(show, tenet)]); uc[, a:=sapply(show,function(s){v<-acov[key==norm(s),a];if(length(v))v[1] else NA})]
  uc[, e:=sapply(show,function(s){v<-acov[key==norm(s),e];if(length(v))v[1] else NA})]; uc[, w:=sapply(show,function(s){v<-acov[key==norm(s),w];if(length(v))v[1] else NA})]
  uc <- uc[is.finite(log(a))]; X<-as.matrix(uc[,.(la=log(a),e,w)]);X[is.na(X)]<-0
  MU <- tryCatch({mo<-Match(Tr=uc$tenet,X=X,M=3,replace=TRUE);unique(c(uc$show[mo$index.treated],uc$show[mo$index.control]))},error=function(e)uc$show)
  out <- list(); add <- function(...) out[[length(out)+1]] <<- data.table(config=cid, ntreat=length(tr_feeds), ...)
  for(o in stance){ st<-o[1];mt<-o[2];col<-o[3];wc<-o[4]
    if(st=="Combined") d<-p[n_ment_r>=MINMENT&n_ment_u>=MINMENT&!is.na(log_aud)&!is.na(get(col))] else if(st=="Russia") d<-p[n_ment_r>=MINMENT&!is.na(log_aud)&!is.na(get(col))] else d<-p[n_ment_u>=MINMENT&!is.na(log_aud)&!is.na(get(col))]
    pre<-d[post==0];prem<-pre[show%in%MU]
    f1<-as.formula(paste(col,"~ tenet + t + t2 + log_aud"));ftw<-as.formula(paste(col,"~ tp + post:log_aud | show + month"))
    v<-gT(tryCatch(feols(f1,pre,cluster=~show),error=function(e)NULL),"tenet");add(hyp="H1",set=st,metric=mt,spec="OLS",est=v[1],se=v[2],p=v[3])
    v<-gT(tryCatch(feols(f1,prem,cluster=~show),error=function(e)NULL),"tenet");add(hyp="H1",set=st,metric=mt,spec="matched",est=v[1],se=v[2],p=v[3])
    v<-gT(tryCatch(feols(ftw,d,cluster=~show),error=function(e)NULL),"tp");add(hyp="H2",set=st,metric=mt,spec="TWFE",est=v[1],se=v[2],p=v[3])
    sc<-tryCatch(scm(d,col,wc),error=function(e)c(NA,NA));add(hyp="H2",set=st,metric=mt,spec="SCM",est=sc[1],se=NA,p=sc[2])
  }
  for(pc in c("prop_7879","prop_78","prop_79")){ tf<-if(pc=="prop_78")"n_total_78" else if(pc=="prop_79")"n_total_79" else "n_total"
    d<-p[get(tf)>=MINTOT&!is.na(get(pc))&!is.na(log_aud)]
    v<-gT(tryCatch(feols(as.formula(paste(pc,"~ tp + post:log_aud | show + month")),d,cluster=~show),error=function(e)NULL),"tp");add(hyp="H3",set=pc,metric="prop",spec="TWFE",est=v[1],se=v[2],p=v[3])
    sc<-tryCatch(scm(d,pc,tf),error=function(e)c(NA,NA));add(hyp="H3",set=pc,metric="prop",spec="SCM",est=sc[1],se=NA,p=sc[2])
  }
  dv<-DV[show%in%keep];dv[,tenet:=as.integer(show%in%tr_feeds)];dv[,t:=as.integer(round(as.numeric(month-minm)/30.4375))];dv[,t2:=t^2];dv[,post:=as.integer(month>=TREAT)];dv[,tp:=tenet*post];dv[,log_aud:=sapply(show,la)];dv[,log_n:=log(n_sentences)];dv[,n_total:=n_sentences]
  pre<-dv[post==0&!is.na(log_aud)];prem<-pre[show%in%MU]
  v<-gT(tryCatch(feols(jsd~tenet+t+t2+log_aud+log_n,pre,cluster=~show),error=function(e)NULL),"tenet");add(hyp="H4a",set="agenda",metric="jsd",spec="OLS",est=v[1],se=v[2],p=v[3])
  v<-gT(tryCatch(feols(jsd~tenet+t+t2+log_aud+log_n,prem,cluster=~show),error=function(e)NULL),"tenet");add(hyp="H4a",set="agenda",metric="jsd",spec="matched",est=v[1],se=v[2],p=v[3])
  v<-gT(tryCatch(feols(jsd~tp+post:log_aud+log_n|show+month,dv[!is.na(log_aud)],cluster=~show),error=function(e)NULL),"tp");add(hyp="H4b",set="agenda",metric="jsd",spec="TWFE",est=v[1],se=v[2],p=v[3])
  d4<-dv[!is.na(log_aud)];setnames(d4,"jsd","jsd",skip_absent=TRUE);sc<-tryCatch(scm(d4,"jsd","n_total"),error=function(e)c(NA,NA));add(hyp="H4b",set="agenda",metric="jsd",spec="SCM",est=sc[1],se=NA,p=sc[2])
  rbindlist(out)
}
RES <- mclapply(configs, run_cfg, mc.cores=NC)
fin <- rbindlist(RES, fill=TRUE)
fin[, sig := fifelse(is.na(p),"NA",fifelse(p<0.01,"***",fifelse(p<0.05,"**",fifelse(p<0.1,"*","ns"))))]
fwrite(fin, file.path(SC, "master_loso_coefs.csv"))
cat("CONFIGS", length(configs), "ROWS", nrow(fin), "DONE_LOSO\n")
