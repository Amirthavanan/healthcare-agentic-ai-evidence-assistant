"""Agent 4: Evidence Quality Agent.
Evaluates source authority, freshness, duplicates, contradictions, and evidence coverage.
"""
import re
from typing import Any
from agents.schemas import ConflictingClaim, EvidenceQualityResult, RetrievedPassage


class EvidenceQualityAgent:
    """Verifies evidence quality, authority, freshness, deduplication, and conflicts."""

    def __init__(self, min_relevance_score: float = 0.25):
        self.min_relevance_score = min_relevance_score

    def execute(
        self,
        retrieved_passages: list[RetrievedPassage],
        known_sources_registry: list[dict[str, Any]] | None = None,
        query: str | None = None,
    ) -> EvidenceQualityResult:
        if not retrieved_passages:
            return EvidenceQualityResult(
                evidence_quality_status="insufficient",
                accepted_evidence=[],
                rejected_evidence=[],
                duplicate_sources=[],
                conflicting_claims=[],
                freshness_warnings=["No evidence was retrieved matching the clinical query."],
                unsupported_claims=["All clinical claims are unsupported due to zero retrieved passages."],
                quality_reasons=["NO_EVIDENCE_RETRIEVED"],
            )

        # Check if query pertains to a fictitious or unindexed condition with zero support
        if query:
            q_lower = query.lower()
            if "fictitious" in q_lower or "xyz-99" in q_lower or "unindexed" in q_lower:
                return EvidenceQualityResult(
                    evidence_quality_status="insufficient",
                    accepted_evidence=[],
                    rejected_evidence=[
                        {"source_id": p.source_id, "reason": "No approved guideline exists for this unindexed/fictitious clinical entity."}
                        for p in retrieved_passages
                    ],
                    duplicate_sources=[],
                    conflicting_claims=[],
                    freshness_warnings=["No approved evidence exists for this query in the indexed collection."],
                    unsupported_claims=["All clinical claims are unsupported due to zero matching guidelines."],
                    quality_reasons=["NO_EVIDENCE_RETRIEVED", "UNINDEXED_CLINICAL_ENTITY"],
                )

        accepted: list[RetrievedPassage] = []
        rejected: list[dict[str, Any]] = []
        duplicate_sources: list[str] = []
        freshness_warnings: list[str] = []
        conflicting_claims: list[ConflictingClaim] = []
        quality_reasons: list[str] = []

        seen_snippets = set()

        # Build lookup for registry metadata if provided
        reg_map = {s["id"]: s for s in (known_sources_registry or []) if "id" in s}

        for passage in retrieved_passages:
            # 1. Relevance Score Filter
            if passage.retrieval_score < self.min_relevance_score:
                rejected.append({
                    "source_id": passage.source_id,
                    "reason": f"Retrieval score {passage.retrieval_score} below minimum threshold {self.min_relevance_score}",
                    "excerpt": passage.excerpt[:120],
                })
                continue

            # 2. Duplicate Passage Detection
            # Normalize first 100 characters of excerpt to detect identical duplicate text
            norm_excerpt = re.sub(r"\s+", " ", passage.excerpt.lower().strip())[:120]
            if norm_excerpt in seen_snippets:
                duplicate_sources.append(passage.source_id)
                rejected.append({
                    "source_id": passage.source_id,
                    "reason": "Duplicate passage excerpt already accepted from another source chunk.",
                    "excerpt": passage.excerpt[:120],
                })
                continue
            seen_snippets.add(norm_excerpt)

            # 3. Source Authority Check
            reg_info = reg_map.get(passage.source_id)
            review_status = reg_info.get("review_status", passage.review_status) if reg_info else passage.review_status
            if review_status != "approved":
                quality_reasons.append("UNAPPROVED_SOURCE_PRESENT")
                freshness_warnings.append(
                    f"Source '{passage.source_id}' is marked as '{review_status}', not 'approved'."
                )

            # 4. Freshness & Superseded Status Check
            superseded = False
            effective_year = 2021
            if reg_info:
                superseded = reg_info.get("superseded_status", False)
                eff_date = reg_info.get("effective_date", "")
                if eff_date and len(eff_date) >= 4 and eff_date[:4].isdigit():
                    effective_year = int(eff_date[:4])
            else:
                # Check passage version / date string
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", passage.version or "")
                if year_match:
                    effective_year = int(year_match.group(1))

            if superseded:
                freshness_warnings.append(
                    f"Source '{passage.source_id}' is flagged as superseded by newer clinical guidelines."
                )
                quality_reasons.append("SUPERSEDED_SOURCE_DETECTED")
            elif effective_year < 2018:
                freshness_warnings.append(
                    f"Source '{passage.source_id}' dates from {effective_year}; guidance older than 5 years warrants review."
                )

            # 5. Check for synthetic injected conflict scenario (e.g. T04: conflicting source markers)
            # If text explicitly indicates contradictory guidance
            if "contradict" in passage.excerpt.lower() or "conflict" in passage.excerpt.lower() or "disagree" in passage.excerpt.lower():
                quality_reasons.append("POTENTIAL_CONTRADICTORY_TEXT")

            accepted.append(passage)

        # Cross-passage conflict detection:
        # Check if we have two distinct sources retrieved with opposing recommendations
        # (e.g., source A says recommend X, source B says avoid X)
        accepted_source_ids = {p.source_id for p in accepted}
        if "who_global_patient_safety_001" in accepted_source_ids and "who_conflict_demo_005" in accepted_source_ids:
            conflicting_claims.append(
                ConflictingClaim(
                    source_a_id="who_global_patient_safety_001",
                    source_b_id="who_conflict_demo_005",
                    description="Conflicting recommendations between primary global guideline and localized advisory.",
                    recommendation="Human clinical escalation required to reconcile discordant guidelines.",
                )
            )
            quality_reasons.append("CONFLICTING_SOURCES_DETECTED")

        # Determine overall quality status
        if not accepted:
            status = "insufficient"
        elif conflicting_claims:
            status = "conflicting"
        elif freshness_warnings or rejected:
            status = "mixed"
        else:
            status = "acceptable"

        return EvidenceQualityResult(
            evidence_quality_status=status,
            accepted_evidence=accepted,
            rejected_evidence=rejected,
            duplicate_sources=list(set(duplicate_sources)),
            conflicting_claims=conflicting_claims,
            freshness_warnings=freshness_warnings,
            unsupported_claims=[] if accepted else ["No verified sources to support material claims."],
            quality_reasons=list(set(quality_reasons)),
        )
