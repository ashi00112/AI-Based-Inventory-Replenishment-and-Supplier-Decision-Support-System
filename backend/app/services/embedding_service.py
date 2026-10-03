import os
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings

class EmbeddingProvider:
    """Lazy-loaded singleton for sentence‑transformer embeddings.

    The model is loaded once per process and reused for subsequent calls.
    Normalized (L2) vectors are returned to match ChromaDB expectations.
    """
    _model: SentenceTransformer | None = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
            cls._model = SentenceTransformer(model_name)
        return cls._model

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        """Return L2‑normalized embeddings for a list of texts.

        Args:
            texts: List of raw text strings.
        Returns:
            List of embedding vectors (as plain Python floats) matching the order of *texts*.
        """
        if not texts:
            return []
        model = cls.get_model()
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()
