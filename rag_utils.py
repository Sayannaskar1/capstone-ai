# --- NEW CODE START ---
"""
rag_utils.py
Handles embedding generation and FAISS-based retrieval for the compliance pipeline.
New file added to support RAG functionality.
"""

from typing import List
import numpy as np

from sentence_transformers import SentenceTransformer
import faiss

# Load the embedding model once at module level (cached after first load)
_embedding_model = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


class RAGRetriever:
    """
    Builds a FAISS index from document chunks and retrieves the top-k
    most relevant chunks for a given query.
    """

    def __init__(self, chunks: List[str]):
        """
        Args:
            chunks: List of text chunks from the document.
        """
        self.chunks = chunks
        self.model = _get_model()
        self._build_index()

    def _build_index(self):
        """Encode all chunks and build the FAISS index."""
        embeddings = self.model.encode(self.chunks, convert_to_numpy=True)
        # Normalise for cosine similarity via inner-product search
        faiss.normalize_L2(embeddings)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def get_relevant_chunks(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieve the top-k chunks most semantically relevant to query.

        Args:
            query: The compliance rule or question to search for.
            top_k: Number of chunks to return.

        Returns:
            List of relevant text chunks.
        """
        query_vec = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_vec)
        distances, indices = self.index.search(query_vec, min(top_k, len(self.chunks)))
        return [self.chunks[i] for i in indices[0] if i < len(self.chunks)]
# --- NEW CODE END ---
