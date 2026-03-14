"""
Kazakh word embeddings engine.

Downloads and loads the FastText pre-trained Kazakh vectors from Meta AI.
Uses cosine similarity to rank all vocabulary words relative to a query word.

Vector source: https://fasttext.cc/docs/en/pretrained-vectors.html
File: wiki.kk.vec  (~600 MB, 300-dim, ~300k words)

Usage:
    engine = EmbeddingEngine()
    await engine.load()                        # call once at startup
    rank = engine.get_rank("үй", "есік")       # returns int rank
    similar = engine.get_top_similar("үй", 10) # returns list of (word, score)
"""

import os
import logging
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FASTTEXT_URL = "https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.kk.vec"
VECTORS_PATH = Path(os.getenv("VECTORS_PATH", "./data/wiki.kk.vec"))
CACHE_PATH = Path(os.getenv("CACHE_PATH", "./data/kk_vectors.npz"))


class EmbeddingEngine:
    """
    Loads Kazakh word vectors and provides fast cosine-similarity ranking.

    Lazy-loads on first request if not pre-loaded at startup.
    Caches the full sorted similarity list per word to speed up repeated queries.
    """

    def __init__(self):
        self.words: list[str] = []
        self.vectors: Optional[np.ndarray] = None   # shape: (N, 300)
        self.word_to_idx: dict[str, int] = {}
        self._rank_cache: dict[str, dict[str, int]] = {}
        self._loaded = False

    async def load(self):
        """Load vectors from disk (or download if missing). Call once at startup."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_sync)

    def _load_sync(self):
        """Synchronous load — runs in thread pool to avoid blocking event loop."""
        if self._loaded:
            return

        # Try fast numpy cache first
        if CACHE_PATH.exists():
            logger.info(f"Loading cached vectors from {CACHE_PATH}")
            self._load_from_cache()
            return

        # Fall back to raw .vec file
        if not VECTORS_PATH.exists():
            logger.warning(
                f"Vector file not found at {VECTORS_PATH}. "
                f"Run scripts/download_vectors.sh to download it.\n"
                f"Falling back to dummy vectors for development."
            )
            self._load_dummy_vectors()
            return

        logger.info(f"Loading FastText vectors from {VECTORS_PATH} ...")
        self._load_from_vec_file()
        self._save_cache()

    def _load_from_vec_file(self):
        """Parse the .vec text format (word2vec-style)."""
        words, vectors = [], []
        with open(VECTORS_PATH, "r", encoding="utf-8") as f:
            first_line = f.readline().strip().split()
            vocab_size, dim = int(first_line[0]), int(first_line[1])
            logger.info(f"Vocab size: {vocab_size}, Dimensions: {dim}")

            for line in f:
                parts = line.rstrip().split(" ")
                if len(parts) != dim + 1:
                    continue
                word = parts[0]
                try:
                    vec = np.array(parts[1:], dtype=np.float32)
                    words.append(word)
                    vectors.append(vec)
                except ValueError:
                    continue

        self.words = words
        self.vectors = np.array(vectors, dtype=np.float32)
        self._normalize()
        self._build_index()
        self._loaded = True
        logger.info(f"Loaded {len(self.words)} word vectors.")

    def _load_from_cache(self):
        """Load from compressed numpy cache (much faster than parsing .vec)."""
        data = np.load(CACHE_PATH, allow_pickle=True)
        self.words = data["words"].tolist()
        self.vectors = data["vectors"]
        self._build_index()
        self._loaded = True
        logger.info(f"Loaded {len(self.words)} words from cache.")

    def _save_cache(self):
        """Save parsed vectors as compressed numpy file for fast future loads."""
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            CACHE_PATH,
            words=np.array(self.words, dtype=object),
            vectors=self.vectors
        )
        logger.info(f"Saved vector cache to {CACHE_PATH}")

    def _load_dummy_vectors(self):
        """
        Fallback for dev/testing when no real vectors are available.
        Creates fake 50-dim vectors for ~200 common Kazakh words.
        Similarity will be random — only useful for UI testing.
        """
        from words import get_all_words
        dev_words = get_all_words()
        np.random.seed(42)
        self.words = dev_words
        self.vectors = np.random.randn(len(dev_words), 50).astype(np.float32)
        self._normalize()
        self._build_index()
        self._loaded = True
        logger.warning(f"Loaded {len(self.words)} DUMMY vectors (dev mode).")

    def _normalize(self):
        """L2-normalize all vectors so dot product == cosine similarity."""
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-9, norms)
        self.vectors = self.vectors / norms

    def _build_index(self):
        """Build word → index lookup dict."""
        self.word_to_idx = {w: i for i, w in enumerate(self.words)}

    def is_loaded(self) -> bool:
        return self._loaded

    def word_exists(self, word: str) -> bool:
        return word in self.word_to_idx

    def get_vector(self, word: str) -> Optional[np.ndarray]:
        idx = self.word_to_idx.get(word)
        if idx is None:
            return None
        return self.vectors[idx]

    def get_rank(self, secret: str, guess: str) -> Optional[int]:
        """
        Returns the rank of `guess` in the similarity-sorted list for `secret`.
        Rank 1 = the secret word itself.
        Returns None if either word is not in vocabulary.
        """
        if secret not in self.word_to_idx or guess not in self.word_to_idx:
            return None

        if secret == guess:
            return 1

        # Use cache if available
        if secret in self._rank_cache:
            return self._rank_cache[secret].get(guess)

        # Compute similarities between secret word and all vocabulary
        secret_vec = self.vectors[self.word_to_idx[secret]]  # (dim,)
        similarities = self.vectors @ secret_vec               # (N,) dot product = cosine sim

        # Sort descending, create rank mapping (rank 1 = most similar = secret itself)
        sorted_indices = np.argsort(-similarities)
        rank_map = {self.words[idx]: rank + 1 for rank, idx in enumerate(sorted_indices)}

        # Cache and return
        self._rank_cache[secret] = rank_map
        return rank_map.get(guess)

    def get_top_similar(self, word: str, topn: int = 10) -> list[tuple[str, float]]:
        """
        Return the top-N most similar words to `word` (excluding itself).
        Returns list of (word, cosine_similarity) tuples.
        """
        if word not in self.word_to_idx:
            return []

        vec = self.vectors[self.word_to_idx[word]]
        sims = self.vectors @ vec
        sorted_idx = np.argsort(-sims)

        result = []
        for idx in sorted_idx:
            w = self.words[idx]
            if w == word:
                continue
            result.append((w, float(sims[idx])))
            if len(result) >= topn:
                break
        return result

    def get_similarity_score(self, word1: str, word2: str) -> Optional[float]:
        """Return raw cosine similarity between two words (0.0 – 1.0 range)."""
        v1 = self.get_vector(word1)
        v2 = self.get_vector(word2)
        if v1 is None or v2 is None:
            return None
        return float(np.dot(v1, v2))


# Singleton instance — shared across all requests
engine = EmbeddingEngine()
