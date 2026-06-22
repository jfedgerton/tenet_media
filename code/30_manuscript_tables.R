###############################################################################
# 30_manuscript_tables.R  --  formatted LaTeX manuscript tables (Table 1/2/3)
# from the saved main_*.csv that 13/15 write. Cells = estimate with significance
# stars and the clustered p-value in parentheses.
#   Table 1  (tab_main1.tex)  H1 SELECTION  -- pre-payment level, 4 specs
#   Table 2  (tab_main2.tex)  H2 + H3       -- post-payment stance DiD & agenda
#   Table 3  (tab_main3.tex)  H4            -- agenda divergence (level + DiD)
# Stars: *** p<.01, ** p<.05, * p<.1.  Seed 123.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table) })
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")

cell <- function(est, p){
  if (is.na(est)) return("--")
  st <- if (is.na(p)) "" else if (p < 0.01) "$^{***}$" else if (p < 0.05) "$^{**}$" else if (p < 0.1) "$^{*}$" else ""
  sprintf("%.3f%s (%.3f)", est, st, p)
}
writetab <- function(lines, file){ writeLines(lines, file.path(SC, file)); cat("WROTE", file, "\n") }

## ---- TABLE 1 : H1 selection -------------------------------------------------
H1 <- fread(file.path(SC, "main_h1.csv"))
b1 <- character(0)
for (i in seq_len(nrow(H1))){ r <- H1[i]
  b1 <- c(b1, paste(r$outcome, cell(r$est_simple,r$p_simple), cell(r$est_simpleM,r$p_simpleM),
                    cell(r$est_ctrl,r$p_ctrl), cell(r$est_ctrlM,r$p_ctrlM), sep = " & "), "\\\\")
}
t1 <- c("% requires \\usepackage{booktabs}",
  "\\begin{table}[!ht]\\centering",
  "\\caption{H1: pre-payment selection. Each cell is the Tenet--control level difference (treated shows' stance before any payment), with the two-way clustered $p$-value in parentheses. Stance outcomes use show-months with $\\geq5$ target mentions; month fixed effects; SE clustered by month and unit.}",
  "\\label{tab:h1}", "\\small",
  "\\begin{tabular}{l cccc}", "\\toprule",
  "Outcome & Simple & Matched & +Controls & +Ctrl/Matched \\\\", "\\midrule",
  paste(b1, collapse = "\n"),
  "\\bottomrule", "\\end{tabular}",
  "\\begin{tablenotes}\\footnotesize\\item Controls: log total words and log monthly audience. $^{***}p<.01,\\ ^{**}p<.05,\\ ^{*}p<.1$.\\end{tablenotes}",
  "\\end{table}")
writetab(t1, "tab_main1.tex")

## ---- TABLE 2 : H2 (post-payment stance DiD) + H3 (agenda) -------------------
mk_did <- function(DT){ b <- character(0)
  for (i in seq_len(nrow(DT))){ r <- DT[i]
    b <- c(b, paste(r$outcome, cell(r$est_twfe,r$p_twfe), cell(r$est_twfe_ctrl,r$p_twfe_ctrl),
                    cell(r$est_twfeM,r$p_twfeM), cell(r$est_scm,r$p_scm), sep = " & "), "\\\\") }
  b }
H2 <- fread(file.path(SC, "main_h2.csv")); H3 <- fread(file.path(SC, "main_h3.csv"))
t2 <- c("% requires \\usepackage{booktabs}",
  "\\begin{table}[!ht]\\centering",
  "\\caption{H2/H3: post-payment difference-in-differences. Each cell is the treated$\\times$post coefficient (the payment effect) with the two-way clustered $p$-value in parentheses. Unit and month fixed effects; SE clustered by unit and month. No robust effect = amplification, not conversion.}",
  "\\label{tab:h2h3}", "\\small",
  "\\begin{tabular}{l cccc}", "\\toprule",
  "Outcome & TWFE & +Controls & Matched & Synth. control \\\\",
  "\\midrule \\multicolumn{5}{l}{\\textit{Panel A. H2 -- stance}} \\\\",
  paste(mk_did(H2), collapse = "\n"),
  "\\midrule \\multicolumn{5}{l}{\\textit{Panel B. H3 -- agenda share}} \\\\",
  paste(mk_did(H3), collapse = "\n"),
  "\\bottomrule", "\\end{tabular}",
  "\\begin{tablenotes}\\footnotesize\\item Controls: log words, log monthly audience. $^{***}p<.01,\\ ^{**}p<.05,\\ ^{*}p<.1$.\\end{tablenotes}",
  "\\end{table}")
writetab(t2, "tab_main2.tex")

## ---- TABLE 3 : H4 agenda divergence (level + DiD) ---------------------------
H4a <- fread(file.path(SC, "main_h4a.csv")); H4b <- fread(file.path(SC, "main_h4b.csv"))
ba <- character(0)
for (i in seq_len(nrow(H4a))){ r <- H4a[i]
  ba <- c(ba, paste(r$measure, cell(r$est_simple,r$p_simple), cell(r$est_simpleM,r$p_simpleM),
                    cell(r$est_ctrl,r$p_ctrl), cell(r$est_ctrlM,r$p_ctrlM), sep = " & "), "\\\\") }
bb <- character(0)
for (i in seq_len(nrow(H4b))){ r <- H4b[i]
  bb <- c(bb, paste(r$measure, cell(r$est_twfe,r$p_twfe), cell(r$est_twfe_ctrl,r$p_twfe_ctrl),
                    cell(r$est_twfeM,r$p_twfeM), cell(r$est_scm,r$p_scm), sep = " & "), "\\\\") }
t3 <- c("% requires \\usepackage{booktabs}",
  "\\begin{table}[!ht]\\centering",
  "\\caption{H4: agenda divergence from the contemporaneous conservative-podcast distribution (JSD, smoothed KL, cosine distance). Panel A is the pre-payment level (Tenet--control); Panel B is the treated$\\times$post DiD. Negative DiD = post-payment convergence toward the broader agenda.}",
  "\\label{tab:h4}", "\\small",
  "\\begin{tabular}{l cccc}", "\\toprule",
  "\\multicolumn{5}{l}{\\textit{Panel A. Level (H4a)}} \\\\",
  "Measure & Simple & Matched & +Controls & +Ctrl/Matched \\\\", "\\midrule",
  paste(ba, collapse = "\n"),
  "\\midrule \\multicolumn{5}{l}{\\textit{Panel B. DiD (H4b)}} \\\\",
  "Measure & TWFE & +Controls & Matched & Synth. control \\\\", "\\midrule",
  paste(bb, collapse = "\n"),
  "\\bottomrule", "\\end{tabular}",
  "\\begin{tablenotes}\\footnotesize\\item Controls: log words, log monthly audience. $^{***}p<.01,\\ ^{**}p<.05,\\ ^{*}p<.1$.\\end{tablenotes}",
  "\\end{table}")
writetab(t3, "tab_main3.tex")
cat("DONE manuscript tables 1-3\n")
