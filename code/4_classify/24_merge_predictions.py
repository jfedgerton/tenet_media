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
Also required before re-running 25-49 (GPT audit C, Nov 23, 2026; deferred to this step by the PI):
  3. Sentence key. sentence_id restarts at 0 in every episode (step 05), so it is not unique. Both output files must carry
     a unique uid = <episode key>#<sentence_id>, the same format as the uid in the coder files (e.g.
     break_the_rules_20230514172500_92#184), and every join must use uid. 46_label_examples.py currently joins text on
     sentence_id alone and must switch to uid. The matching format also links the human gold codes to the corpus.
  4. Topic model consistency. 27, 28 and 41 still read the pre-windowing data/topic_model/topic_info.csv,
     data/topic_info.csv and data/topic_model/topic_model, and hard-code Russia topics [78, 79]. Refits renumber topics.
     Repoint them to step 07's data/windows/one_sentence/{topic_info.csv,topic_model} and take the Russia/Ukraine topic
     IDs from step 08's topic_labels.csv (label == "russia"). 41's H3 grid assumes exactly two Russia topics, each paired
     with its nearest neighbor; 08 may find more. How 41 handles k Russia topics is a PI decision.
See README.md (pipeline table) for status."""
raise SystemExit("24_merge_predictions.py is a planned step and has not been implemented yet.")
