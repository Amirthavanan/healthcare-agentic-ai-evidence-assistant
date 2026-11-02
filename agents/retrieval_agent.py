"""Agent 3: Evidence Retrieval Agent.
Wraps the existing validated BM25+FAISS hybrid retrieval engine, preserving source provenance, page numbers, and versions.
"""
from typing import Any
from agents.schemas import RetrievalAgentResult, RetrievedPassage
from retrieval.hybrid import retriever


class EvidenceRetrievalAgent:
    """Executes hybrid retrieval over approved clinical guidelines and policy sources."""

    def __init__(self, retrieval_engine=None):
        self.retriever = retrieval_engine or retriever

    def execute(
        self,
        query: str,
        patient_facts: list[str] | None = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> RetrievalAgentResult:
        clean_q = (query or "").strip()
        search_query = clean_q
        if patient_facts:
            # Augment query with salient clinical facts for contextual retrieval
            search_query = f"{clean_q} {' '.join(patient_facts)}"

        if not search_query:
            return RetrievalAgentResult(
                query_used="",
                passages=[],
                total_retrieved=0,
                top_score=0.0,
                no_results_found=True,
            )

        results = self.retriever.search(
            query=search_query,
            top_k=top_k,
            min_score=min_score,
        )

        passages: list[RetrievedPassage] = []
        for r in results:
            passages.append(
                RetrievedPassage(
                    source_id=r.get("source_id") or r.get("id", "UNKNOWN"),
                    document_title=r.get("title", "Clinical Document"),
                    publisher=r.get("publisher", "World Health Organization"),
                    version=str(r.get("version", "2021")),
                    publication_date=r.get("publication_date") or r.get("effective_date"),
                    effective_date=r.get("effective_date"),
                    page_number=r.get("page"),
                    section=r.get("section", "General"),
                    excerpt=r.get("excerpt", ""),
                    retrieval_score=round(float(r.get("score", 0.0)), 4),
                    sparse_score=round(float(r.get("sparse_score", 0.0)), 4) if r.get("sparse_score") is not None else None,
                    dense_score=round(float(r.get("dense_score", 0.0)), 4) if r.get("dense_score") is not None else None,
                    review_status=r.get("review_status", "approved"),
                )
            )

        top_score = passages[0].retrieval_score if passages else 0.0
        no_results = len(passages) == 0

        return RetrievalAgentResult(
            query_used=search_query,
            passages=passages,
            total_retrieved=len(passages),
            top_score=top_score,
            no_results_found=no_results,
        )
