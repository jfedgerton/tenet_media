###############################################################################
# 21_h3_topic_grid.R  --  topic mass-transfer robustness grid for H3 (agenda:
# share of discussion devoted to the Russia/Ukraine topics). Topic analog of
# 19_probshift_grid.R; reuses the same TWFE + SCM (in-space placebo) machinery.
#
# Mechanic (per candidate sentence; from 20_topic_distribution.py we have
#   p78, p79, p_nn78, p_nn79, p_rest_max  = the only quantities that determine
#   whether a sentence's argmax topic is 78, 79, or neither under a transfer):
#   for a relevant topic T (78 or 79) and its nearest-neighbor N, shift s:
#     s < 0  (out): move m = min(|s|, p_T) from T -> N
#     s > 0  (in) : move m = min( s , p_N) from N -> T
#   then re-argmax over {p78, p79, p_nn78, p_nn79, p_rest_max}. Applied to
#   {78}, {79}, and {both}. s in seq(-0.10, 0.10, 0.01).
#
# Outcomes = topic SHARE of ALL discussion (denominator = every sentence, from
#   h3_ntotal.csv): prop_78, prop_79, prop_combined (= (78 or 79)/n_total).
# Treatment dates: 2023-10-01 (first payment), 2023-11-01 (join/launch).
# Window already truncated at the indictment (Aug 2024) upstream in 20.
# Specs: H3_TWFE (y ~ tp + post:log_aud | unit+month) and H3_SCM (composite vs
#   donors, quadprog + in-space placebo).  PI: Jared Edgerton (PSU). Seed 123.
###############################################################################

suppressMessages({ library(data.table); library(fixest); library(quadprog); library(parallel) })
set.seed(123)
setDTthreads(1)
NC <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "8"))

COLLAB <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(COLLAB, "data", "sc_results")
TREAT_DATES <- as.Date(c("2023-10-01", "2023-11-01"))
SCM_WIN <- as.Date("2021-01-01"); MINTOT <- 10
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny
norm <- function(x) gsub("[^a-z0-9]", "", tolower(x))

## ---- inputs ----
C <- fread(file.path(SC, "topic_cand_probs.csv")); C[, month := as.Date(month)]
NT <- fread(file.path(SC, "h3_ntotal.csv")); NT[, month := as.Date(month)]
minm <- min(NT$month)
cu <- C$unit; cm <- C$month
P78 <- C$p78; P79 <- C$p79; PN78 <- C$p_nn78; PN79 <- C$p_nn79; PR <- C$p_rest_max

## ---- audience + matched donor set (unit level; same as 19) ----
aud <- fread(file.path(COLLAB, "data", "show_data", "treated_terminal_blocks_weightedDecay.csv"))
aud[, key := norm(title)]; aud <- aud[!is.na(mean_audience)]
al <- function(s) { v <- aud[key == norm(s), mean_audience]; if (length(v) == 0) NA_real_ else v[1] }
units <- unique(NT$unit)
ua <- vapply(units, function(u) if (u == "tim_pool") sum(sapply(TIM, al), na.rm = TRUE) else al(u), numeric(1))
umeta <- data.table(unit = units, mean_audience = ua); umeta[, log_aud := log(mean_audience)]
umeta[, treated := as.integer(unit %in% TRU)]
# time-varying monthly audience (Jon Green) -> log_aud_m, merged by unit-month (match 13/15)
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
AM <- AM[, .(unit, month, log_aud_m = log(aud_mid))]

## ---- SCM (quadprog + in-space placebo), treat date a parameter (same as 19) ----
scm_weights <- function(Y0pre, y1pre) { n <- ncol(Y0pre); Dmat <- t(Y0pre) %*% Y0pre + diag(1e-8, n); dvec <- as.vector(t(Y0pre) %*% y1pre); Amat <- cbind(rep(1, n), diag(n)); bvec <- c(1, rep(0, n)); tryCatch(solve.QP(Dmat, dvec, Amat, bvec, meq = 1)$solution, error = function(e) rep(1/n, n)) }
scm_one <- function(y1, Y0, pre) { w <- scm_weights(Y0[pre, , drop = FALSE], y1[pre]); g <- y1 - as.vector(Y0 %*% w); list(ratio = sqrt(mean(g[!pre]^2)) / sqrt(mean(g[pre]^2)), gap = mean(g[!pre])) }
scm_outcome <- function(pan, col, treat) {
  dd <- pan[!is.na(get(col)) & month >= SCM_WIN]; tr <- dd[treated == 1]; if (nrow(tr) == 0) return(c(NA, NA, NA))
  comp <- tr[, .(y = weighted.mean(get(col), pmax(n_total, 1))), by = month]
  months <- sort(unique(dd$month)); pre <- months < treat
  if (sum(pre) < 6 || sum(!pre) < 2) return(c(NA, NA, NA))
  y1 <- comp[match(months, comp$month)]$y
  don <- dcast(dd[treated == 0], month ~ unit, value.var = col); don <- don[match(months, don$month)]; dm <- as.matrix(don[, -1])
  good <- which(colSums(is.na(dm)) == 0 & apply(dm, 2, sd) > 0); if (length(good) < 5 || any(is.na(y1))) return(c(NA, NA, NA))
  Y0 <- dm[, good, drop = FALSE]; main <- scm_one(y1, Y0, pre)
  ratios <- c(); for (j in seq_len(ncol(Y0))) { o <- scm_one(Y0[, j], Y0[, -j, drop = FALSE], pre); if (is.finite(o$ratio)) ratios <- c(ratios, o$ratio) }
  pval <- if (length(ratios)) (sum(ratios >= main$ratio) + 1) / (length(ratios) + 1) else NA
  c(main$gap, main$ratio, pval)
}
grabT <- function(m, term) { ct <- tryCatch(coeftable(m), error = function(e) NULL); if (is.null(ct) || !term %in% rownames(ct)) return(c(NA, NA, NA)); as.numeric(ct[term, c("Estimate", "Std. Error", "Pr(>|t|)")]) }

TARGETS <- list(t78 = c(78L), t79 = c(79L), both = c(78L, 79L))
OUT <- list(c("prop_78", "n78"), c("prop_79", "n79"), c("prop_comb", "ncomb"))

run_cell <- function(tname, s) {
  p78 <- P78; p79 <- P79; pn78 <- PN78; pn79 <- PN79
  for (T in TARGETS[[tname]]) {
    if (T == 78L) { if (s < 0) { m <- pmin(-s, p78); p78 <- p78 - m; pn78 <- pn78 + m } else { m <- pmin(s, pn78); pn78 <- pn78 - m; p78 <- p78 + m } }
    else          { if (s < 0) { m <- pmin(-s, p79); p79 <- p79 - m; pn79 <- pn79 + m } else { m <- pmin(s, pn79); pn79 <- pn79 - m; p79 <- p79 + m } }
  }
  in78 <- p78 >= p79 & p78 >= pn78 & p78 >= pn79 & p78 >= PR
  in79 <- (!in78) & p79 >= p78 & p79 >= pn78 & p79 >= pn79 & p79 >= PR
  ag <- data.table(unit = cu, month = cm, in78 = in78, in79 = in79)[
    , .(n78 = sum(in78), n79 = sum(in79)), by = .(unit, month)]
  pan <- merge(NT, ag, by = c("unit", "month"), all.x = TRUE)
  pan[is.na(n78), n78 := 0L]; pan[is.na(n79), n79 := 0L]; pan[, ncomb := n78 + n79]
  pan[, prop_78 := n78 / n_total]; pan[, prop_79 := n79 / n_total]; pan[, prop_comb := ncomb / n_total]
  pan <- merge(pan, umeta[, .(unit, treated)], by = "unit", all.x = TRUE)
  pan <- merge(pan, AM, by = c("unit", "month"), all.x = TRUE)        # time-varying audience
  pan[, log_ntot := log(n_total)]                                      # volume control (match 13/15)
  pan[, tenet := treated]
  res <- list(); k <- 0L
  for (td in TREAT_DATES) {
    pan[, post := as.integer(month >= td)]; pan[, tp := tenet * post]
    for (o in OUT) {
      col <- o[1]
      d <- pan[n_total >= MINTOT & is.finite(log_aud_m)]
      v <- grabT(tryCatch(feols(as.formula(paste(col, "~ tp + log_ntot + log_aud_m | unit + month")), d, cluster = ~unit+month), error = function(e) NULL), "tp")
      k <- k + 1L; res[[k]] <- data.table(target = tname, shift = s, treat_date = as.character(td), outcome = col, spec = "H3_TWFE", estimate = v[1], se = v[2], p = v[3])
      sc <- tryCatch(scm_outcome(d, col, td), error = function(e) c(NA, NA, NA))
      k <- k + 1L; res[[k]] <- data.table(target = tname, shift = s, treat_date = as.character(td), outcome = col, spec = "H3_SCM", estimate = sc[1], se = NA_real_, p = sc[3])
    }
  }
  rbindlist(res)
}

grid <- as.data.table(expand.grid(target = names(TARGETS), s = round(seq(-0.10, 0.10, 0.01), 2), stringsAsFactors = FALSE))
cat("CELLS", nrow(grid), "CORES", NC, "\n")
RES <- mclapply(seq_len(nrow(grid)), function(i) run_cell(grid$target[i], grid$s[i]), mc.cores = NC)
fin <- rbindlist(RES, fill = TRUE)
fin[, sig := fifelse(is.na(p), "NA", fifelse(p < 0.01, "***", fifelse(p < 0.05, "**", fifelse(p < 0.1, "*", "ns"))))]
fwrite(fin, file.path(SC, "master_h3_topicshift_coefs.csv"))
cat("ROWS", nrow(fin), "DONE_H3\n")
