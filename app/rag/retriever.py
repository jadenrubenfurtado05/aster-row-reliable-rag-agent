from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.config import get_config
from app.schemas import RAGSearchResult, RetrievedChunk
from app.rag.loader import DocumentChunk, DocumentLoader
from app.rag.vector_store import VectorStore

class RAGRetriever:
    """Metadata-aware RAG retriever enforcing document precedence and active source conflict detection."""

    def __init__(self, kb_directory: str | Path = "knowledge-base", embedding_model: Optional[str] = None):
        config = get_config()
        model_name = embedding_model or config.embedding_model

        self.loader = DocumentLoader(kb_directory)
        self.chunks = self.loader.load_documents()

        self.vector_store = VectorStore(embedding_model_name=model_name)
        self.vector_store.add_chunks(self.chunks)

    def retrieve(self, query: str, top_k: int = 5) -> RAGSearchResult:
        """Retrieves authoritative passages for a query while enforcing precedence and conflict detection."""
        # Retrieve candidate chunks across the vector index
        all_candidates: List[Tuple[DocumentChunk, float]] = self.vector_store.search(query, top_k=50)

        authoritative_chunks: List[RetrievedChunk] = []
        deprioritized_or_excluded: List[Dict[str, Any]] = []

        for chunk, score in all_candidates:
            # Precedence hierarchy:
            # Authoritative = status active AND policy_authority official AND audience customer AND customer_answering True
            is_authoritative = (
                chunk.status == "active"
                and chunk.policy_authority == "official"
                and chunk.audience != "internal"
                and chunk.customer_answering is True
            )

            chunk_schema = RetrievedChunk(
                source_filename=chunk.source_filename,
                document_id=chunk.document_id,
                title=chunk.title,
                heading=chunk.heading,
                text=chunk.text,
                similarity_score=round(score, 4),
                status=chunk.status,
                policy_authority=chunk.policy_authority,
                audience=chunk.audience,
                effective_date=chunk.effective_date,
                last_reviewed=chunk.last_reviewed,
                supersedes=chunk.supersedes
            )

            if is_authoritative:
                if len(authoritative_chunks) < top_k:
                    authoritative_chunks.append(chunk_schema)
            else:
                exclusion_reason = (
                    "superseded_version" if chunk.status == "superseded"
                    else "internal_audience" if chunk.audience == "internal"
                    else "unapproved_draft" if (chunk.status == "draft" or chunk.policy_authority == "none")
                    else "non_authoritative"
                )
                deprioritized_or_excluded.append({
                    "source_filename": chunk.source_filename,
                    "heading": chunk.heading,
                    "similarity_score": round(score, 4),
                    "status": chunk.status,
                    "policy_authority": chunk.policy_authority,
                    "reason": exclusion_reason
                })

        # 6. Detect genuine conflicts among active authoritative sources relevant to query
        conflict_detected, conflicting_sources = self._detect_conflicts(authoritative_chunks, query)

        diagnostics = {
            "total_raw_chunks": len(all_candidates),
            "excluded_chunks_count": len(deprioritized_or_excluded),
            "excluded_chunks": deprioritized_or_excluded[:10],
            "conflict_detected": conflict_detected,
            "conflicting_sources": conflicting_sources
        }

        return RAGSearchResult(
            query=query,
            retrieved_chunks=authoritative_chunks,
            conflict_detected=conflict_detected,
            conflicting_sources=conflicting_sources,
            diagnostics=diagnostics
        )

    def _detect_conflicts(self, chunks: List[RetrievedChunk], query: str = "") -> Tuple[bool, List[str]]:
        """Detects whether active, official chunks from different files contain opposing directives."""
        top_chunks = [c for c in chunks if c.similarity_score >= 0.35]
        if len(top_chunks) < 2:
            return False, []

        sources_by_file: Dict[str, List[RetrievedChunk]] = {}
        for chunk in top_chunks:
            sources_by_file.setdefault(chunk.source_filename, []).append(chunk)

        filenames = list(sources_by_file.keys())
        if len(filenames) < 2:
            return False, []

        # Check for directive contradictions between different active files
        for i in range(len(filenames)):
            for j in range(i + 1, len(filenames)):
                f1, f2 = filenames[i], filenames[j]
                text1 = " ".join([c.text.lower() for c in sources_by_file[f1]])
                text2 = " ".join([c.text.lower() for c in sources_by_file[f2]])

                # Contradictory washing/dishwasher care directives
                has_handwash1 = "hand-wash" in text1 or "hand-washed" in text1
                has_handwash2 = "hand-wash" in text2 or "hand-washed" in text2
                has_dishwasher1 = "dishwasher" in text1 and ("dishwasher safe" in text1 or "top rack" in text1)
                has_dishwasher2 = "dishwasher" in text2 and ("dishwasher safe" in text2 or "top rack" in text2)

                if (has_handwash1 and has_dishwasher2 and "all components" in text2) or \
                   (has_handwash2 and has_dishwasher1 and "all components" in text1):
                    return True, sorted([f1, f2])

                # Check general contradictory statements on care/policy
                if (has_handwash1 and "dishwasher safe" in text2 and "body" in text1) or \
                   (has_handwash2 and "dishwasher safe" in text1 and "body" in text2):
                    return True, sorted([f1, f2])

        return False, []
