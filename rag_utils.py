"""
rag_utils.py
Lightweight FAISS-based RAG using TF-IDF embeddings (scikit-learn).

WHY TF-IDF instead of sentence_transformers:
  - sentence_transformers pulls in PyTorch (~800MB) which crashes Streamlit Cloud (1GB limit).
  - TF-IDF + faiss-cpu is ~70MB total and zero PyTorch dependency.
  - For compliance rules (SLA, uptime, penalty, governing law), TF-IDF keyword
    matching is highly effective because compliance language is domain-specific
    and keyword-rich.
"""

from typing import List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import faiss


class FAISSRetriever:
    """
    Stores document chunks in a FAISS inner-product index using TF-IDF vectors.

    Usage:
        retriever = FAISSRetriever(chunks)
        relevant = retriever.query("uptime SLA percentage", top_k=3)
    """

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self._empty = len(chunks) == 0

        if self._empty:
            return

        # TF-IDF vectorizer: bigrams help match multi-word compliance terms
        # (e.g. "governing law", "termination clause", "incident response")
        self.vectorizer = TfidfVectorizer(
            max_features=3000,
            ngram_range=(1, 2),   # unigrams + bigrams
            stop_words="english",
            sublinear_tf=True,    # log(1+tf) dampens very frequent terms
        )
        tfidf_matrix = self.vectorizer.fit_transform(chunks)  # sparse

        # Convert sparse → dense float32 for FAISS
        dense = tfidf_matrix.toarray().astype(np.float32)

        # L2-normalize so inner-product == cosine similarity
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        dense = dense / norms

        dim = dense.shape[1]
        self.index = faiss.IndexFlatIP(dim)   # inner-product index
        self.index.add(dense)

    def query(self, query_text: str, top_k: int = 3) -> List[str]:
        """
        Return the top_k document chunks most relevant to query_text.
        Falls back to the first top_k chunks if the index is empty.
        """
        if self._empty or not query_text.strip():
            return self.chunks[:top_k] if self.chunks else []

        q_sparse = self.vectorizer.transform([query_text])
        q_dense = q_sparse.toarray().astype(np.float32)

        # Normalize query vector
        norm = np.linalg.norm(q_dense)
        if norm > 0:
            q_dense = q_dense / norm

        k = min(top_k, len(self.chunks))
        _, indices = self.index.search(q_dense, k)
        return [self.chunks[i] for i in indices[0] if 0 <= i < len(self.chunks)]
