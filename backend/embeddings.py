"""
Kazakh word embeddings engine.
Loads ONLY the words in DAILY_WORDS from the FastText vectors file.
This ensures rank, similarity, and hints only use clean root-form nouns.
"""

import os
import logging
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VECTORS_PATH = Path(os.getenv("VECTORS_PATH", "./data/wiki.kk.clean.vec"))
# Cache disabled — always load fresh so DAILY_WORDS changes take effect
CACHE_PATH = Path(os.getenv("CACHE_PATH", "./data/kk_vectors.npz"))


class EmbeddingEngine:

    def __init__(self):
        self.words: list[str] = []
        self.vectors: Optional[np.ndarray] = None
        self.word_to_idx: dict[str, int] = {}
        self._rank_cache: dict[str, dict[str, int]] = {}
        self._loaded = False

    async def load(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_sync)

    def _load_sync(self):
        if self._loaded:
            return

        # DELETE old cache — it may contain 163k words instead of DAILY_WORDS
        if CACHE_PATH.exists():
            try:
                CACHE_PATH.unlink()
                logger.info(f"Deleted old cache: {CACHE_PATH}")
            except Exception as e:
                logger.warning(f"Could not delete cache: {e}")

        # Load DAILY_WORDS list
        from words import DAILY_WORDS
        daily_set = set(w.strip().lower() for w in DAILY_WORDS)
        logger.info(f"DAILY_WORDS: {len(daily_set)} words to load")

        if not VECTORS_PATH.exists():
            logger.warning(f"Vector file not found at {VECTORS_PATH}. Using dummy vectors.")
            self._load_dummy_vectors()
            return

        logger.info(f"Loading vectors from {VECTORS_PATH} (filtering to DAILY_WORDS)...")
        self._load_filtered(daily_set)

    def _load_filtered(self, daily_set: set):
        """Load only vectors for words in DAILY_WORDS."""
        words, vectors = [], []

        with open(VECTORS_PATH, "r", encoding="utf-8") as f:
            first_line = f.readline().strip().split()
            dim = int(first_line[1])
            logger.info(f"Vec file dim: {dim}")

            for line in f:
                parts = line.rstrip().split(" ")
                if len(parts) != dim + 1:
                    continue
                word = parts[0].strip().lower()
                if word not in daily_set:
                    continue
                try:
                    vec = np.array(parts[1:], dtype=np.float32)
                    words.append(word)
                    vectors.append(vec)
                except ValueError:
                    continue

        if not words:
            logger.warning("No matching words found in vec file! Using dummy vectors.")
            self._load_dummy_vectors()
            return

        self.words = words
        self.vectors = np.array(vectors, dtype=np.float32)
        self._normalize()
        self._build_index()
        self._loaded = True
        logger.info(f"Loaded {len(self.words)} vectors (filtered from DAILY_WORDS).")

        # Log which DAILY_WORDS are missing from vec file
        loaded_set = set(self.words)
        missing = daily_set - loaded_set
        if missing:
            logger.warning(f"{len(missing)} DAILY_WORDS not found in vec file: {list(missing)[:10]}")

    def _load_dummy_vectors(self):
        from words import DAILY_WORDS
        words = [w.strip().lower() for w in DAILY_WORDS]
        np.random.seed(42)
        self.words = words
        self.vectors = np.random.randn(len(words), 50).astype(np.float32)
        self._normalize()
        self._build_index()
        self._loaded = True
        logger.warning(f"Loaded {len(self.words)} DUMMY vectors.")

    def _normalize(self):
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-9, norms)
        self.vectors = self.vectors / norms

    def _build_index(self):
        self.word_to_idx = {w: i for i, w in enumerate(self.words)}

    def is_loaded(self) -> bool:
        return self._loaded

    def word_exists(self, word: str) -> bool:
        return word.strip().lower() in self.word_to_idx

    def get_vector(self, word: str) -> Optional[np.ndarray]:
        idx = self.word_to_idx.get(word.strip().lower())
        if idx is None:
            return None
        return self.vectors[idx]

    def get_rank(self, secret: str, guess: str) -> Optional[int]:
        """
        Rank of guess among all DAILY_WORDS by similarity to secret.
        Rank 1 = secret word itself.
        """
        s = secret.strip().lower()
        g = guess.strip().lower()

        if s not in self.word_to_idx or g not in self.word_to_idx:
            return None

        if s == g:
            return 1

        if s in self._rank_cache:
            return self._rank_cache[s].get(g)

        secret_vec = self.vectors[self.word_to_idx[s]]
        similarities = self.vectors @ secret_vec
        sorted_indices = np.argsort(-similarities)
        rank_map = {self.words[idx]: rank + 1 for rank, idx in enumerate(sorted_indices)}

        self._rank_cache[s] = rank_map
        return rank_map.get(g)

    def get_top_similar(self, word: str, topn: int = 10) -> list[tuple[str, float]]:
        """Top-N similar words from DAILY_WORDS only."""
        w = word.strip().lower()
        if w not in self.word_to_idx:
            return []

        vec = self.vectors[self.word_to_idx[w]]
        sims = self.vectors @ vec
        sorted_idx = np.argsort(-sims)

        result = []
        for idx in sorted_idx:
            word_i = self.words[idx]
            if word_i == w:
                continue
            result.append((word_i, float(sims[idx])))
            if len(result) >= topn:
                break
        return result

    def get_similarity_score(self, word1: str, word2: str) -> Optional[float]:
        v1 = self.get_vector(word1)
        v2 = self.get_vector(word2)
        if v1 is None or v2 is None:
            return None
        return float(np.dot(v1, v2))


# Singleton
engine = EmbeddingEngine()
