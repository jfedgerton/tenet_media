###############################################################################
# 18_label_noise.R  --  label-perturbation robustness for H1/H2, in R (ports the
# old 18_label_noise.py so every regression is in R and runs interactively).
#
# Two families of perturbation to the discrete stance LABELS of mentioned
# Russia/Ukraine sentences, then re-aggregate and re-estimate H1 + H2:
#   (A) DETERMINISTIC recodes: neu->pos, pos->neu, neg->neu, neu->neg
#   (B) RANDOM flips: reassign 5% / 10% / 20% of mentioned labels to a DIFFERENT
#       class (uniform over the other two), over seeds {123,124,125}.
#
# Label-derived outcomes only (pos rate, net ordinal) for Russia / Ukraine /
# Combined (= Russia - Ukraine); the probability `score` is unaffected by label
# moves (covered by 16_grid_h1h2). Tim's three feeds pooled to tim_pool.
# Treatment 2023-10-01. Reads the labeled parquet via `arrow`.
# Output: master_labelnoise_coefs.csv.  Seed 123.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(fixest); library(arrow) })
set.seed(123)

CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); START <- as.Date("2018-01-01")
MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
CLASSES <- c("positive", "negative", "neutral"); ORD <- c(positive = 1, neutral = 0, negative = -1)

## ---- load sentence-level 4-class stance labels ------------------------------
S <- as.data.table(read_parquet(file.path(SC, "opus_c0_corpus_labeled.parquet"),
       col_select = c("show", "date", "russia_label", "ukraine_label")))
S[, date := as.Date(date)]; S <- S[!is.na(date) & date >= START & date < TRUNC]
S[, month := as.Date(format(date, "%Y-%m-01"))]
S[, unit := fifelse(show %in% TIM, "tim_pool", show)]

## ---- label transforms -------------------------------------------------------
recode <- function(lab, rule) {
  if (rule == "neu2pos") lab[lab == "neutral"]  <- "positive"
  else if (rule == "pos2neu") lab[lab == "positive"] <- "neutral"
  else if (rule == "neg2neu") lab[lab == "negative"] <- "neutral"
  else if (rule == "neu2neg") lab[lab == "neutral"]  <- "negative"
  lab
}
flip <- function(lab, frac, seed) {
  set.seed(seed); ment <- which(lab %in% CLASSES); k <- round(frac * length(ment))
  if (k == 0) return(lab)
  pick <- sample(ment, k)
  lab[pick] <- vapply(lab[pick], function(c0) sample(setdiff(CLASSES, c0), 1), character(1))
  lab
}

## ---- one scenario -> H1 + H2 over the 6 label-derived outcomes ---------------
run_scenario <- function(rl, ul, tag) {
  d <- data.table(unit = S$unit, month = S$month, rl = rl, ul = ul)
  d[, rment := rl %in% CLASSES]; d[, ument := ul %in% CLASSES]
  aggR <- d[rment == TRUE, .(n_ment_r = .N, r_pos = mean(rl == "positive"), r_net = mean(ORD[rl])), by = .(unit, month)]
  aggU <- d[ument == TRUE, .(n_ment_u = .N, u_pos = mean(ul == "positive"), u_net = mean(ORD[ul])), by = .(unit, month)]
  nT   <- d[, .(n_total = .N), by = .(unit, month)]
  p <- merge(merge(aggR, aggU, by = c("unit","month"), all = TRUE), nT, by = c("unit","month"), all = TRUE)
  p[, c_pos := r_pos - u_pos]; p[, c_net := r_net - u_net]
  p[, tenet := as.integer(unit %in% TRU)]; p[, mfac := factor(month)]
  p[, t := as.integer(round(as.numeric(month - min(month))/30.4375))]; p[, t2 := t^2]
  p[, post := as.integer(month >= TREAT)]; p[, tp := tenet * post]; p[, log_vol := log(n_total)]
  outs <- list(c("Russia","pos","r_pos","n_ment_r"), c("Russia","net","r_net","n_ment_r"),
               c("Ukraine","pos","u_pos","n_ment_u"), c("Ukraine","net","u_net","n_ment_u"),
               c("Combined","pos","c_pos","n_ment_r"), c("Combined","net","c_net","n_ment_r"))
  rows <- list()
  for (o in outs) {
    set <- o[1]; met <- o[2]; col <- o[3]; mc <- o[4]
    if (set == "Combined") dd <- p[n_ment_r >= MINMENT & n_ment_u >= MINMENT & is.finite(get(col))]
    else dd <- p[get(mc) >= MINMENT & is.finite(get(col))]
    pre <- dd[post == 0]
    h1 <- tryCatch(feols(as.formula(paste(col, "~ tenet + log_vol | mfac")), pre, cluster = ~unit), error = function(e) NULL)
    h2 <- tryCatch(feols(as.formula(paste(col, "~ tp + post:log_vol | unit + month")), dd, cluster = ~unit), error = function(e) NULL)
    g <- function(m, term) if (is.null(m)) c(NA,NA) else { ct <- coeftable(m); if (term %in% rownames(ct)) ct[term, c("Estimate","Pr(>|t|)")] else c(NA,NA) }
    v1 <- g(h1, "tenet"); v2 <- g(h2, "tp")
    rows[[length(rows)+1]] <- data.table(scenario = tag, set = set, metric = met,
      H1_est = v1[1], H1_p = v1[2], H2_est = v2[1], H2_p = v2[2])
  }
  rbindlist(rows)
}

## ---- scenarios: baseline + deterministic recodes + random flips -------------
res <- list()
res[[length(res)+1]] <- run_scenario(S$russia_label, S$ukraine_label, "baseline")
for (rule in c("neu2pos","pos2neu","neg2neu","neu2neg"))
  res[[length(res)+1]] <- run_scenario(recode(copy(S$russia_label), rule), recode(copy(S$ukraine_label), rule), paste0("recode_", rule))
for (frac in c(0.05, 0.10, 0.20)) for (sd in c(123, 124, 125))
  res[[length(res)+1]] <- run_scenario(flip(copy(S$russia_label), frac, sd), flip(copy(S$ukraine_label), frac, sd + 1),
                                       sprintf("flip%02d_s%d", as.integer(frac*100), sd))
fin <- rbindlist(res)
fwrite(fin, file.path(SC, "master_labelnoise_coefs.csv"))
print(fin); cat("DONE_LABELNOISE_R", nrow(fin), "\n")
