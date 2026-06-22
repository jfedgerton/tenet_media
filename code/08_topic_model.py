"""
6_topic_model.py
Fit a BERTopic model on the sentence corpus and assign topics to all sentences.

Loads data/corpus.parquet, samples up to 500K sentences for fitting, then
transforms the full corpus in batches. Saves topic info, assignments, and
the serialized model.
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SEED = 123
TRANSFORM_BATCH = 50_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def sample_sentences(corpus: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    """Sample up to sample_size sentences uniformly across shows."""
    rng = np.random.RandomState(SEED)
    n_shows = corpus["show"].nunique()
    per_show = max(1, sample_size // n_shows)

    sampled_parts = []
    for show, grp in corpus.groupby("show"):
        if len(grp) <= per_show:
            sampled_parts.append(grp)
        else:
            sampled_parts.append(grp.sample(n=per_show, random_state=rng))

    sampled = pd.concat(sampled_parts, ignore_index=False)

    # If total exceeds sample_size, trim uniformly
    if len(sampled) > sample_size:
        sampled = sampled.sample(n=sample_size, random_state=rng)

    log.info(
        "Sampled %d sentences from %d shows for topic fitting",
        len(sampled),
        sampled["show"].nunique(),
    )
    return sampled


def build_bertopic() -> BERTopic:
    """Construct BERTopic with configured sub-models."""
    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=SEED,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=150,
        min_samples=10,
        prediction_data=True,
    )
    vectorizer = CountVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )
    topic_model = BERTopic(
        embedding_model="all-MiniLM-L6-v2",
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        nr_topics="auto",
        verbose=True,
    )
    return topic_model


def transform_all(
    topic_model: BERTopic, sentences: pd.Series
) -> tuple[list[int], list[float]]:
    """Transform all sentences in batches, returning topics and probabilities."""
    all_topics = []
    all_probs = []
    n = len(sentences)
    n_batches = (n + TRANSFORM_BATCH - 1) // TRANSFORM_BATCH

    for i in range(n_batches):
        start = i * TRANSFORM_BATCH
        end = min(start + TRANSFORM_BATCH, n)
        log.info(
            "Transforming batch %d/%d  (rows %d–%d)",
            i + 1,
            n_batches,
            start,
            end - 1,
        )
        batch_docs = sentences.iloc[start:end].tolist()
        topics, probs = topic_model.transform(batch_docs)
        all_topics.extend(topics)
        # probs can be arrays per doc if nr_topics > 1; take max prob
        for p in probs:
            if hasattr(p, "__len__"):
                all_probs.append(float(np.max(p)) if len(p) > 0 else 0.0)
            else:
                all_probs.append(float(p))

    return all_topics, all_probs


def main():
    parser = argparse.ArgumentParser(
        description="Fit BERTopic on sentence corpus and assign topics."
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=str(PROJECT_ROOT / "data" / "corpus.parquet"),
        help="Path to corpus parquet file.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=500_000,
        help="Max sentences to use for topic model fitting.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "data"),
        help="Directory for output files.",
    )
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Load corpus ----
    log.info("Loading corpus from %s", corpus_path)
    corpus = pd.read_parquet(corpus_path)
    log.info("Corpus: %d rows, %d columns", len(corpus), len(corpus.columns))

    # ---- Sample for fitting ----
    sample_df = sample_sentences(corpus, args.sample_size)
    sample_docs = sample_df["sentence"].tolist()

    # ---- Build and fit model ----
    log.info("Building BERTopic model")
    topic_model = build_bertopic()

    log.info("Fitting topic model on %d sentences", len(sample_docs))
    topic_model.fit(sample_docs)

    topic_info = topic_model.get_topic_info()
    log.info("Number of topics found: %d", len(topic_info))

    # ---- Transform ALL sentences ----
    log.info("Transforming full corpus (%d sentences)", len(corpus))
    all_topics, all_probs = transform_all(topic_model, corpus["sentence"])

    # ---- Save topic info ----
    topic_info_path = output_dir / "topic_info.csv"
    topic_info.to_csv(topic_info_path, index=False)
    log.info("Saved topic info to %s", topic_info_path)

    # ---- Save topic assignments ----
    topics_df = pd.DataFrame(
        {
            "corpus_index": corpus.index,
            "topic": all_topics,
            "probability": all_probs,
        }
    )
    topics_parquet = output_dir / "topics.parquet"
    topics_df.to_parquet(topics_parquet, index=False)
    log.info("Saved topic assignments to %s", topics_parquet)

    # ---- Save model ----
    model_dir = output_dir / "topic_model"
    model_dir.mkdir(parents=True, exist_ok=True)
    topic_model.save(str(model_dir), serialization="safetensors", save_ctfidf=True)
    log.info("Saved BERTopic model to %s", model_dir)

    # ---- Print top 20 topics ----
    log.info("===== Top 20 topics =====")
    top20 = topic_info.head(21)  # topic -1 is outlier, so take 21 rows
    for _, row in top20.iterrows():
        topic_id = row["Topic"]
        name = row.get("Name", "")
        count = row.get("Count", "")
        # Get representative words
        topic_words = topic_model.get_topic(topic_id)
        if topic_words and isinstance(topic_words, list):
            words_str = ", ".join(w for w, _ in topic_words[:8])
        else:
            words_str = str(name)
        log.info("  Topic %4d  (n=%7s)  %s", topic_id, count, words_str)


if __name__ == "__main__":
    main()
