from typing import Callable, List, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from app.rag.loader import DocumentChunk

class VectorStore:
    """In-memory numpy-based vector store for Markdown document chunks."""

    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model_name
        self.model = SentenceTransformer(embedding_model_name)
        self.chunks: List[DocumentChunk] = []
        self.embeddings: Optional[np.ndarray] = None

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Embeds and indexes a list of DocumentChunk objects."""
        if not chunks:
            return

        texts = [f"{c.title or ''} {c.heading}\n{c.text}".strip() for c in chunks]
        new_embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

        self.chunks.extend(chunks)
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_fn: Optional[Callable[[DocumentChunk], bool]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Performs cosine similarity search against indexed chunks with optional metadata filtering."""
        if not self.chunks or self.embeddings is None:
            return []

        query_embedding = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        scores = np.dot(self.embeddings, query_embedding)

        sorted_indices = np.argsort(scores)[::-1]

        results: List[Tuple[DocumentChunk, float]] = []
        for idx in sorted_indices:
            chunk = self.chunks[idx]
            score = float(scores[idx])
            if filter_fn is None or filter_fn(chunk):
                results.append((chunk, score))
                if len(results) >= top_k:
                    break

        return results
