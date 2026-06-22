###############################################################################
# 30_make_tables.R  --  manuscript regression tables (LaTeX, booktabs) from the
# result CSVs written by 13_main_h1h3.R and 15_main_h4.R. No model refits.
#
#   table1_h1.tex   H1 SELECTION (pre-payment level): 9 outcomes x 4 specs
#   table2_h2h3.tex H2 STANCE DiD (9 outcomes) + H3 AGENDA DiD (3 outcomes): 6 specs
#   table3_h4.tex   H4 DIVERGENCE: H4a level (4 specs) + H4b DiD (6 specs)
#
# Each cell = point estimate with significance stars; p-value in parentheses below.
# Stars: *** p<.01, ** p<.05, * p<.10.  PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table) })
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")

star <- function(p) ifelse(is.na(p), "", ifelse(p < .01, "***", ifelse(p < .05, "**", ifelse(p < .10, "*", ""))))
fe   <- function(e, p) ifelse(is.na(e), "", sprintf("%.3f%s", e, star(p)))
fp   <- function(p) ifelse(is.na(p), "", ifelse(p < .001, "($<$.001)", sprintf("(%.3f)", p)))

## generic: dt with a name column + (est_col,p_col) pairs -> booktabs LaTeX body
make_tex <- function(dt, namecol, est_cols, p_cols, col_labels, caption, lab, colspec, group_hdr = NULL) {
  body <- character(0)
  for (i in seq_len(nrow(dt))) {
    r <- dt[i]
    ests <- vapply(seq_along(est_cols), function(j) fe(as.numeric(r[[est_cols[j]]]), as.numeric(r[[p_cols[j]]])), "")
    ps   <- vapply(seq_along(p_cols),   function(j) fp(as.numeric(r[[p_cols[j]]])), "")
    body <- c(body, paste0(r[[namecol]], " & ", paste(ests, collapse = " & "), " \\\\"),
                    paste0(" & ", paste(ps, collapse = " & "), " \\\\[2pt]"))
  }
  hdr <- paste0(" & ", paste(col_labels, collapse = " & "), " \\\\")
  c("% requires \\usepackage{booktabs}", "\\begin{table}[!ht]\\centering", paste0("\\caption{", caption, "}"),
    paste0("\\label{", lab, "}"), "\\small", paste0("\\begin{tabular}{", colspec, "}"), "\\toprule",
    if (!is.null(group_hdr)) group_hdr, hdr, "\\midrule", body, "\\bottomrule", "\\end{tabular}",
    "\\begin{tablenotes}\\footnotesize\\item Significance: *** $p<.01$, ** $p<.05$, * $p<.10$. $p$-values in parentheses.\\end{tablenotes}",
    "\\end{table}")
}

## ---- TABLE 1: H1 selection --------------------------------------------------
H1 <- fread(file.path(SC, "main_h1.csv"))
t1 <- make_tex(H1, "outcome",
  est_cols = c("est_simple","est_simpleM","est_ctrl","est_ctrlM"),
  p_cols   = c("p_simple","p_simpleM","p_ctrl","p_ctrlM"),
  col_labels = c("Simple","Simple (matched)","+Controls","+Controls (matched)"),
  caption = "H1 (selection): pre-payment level difference, Tenet vs. control. Month fixed effects; SE two-way clustered by month and unit. Outcomes are stance among $\\geq 5$ Russia-mention sentences.",
  lab = "tab:h1", colspec = "l cccc")
writeLines(t1, file.path(SC, "table1_h1.tex"))

## ---- TABLE 2: H2 stance DiD + H3 agenda DiD ---------------------------------
H2 <- fread(file.path(SC, "main_h2.csv")); H2[, block := "Stance (H2)"]
H3 <- fread(file.path(SC, "main_h3.csv")); H3[, block := "Agenda (H3)"]
H23 <- rbind(H2, H3, fill = TRUE)
ec <- c("est_twfe","est_twfe_ctrl","est_twfeM","est_twfeM_ctrl","est_scm","est_scm_ctrl")
pc <- c("p_twfe","p_twfe_ctrl","p_twfeM","p_twfeM_ctrl","p_scm","p_scm_ctrl")
cl <- c("TWFE","TWFE+ctrl","TWFE (M)","TWFE+ctrl (M)","SCM","SCM+ctrl")
# build body with a block separator between H2 and H3
body23 <- character(0)
for (blk in c("Stance (H2)","Agenda (H3)")) {
  body23 <- c(body23, paste0("\\multicolumn{7}{l}{\\textit{", blk, "}} \\\\"))
  sub <- H23[block == blk]
  for (i in seq_len(nrow(sub))) { r <- sub[i]
    ests <- vapply(seq_along(ec), function(j) fe(as.numeric(r[[ec[j]]]), as.numeric(r[[pc[j]]])), "")
    ps   <- vapply(seq_along(pc), function(j) fp(as.numeric(r[[pc[j]]])), "")
    body23 <- c(body23, paste0(r$outcome, " & ", paste(ests, collapse=" & "), " \\\\"),
                        paste0(" & ", paste(ps, collapse=" & "), " \\\\[2pt]")) }
}
t2 <- c("% requires \\usepackage{booktabs}", "\\begin{table}[!ht]\\centering",
  "\\caption{H2 (stance amplification) and H3 (agenda) difference-in-differences: treated $\\times$ post. Unit and month fixed effects; SE two-way clustered by unit and month. SCM = synthetic control with in-space placebo $p$.}",
  "\\label{tab:h2h3}", "\\footnotesize", "\\begin{tabular}{l cccccc}", "\\toprule",
  paste0(" & ", paste(cl, collapse=" & "), " \\\\"), "\\midrule", body23, "\\bottomrule", "\\end{tabular}",
  "\\begin{tablenotes}\\footnotesize\\item Significance: *** $p<.01$, ** $p<.05$, * $p<.10$. $p$-values in parentheses. (M) = matched donor set.\\end{tablenotes}",
  "\\end{table}")
writeLines(t2, file.path(SC, "table2_h2h3.tex"))

## ---- TABLE 3: H4 divergence (level + DiD) -----------------------------------
H4a <- fread(file.path(SC, "main_h4a.csv"))
t3a <- make_tex(H4a, "measure",
  est_cols = c("est_simple","est_simpleM","est_ctrl","est_ctrlM"),
  p_cols   = c("p_simple","p_simpleM","p_ctrl","p_ctrlM"),
  col_labels = c("Simple","Simple (M)","+Controls","+Controls (M)"),
  caption = "H4a (agenda divergence, pre-payment level): treated vs. control.",
  lab = "tab:h4a", colspec = "l cccc")
writeLines(t3a, file.path(SC, "table3a_h4a.tex"))
H4b <- fread(file.path(SC, "main_h4b.csv"))
t3b <- make_tex(H4b, "measure",
  est_cols = c("est_twfe","est_twfe_ctrl","est_twfeM","est_twfeM_ctrl","est_scm","est_scm_ctrl"),
  p_cols   = c("p_twfe","p_twfe_ctrl","p_twfeM","p_twfeM_ctrl","p_scm","p_scm_ctrl"),
  col_labels = c("TWFE","TWFE+ctrl","TWFE (M)","TWFE+ctrl (M)","SCM","SCM+ctrl"),
  caption = "H4b (agenda divergence, post-payment DiD): treated $\\times$ post. Negative = treated converge toward the contemporaneous agenda.",
  lab = "tab:h4b", colspec = "l cccccc")
writeLines(t3b, file.path(SC, "table3b_h4b.tex"))

cat("WROTE table1_h1.tex, table2_h2h3.tex, table3a_h4a.tex, table3b_h4b.tex\n")
