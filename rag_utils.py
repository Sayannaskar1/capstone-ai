"""
rag_utils.py
Embedding model is loaded once at the process level and exposed via a helper
that is compatible with Streamlit's @st.cache_resource pattern.
"""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# ── Module-level singleton (safe for multi-thread, single-process Streamlit) ──
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Lazy-load the SentenceTransformer model exactly once per process.
    Call this from a @st.cache_resource wrapper in app.py for the cleanest
    Streamlit integration, or use it directly — both work.
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


class RAGRetriever:
    """
    Builds a FAISS cosine-similarity index from document chunks and retrieves
    the top-k most relevant chunks for a given query.
    """

    def __init__(self, chunks: List[str], model: SentenceTransformer | None = None):
        """
        Args:
            chunks: List of text chunks from the document.
            model:  Optional pre-loaded SentenceTransformer (avoids reloading).
        """
        self.chunks = chunks
        self.model = model if model is not None else get_embedding_model()
        self._build_index()

    def _build_index(self) -> None:
        """Encode all chunks and build the FAISS inner-product (cosine) index."""
        embeddings: np.ndarray = self.model.encode(
            self.chunks, convert_to_numpy=True, show_progress_bar=False
        )
        faiss.normalize_L2(embeddings)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def get_relevant_chunks(self, query: str, top_k: int = 5) -> List[str]:
        """
        Retrieve the top-k chunks most semantically relevant to query.

        Args:
            query: The compliance rule or question to search for.
            top_k: Number of chunks to return.

        Returns:
            List of relevant text chunks (ordered by relevance).
        """
        query_vec: np.ndarray = self.model.encode(
            [query], convert_to_numpy=True, show_progress_bar=False
        )
        faiss.normalize_L2(query_vec)
        k = min(top_k, len(self.chunks))
        distances, indices = self.index.search(query_vec, k)
        return [self.chunks[i] for i in indices[0] if i < len(self.chunks)]
