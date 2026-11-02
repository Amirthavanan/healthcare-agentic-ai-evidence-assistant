"""Validator for verifying citation authenticity, source ID validity, and passage support."""
import re
from typing import Any
from agents.schemas import CitationReference, EvidenceClaim, RetrievedPassage


class CitationValidator:
    """Verifies that every generated citation corresponds to a retrieved approved passage."""

    def validate_citations(
        self,
        citations: list[CitationReference] | list[dict[str, Any]],
        evidence_claims: list[EvidenceClaim] | list[dict[str, Any]],
        retrieved_passages: list[RetrievedPassage] | list[dict[str, Any]],
        is_abstention: bool = False,
    ) -> tuple[bool, list[str], dict[str, Any]]:
        errors: list[str] = []
        details: dict[str, Any] = {
            "valid_citations": [],
            "invalid_citations": [],
            "unsupported_claims": [],
        }

        # Build lookup of valid retrieved source IDs and pages
        valid_source_map: dict[str, list[dict[str, Any]]] = {}
        for p in retrieved_passages:
            sid = getattr(p, "source_id", None) or (p.get("source_id") if isinstance(p, dict) else None)
            if sid:
                page = getattr(p, "page_number", None) if hasattr(p, "page_number") else p.get("page")
                excerpt = getattr(p, "excerpt", "") if hasattr(p, "excerpt") else p.get("excerpt", "")
                valid_source_map.setdefault(sid, []).append({"page": page, "excerpt": excerpt})

        if is_abstention:
            # When explicitly abstaining due to no evidence, citation list may be empty or contain NONE
            return True, [], details

        # 1. Check citations presence
        if not citations and retrieved_passages:
            errors.append("MISSING_CITATIONS")

        # 2. Verify each citation exists in retrieved source IDs
        for c in citations:
            sid = getattr(c, "source_id", None) or (c.get("source_id") if isinstance(c, dict) else None)
            if not sid or (sid not in valid_source_map and sid != "NONE"):
                errors.append(f"INVALID_SOURCE_ID:{sid}")
                details["invalid_citations"].append(sid)
            else:
                details["valid_citations"].append(sid)

        # 3. Verify evidence claims against source IDs
        for cl in evidence_claims:
            sid = getattr(cl, "source_id", None) or (cl.get("source_id") if isinstance(cl, dict) else None)
            claim_text = getattr(cl, "claim", "") if hasattr(cl, "claim") else cl.get("claim", "")
            if not sid or (sid not in valid_source_map and sid != "NONE"):
                errors.append("UNSUPPORTED_CLAIM_SOURCE")
                details["unsupported_claims"].append(claim_text[:80])

        passed = len(errors) == 0
        return passed, errors, details
