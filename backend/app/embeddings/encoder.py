"""
MemoraGraph – Sentence Transformer Embedding Encoder

Singleton embedding encoder for generating dense vector representations
of text chunks. Configurable model via EMBEDDING_MODEL env variable.
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

_encoder_instance: Optional["EmbeddingEncoder"] = None


class EmbeddingEncoder:
    """
    Wraps sentence-transformers SentenceTransformer.
    Loaded once at startup and reused for all requests.
    """

    def __init__(self, model_name: str):
        logger.info("Loading embedding model: %s", model_name)
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Embedding model loaded. Dimension: %d", self.dimension
        )

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of strings to encode
            batch_size: Encoding batch size
            normalize: Whether to L2-normalize embeddings (recommended for cosine similarity)
        
        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        
        # Convert numpy array to Python list of lists
        return [emb.tolist() for emb in embeddings]

    def encode_single(self, text: str, normalize: bool = True) -> list[float]:
        """Encode a single text string."""
        result = self.encode([text], normalize=normalize)
        return result[0] if result else []


def get_encoder() -> EmbeddingEncoder:
    """Get or initialize the global encoder singleton."""
    global _encoder_instance
    if _encoder_instance is None:
        raise RuntimeError(
            "Embedding encoder not initialized. Call init_encoder() first."
        )
    return _encoder_instance


def init_encoder(model_name: str) -> EmbeddingEncoder:
    """Initialize the global encoder singleton."""
    global _encoder_instance
    _encoder_instance = EmbeddingEncoder(model_name)
    return _encoder_instance


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    arr_a = np.array(a)
    arr_b = np.array(b)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
