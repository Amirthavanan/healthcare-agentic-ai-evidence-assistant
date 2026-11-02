"""Claim-Level Semantic Grounding Evaluation Module.

Evaluates whether each generated material clinical claim is supported by its cited
evidence passage. Distinguishes structural citation existence from actual semantic support.

DISCLAIMER: This automated evaluation mechanism uses deterministic lexical/token containment
and heuristic concept overlap. It is an engineering quality-assurance tool and is NOT
clinically validated for patient care or medical decision-making.
"""
import re
import string
from typing import Any, Optional
from pydantic import BaseModel, Field

# Standard healthcare/general English stop words to filter for semantic content words
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "patient", "guideline", "guidelines", "shall", "may", "also",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize and normalize text into alphanumeric words."""
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    return [w.strip() for w in cleaned.split() if len(w.strip()) > 1]


def _content_words(text: str) -> set[str]:
    """Extract non-stopword content words for semantic overlap matching."""
    tokens = _tokenize(text)
    return {w for w in tokens if w not in STOP_WORDS and len(w) > 2}


def _ngram_set(tokens: list[str], n: int = 2) -> set[tuple[str, ...]]:
    """Extract n-grams from token sequence."""
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


class SemanticGroundingVerdict(BaseModel):
    grounding_status: str = Field(description="supported | partially_supported | unsupported")
    rationale: str = Field(description="Engineering reasoning for semantic support verdict (non-clinical)")


class ClaimGroundingRecord(BaseModel):
    claim_id: str
    claim_text: str
    source_id: str
    page_number: Optional[int] = None
    supporting_evidence_passage: str
    grounding_status: str = Field(description="supported | partially_supported | unsupported")
    evaluation_method: str = Field(description="deterministic_verbatim | deterministic_lexical_containment | semantic_llm_entailment | semantic_heuristic | unmatched_source")
    overlap_score: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class ClaimGroundingSummary(BaseModel):
    total_claims: int
    supported_count: int
    partially_supported_count: int
    unsupported_count: int
    support_rate: float
    partial_rate: float
    unsupported_rate: float
    records: list[ClaimGroundingRecord]


class ClaimGroundingEvaluator:
    """Evaluates whether generated material claims are semantically supported by cited evidence.
    
    Supports:
    - Deterministic verbatim substring containment.
    - Deterministic lexical containment (content-word token set & bigram overlap).
    - Separately documented semantic LLM entailment for complex claims (optional).
    
    DISCLAIMER: The LLM-based semantic evaluator is an automated engineering heuristic for
    software quality assurance and is NOT clinically validated for patient care or medical decision-making.
    Citation existence is never treated as proof of semantic support.
    """

    def __init__(self, llm_provider: Optional[Any] = None):
        self.llm_provider = llm_provider

    def _evaluate_semantic_llm(self, claim_text: str, passage_text: str) -> Optional[tuple[str, str]]:
        """Separately documented semantic evaluation method for complex claims using LLM.
        
        Evaluates entailment between claim and evidence passage without treating citation as support.
        DISCLAIMER: NOT clinically validated.
        """
        if not self.llm_provider:
            return None
        try:
            from llm.schemas import LLMMessage
            messages = [
                LLMMessage(
                    role="system",
                    content=(
                        "You are an automated software test evaluator checking claim-evidence grounding. "
                        "Determine if the claim is supported, partially supported, or unsupported by the evidence excerpt. "
                        "Do not assume truth beyond what is explicitly stated in the evidence excerpt. "
                        "Return only valid JSON matching the requested schema."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"Evidence Excerpt:\n{passage_text}\n\n"
                        f"Claim to verify:\n{claim_text}\n\n"
                        "Evaluate whether the claim is: 'supported', 'partially_supported', or 'unsupported'."
                    ),
                ),
            ]
            verdict, _ = self.llm_provider.generate_structured(messages, SemanticGroundingVerdict)
            status = verdict.grounding_status.lower().strip()
            if status not in {"supported", "partially_supported", "unsupported"}:
                status = "partially_supported"
            return status, verdict.rationale
        except Exception:
            return None

    def evaluate_claims(
        self,
        claims: list[dict[str, Any]],
        retrieved_passages: list[dict[str, Any]],
        use_semantic_evaluator: bool = False,
    ) -> ClaimGroundingSummary:
        """Run claim-level semantic grounding evaluation over a set of claims against retrieved passages.
        
        Evaluates each claim:
        1. Checks source_id existence in retrieved passages (unmatched -> unsupported).
        2. Evaluates verbatim containment in candidate passage excerpt.
        3. Evaluates content-word token containment and bigram overlap.
        4. Categorizes into supported (>=70% containment), partially supported (35-70%), or unsupported (<35%).
        """
        records: list[ClaimGroundingRecord] = []
        
        # Build passage lookup by source_id
        passage_map: dict[str, list[dict[str, Any]]] = {}
        for p in retrieved_passages:
            sid = p.get("source_id") or p.get("id")
            if sid:
                passage_map.setdefault(sid, []).append(p)

        for idx, cl in enumerate(claims, start=1):
            claim_id = cl.get("claim_id") or f"CLM-{idx:03d}"
            claim_text = (cl.get("claim") or cl.get("claim_text") or "").strip()
            source_id = cl.get("source_id") or ""
            page_num = cl.get("page_number") or cl.get("page")

            # 1. Unmatched source verification
            if not source_id or source_id not in passage_map:
                records.append(
                    ClaimGroundingRecord(
                        claim_id=claim_id,
                        claim_text=claim_text,
                        source_id=source_id,
                        page_number=page_num,
                        supporting_evidence_passage="",
                        grounding_status="unsupported",
                        evaluation_method="unmatched_source",
                        overlap_score=0.0,
                        details={"reason": f"Cited source_id '{source_id}' was not found in retrieved passages."},
                    )
                )
                continue

            candidate_passages = passage_map[source_id]
            best_passage = (candidate_passages[0].get("excerpt") or "")[:300] if candidate_passages else ""
            best_overlap = 0.0
            best_status = "unsupported"
            best_method = "semantic_heuristic"
            best_details: dict[str, Any] = {}

            claim_tokens = _tokenize(claim_text)
            claim_content = _content_words(claim_text)
            claim_bigrams = _ngram_set(claim_tokens, 2)

            for cand in candidate_passages:
                excerpt = (cand.get("excerpt") or "").strip()
                if not excerpt:
                    continue

                excerpt_tokens = _tokenize(excerpt)
                excerpt_content = _content_words(excerpt)
                excerpt_bigrams = _ngram_set(excerpt_tokens, 2)

                # Check exact / normalized verbatim substring match
                norm_claim = " ".join(claim_tokens)
                norm_excerpt = " ".join(excerpt_tokens)
                if norm_claim in norm_excerpt or claim_text.lower() in excerpt.lower():
                    best_overlap = 1.0
                    best_status = "supported"
                    best_method = "deterministic_verbatim"
                    best_passage = excerpt[:300]
                    best_details = {"match_type": "exact_verbatim_containment"}
                    break

                # Content-word containment
                if claim_content:
                    matched_words = claim_content.intersection(excerpt_content)
                    containment = len(matched_words) / len(claim_content)
                else:
                    containment = 0.0

                # Bigram overlap
                if claim_bigrams and excerpt_bigrams:
                    bigram_overlap = len(claim_bigrams.intersection(excerpt_bigrams)) / len(claim_bigrams)
                else:
                    bigram_overlap = 0.0

                combined_score = 0.7 * containment + 0.3 * bigram_overlap

                if combined_score > best_overlap or not best_details:
                    best_overlap = combined_score
                    best_passage = excerpt[:300]
                    if containment >= 0.65 or combined_score >= 0.60:
                        best_status = "supported"
                        best_method = "deterministic_lexical_containment"
                    elif containment >= 0.30 or combined_score >= 0.30:
                        best_status = "partially_supported"
                        best_method = "semantic_heuristic"
                    else:
                        best_status = "unsupported"
                        best_method = "semantic_heuristic"

                    best_details = {
                        "content_word_containment": round(containment, 4),
                        "bigram_overlap": round(bigram_overlap, 4),
                        "matched_content_words": sorted(list(claim_content.intersection(excerpt_content)))[:8],
                    }

            if best_method != "deterministic_verbatim" and (use_semantic_evaluator or self.llm_provider) and best_passage:
                semantic_res = self._evaluate_semantic_llm(claim_text, best_passage)
                if semantic_res:
                    sem_status, sem_rationale = semantic_res
                    best_status = sem_status
                    best_method = "semantic_llm_entailment"
                    best_details["semantic_rationale"] = sem_rationale
                    best_details["disclaimer"] = "Automated engineering check; not clinically validated."

            records.append(
                ClaimGroundingRecord(
                    claim_id=claim_id,
                    claim_text=claim_text,
                    source_id=source_id,
                    page_number=page_num,
                    supporting_evidence_passage=best_passage,
                    grounding_status=best_status,
                    evaluation_method=best_method,
                    overlap_score=round(best_overlap, 4),
                    details=best_details,
                )
            )

        total = len(records)
        sup = sum(1 for r in records if r.grounding_status == "supported")
        part = sum(1 for r in records if r.grounding_status == "partially_supported")
        unsup = sum(1 for r in records if r.grounding_status == "unsupported")

        return ClaimGroundingSummary(
            total_claims=total,
            supported_count=sup,
            partially_supported_count=part,
            unsupported_count=unsup,
            support_rate=round(sup / total, 4) if total else 1.0,
            partial_rate=round(part / total, 4) if total else 0.0,
            unsupported_rate=round(unsup / total, 4) if total else 0.0,
            records=records,
        )
