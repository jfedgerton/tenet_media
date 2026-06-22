###############################################################################
# 31_ranked_prepost.R  --  STANDALONE exploratory figure (separate from 29 so you
# can judge how it renders). Ranked lollipop of every program, faceted
#   rows    = measure  {Russia mention share, Russia score, Russia pos,
#                        Combined score, Combined pos}
#   columns = period   {Pre-payment, Post-payment}  (split at 2023-10-01)
# Each program is one lollipop; the 3 Tenet shows are highlighted (red, enlarged).
# Output: data/sc_results/figH_ranked_prepost.pdf (+ _data.csv).  Seed 123.
# PI: Jared Edgerton (PSU).
###############################################################################
suppressMessages({ library(data.table); library(ggplot2) })
set.seed(123)
CO <- "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC <- file.path(CO, "data", "sc_results")
TREAT <- as.Date("2023-10-01"); TRUNC <- as.Date("2024-09-01"); MINMENT <- 5
TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool")
TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")

P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
P[, tenet := as.integer(unit %in% TRU)]
P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]
V <- fread(file.path(SC, "loso_volume.csv")); V[, month := as.Date(month)]
V[, unit := fifelse(show %in% TIM, "tim_pool", show)]
Vunit <- V[, .(n_words = sum(n_sent_total)), by = .(unit, month)]
P <- merge(P, Vunit, by = c("unit", "month"), all.x = TRUE)
P[, prop_rus := n_ment_r / n_words]
P[, period := factor(ifelse(month < TREAT, "Pre-payment", "Post-payment"), levels = c("Pre-payment", "Post-payment"))]

## per show x period: stance measures among >=MINMENT-mention months; mentions = agenda share
st <- P[n_ment_r >= MINMENT, .(
  r_score = weighted.mean(r_score, n_ment_r, na.rm = TRUE),
  r_pos   = weighted.mean(r_pos,   n_ment_r, na.rm = TRUE),
  c_score = weighted.mean(c_score, n_ment_r, na.rm = TRUE),
  c_pos   = weighted.mean(c_pos,   n_ment_r, na.rm = TRUE),
  tenet = tenet[1]), by = .(unit, period)]
mn <- P[, .(mentions = weighted.mean(prop_rus, n_words, na.rm = TRUE), tenet = tenet[1]), by = .(unit, period)]
agg <- merge(mn, st, by = c("unit", "period", "tenet"), all = TRUE)

G <- melt(agg, id.vars = c("unit", "period", "tenet"),
          measure.vars = c("mentions", "r_score", "r_pos", "c_score", "c_pos"),
          variable.name = "measure", value.name = "val")
G[, measure := factor(measure, levels = c("mentions", "r_score", "r_pos", "c_score", "c_pos"),
                      labels = c("Russia mention share", "Russia score", "Russia pos rate",
                                 "Combined score", "Combined pos rate"))]
G <- G[is.finite(val)]
G[, rk := frank(val, ties.method = "first"), by = .(measure, period)]
G[, grp := ifelse(tenet == 1, "Tenet show", "Other program")]
fwrite(G, file.path(SC, "figH_ranked_prepost_data.csv"))

pH <- ggplot(G, aes(val, rk)) +
  geom_segment(aes(x = 0, xend = val, yend = rk, colour = grp, linewidth = grp), alpha = 0.75) +
  geom_point(aes(colour = grp, size = grp)) +
  facet_grid(measure ~ period, scales = "free") +
  scale_colour_manual(values = c("Tenet show" = "#b2182b", "Other program" = "grey78")) +
  scale_size_manual(values = c("Tenet show" = 2.2, "Other program" = 0.6), guide = "none") +
  scale_linewidth_manual(values = c("Tenet show" = 0.7, "Other program" = 0.25), guide = "none") +
  labs(x = "Value (programs ranked low to high within each panel)", y = NULL, colour = NULL,
       title = "Tenet shows vs. all programs, pre- and post-payment",
       subtitle = "Each lollipop is one program; the three Tenet shows are red. Split at the first payment (Oct 2023).") +
  theme_bw(base_size = 11) +
  theme(panel.grid.minor = element_blank(), axis.text.y = element_blank(), axis.ticks.y = element_blank(),
        axis.text.x = element_text(angle = 0, hjust = 0.5),
        strip.background = element_rect(fill = "grey92", colour = NA), legend.position = "bottom")
ggsave(file.path(SC, "figH_ranked_prepost.pdf"), pH, width = 9, height = 12)
cat("WROTE figH_ranked_prepost.pdf (+ _data.csv)\n")
