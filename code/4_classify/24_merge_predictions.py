"""24_merge_predictions.py -- PLANNED, NOT YET IMPLEMENTED.
Writes the two files the analysis layer reads (decided Nov 23, 2026, audit finding B5):
  1. $COLLAB/data/windows/one_sentence/corpus_with_topics.parquet
     Full one-sentence corpus (data/windows/one_sentence/corpus.parquet from step 06) joined to the step-07 topic
     assignments. Required columns: show, date, sentence_id, sentence, topic.
     Read by 25, 27, 28, 36, 41, 46. The old data/corpus_with_topics.parquet (pre-windowing corpus; its producer was
     deleted in July, commit 989f0a9) must not be used.
  2. The sentence-level label file that replaces data/sc_results/opus_c0_corpus_labeled.parquet (read by 25, 36, 46),
     from gate (21) + stance (23) predictions. Required columns: show, date, sentence_id, topic, russia_label,
     russia_p_pos, russia_p_neg, ukraine_label, ukraine_p_pos, ukraine_p_neg. 30_grid_h1h2.R also reads
     data/sc_results/probs_4class.csv (4-class probabilities); write that too or repoint 30.
See README.md (pipeline table) for status."""
raise SystemExit("24_merge_predictions.py is a planned step and has not been implemented yet.")
