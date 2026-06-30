###############################################################################
# 27_descriptives.R  --  descriptive statistics table for outcomes + IVs.
# Builds the SAME show-month panel as 13_main_h1h3.R (identical variable
# construction), then writes a treated-vs-control descriptives table to
#   data/sc_results/tab_descriptives.tex   (LaTeX, booktabs)
#   data/sc_results/tab_descriptives.csv   (machine-readable)
# Pre-payment window only (the H1 comparison window). Seed 123. PI: Jared Edgerton.
###############################################################################
suppressMessages({ library(data.table) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01")
MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny

## ---- panel build (mirrors 13_main_h1h3.R) -----------------------------------
P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
P[, tenet := as.integer(unit %in% TRU)]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", fifelse(show %in% BEN, "the_benny_show", show))]
Vunit <- V[, .(n_words = mean(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit", "month"), all.x = TRUE); P[, log_words := log(n_words)]
AM <- fread(file.path(SC, "audience_monthly.csv")); AM[, month := as.Date(month)]
P <- merge(P, AM[, .(unit, month, aud_mid)], by = c("unit", "month"), all.x = TRUE); P[, log_aud_m := log(aud_mid)]
P[, prop_rus := n_ment_r / n_words]; P[, prop_ukr := n_ment_u / n_words]; P[, prop_comb := (n_ment_r + n_ment_u) / n_words]

## restrict to the pre-payment H1 window
D <- P[month < TREAT]

## ---- variable dictionary (label, column, scope) -----------------------------
# stance outcomes are only defined among a target's mentioned sentences, so we
# summarize them on cells with >= MINMENT Russia mentions (the H1 estimation set).
vars <- list(
  c("Russia stance score (p_pos - p_neg)", "r_score",  "ment"),
  c("Russia positive rate",                "r_pos",    "ment"),
  c("Russia net stance (ordinal)",         "r_net",    "ment"),
  c("Ukraine stance score",                "u_score",  "ment"),
  c("Ukraine positive rate",               "u_pos",    "ment"),
  c("Ukraine net stance (ordinal)",        "u_net",    "ment"),
  c("Combined stance score (R - U)",       "c_score",  "ment"),
  c("Combined positive rate (R - U)",      "c_pos",    "ment"),
  c("Combined net stance (R - U)",         "c_net",    "ment"),
  c("Russia agenda share",                 "prop_rus", "all"),
  c("Ukraine agenda share",                "prop_ukr", "all"),
  c("Combined agenda share",               "prop_comb","all"),
  c("log total words (volume)",            "log_words","all"),
  c("log monthly audience",                "log_aud_m","all"),
  c("Russia-mention sentences (n)",        "n_ment_r", "all"),
  c("Total sentences (n)",                 "n_total",  "all"))

summ <- function(x){ x <- x[is.finite(x)]; c(mean(x), sd(x), min(x), max(x), length(x)) }
rowfor <- function(lbl, col, scope){
  base <- if (scope == "ment") D[n_ment_r >= MINMENT] else D
  tr <- summ(base[tenet == 1][[col]]); co <- summ(base[tenet == 0][[col]])
  data.table(Variable = lbl,
             T_mean = tr[1], T_sd = tr[2], T_min = tr[3], T_max = tr[4], T_N = tr[5],
             C_mean = co[1], C_sd = co[2], C_min = co[3], C_max = co[4], C_N = co[5])
}
TAB <- rbindlist(lapply(vars, function(v) rowfor(v[1], v[2], v[3])))
fwrite(TAB, file.path(SC, "tab_descriptives.csv"))

## ---- LaTeX (booktabs) -------------------------------------------------------
fnum <- function(x, d = 3) ifelse(is.na(x), "", formatC(x, format = "f", digits = d))
fint <- function(x) ifelse(is.na(x), "", formatC(round(x), format = "d", big.mark = ","))
body <- character(0)
for (i in seq_len(nrow(TAB))){ r <- TAB[i]
  body <- c(body, paste0(paste(r$Variable,
    fnum(r$T_mean), fnum(r$T_sd), fnum(r$T_min), fnum(r$T_max), fint(r$T_N),
    fnum(r$C_mean), fnum(r$C_sd), fnum(r$C_min), fnum(r$C_max), fint(r$C_N),
    sep = " & "), " \\\\")) }
lines <- c(
  "% requires \\usepackage{booktabs}",
  "\\begin{table}[!ht]\\centering",
  "\\caption{Descriptive statistics, pre-payment window (2018-01 to 2023-09). Treated = Benny Johnson, Dave Rubin, Tim Pool (pooled); Control = remaining conservative podcasts. Stance outcomes are summarized on show-months with $\\geq 5$ Russia-mention sentences.}",
  "\\label{tab:descriptives}", "\\small",
  "\\begin{tabular}{l rrrr r rrrr r}", "\\toprule",
  " & \\multicolumn{5}{c}{Treated (Tenet)} & \\multicolumn{5}{c}{Control} \\\\",
  "\\cmidrule(lr){2-6}\\cmidrule(lr){7-11}",
  "Variable & Mean & SD & Min & Max & $N$ & Mean & SD & Min & Max & $N$ \\\\",
  "\\midrule", body, "\\bottomrule", "\\end{tabular}", "\\end{table}")
writeLines(lines, file.path(SC, "tab_descriptives.tex"))
cat("WROTE tab_descriptives.{csv,tex}  rows =", nrow(TAB), "\n")
