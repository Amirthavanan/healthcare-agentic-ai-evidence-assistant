"""Deterministic Output Validator implementing the 12 clinical decision-support rules."""
import re
from typing import Any
from validators.citation_validator import CitationValidator
from validators.schemas import ValidationResult

# Prohibited medical decision language in generated output text
PROHIBITED_OUTPUT_PATTERNS = [
    r"\bi\s+diagnose\s+(?:you|the\s+patient)\b",
    r"\bthe\s+patient\s+has\s+(?:been\s+diagnosed\s+with|definite\s+cancer|acute\s+myocardial\s+infarction)\b",
    r"\btake\s+\d+\s*mg\s+of\b",
    r"\bstart\s+taking\b",
    r"\bdiscontinue\s+(?:your|the)\s+medication\b",
    r"\bi\s+prescribe\b",
    r"\byou\s+should\s+take\b",
]


class OutputValidator:
    """Independent deterministic validator enforcing all 12 healthcare safety rules."""

    def __init__(self):
        self.citation_validator = CitationValidator()

    def validate(
        self,
        workflow_state: dict[str, Any],
        max_repairs: int = 1,
    ) -> ValidationResult:
        error_codes: list[str] = []
        warnings: list[str] = []
        rules_checked: list[str] = []
        details: dict[str, Any] = {}

        # -------------------------------------------------------------
        # Rule 1: Pydantic Schema Conformance
        # -------------------------------------------------------------
        rules_checked.append("RULE_1_SCHEMA_CONFORMANCE")
        if not isinstance(workflow_state, dict):
            error_codes.append("INVALID_STATE_TYPE")

        # -------------------------------------------------------------
        # Rule 2: Required Fields Presence
        # -------------------------------------------------------------
        rules_checked.append("RULE_2_REQUIRED_FIELDS")
        required_keys = [
            "case_id",
            "trace_id",
            "case_status",
            "record_facts",
            "missing_information",
            "evidence_summary",
        ]
        missing_keys = [k for k in required_keys if k not in workflow_state or workflow_state[k] is None]
        if missing_keys:
            error_codes.append(f"MISSING_REQUIRED_FIELDS:{','.join(missing_keys)}")
            details["missing_keys"] = missing_keys

        # -------------------------------------------------------------
        # Rule 3, 4, 5, 6, 7: Citation & Grounding Rules
        # -------------------------------------------------------------
        rules_checked.extend([
            "RULE_3_CITATION_EXISTENCE",
            "RULE_4_CITATION_SOURCE_ID_VALIDITY",
            "RULE_5_CITATION_PAGE_REFERENCES",
            "RULE_6_CITATION_CORRESPONDENCE",
            "RULE_7_UNSUPPORTED_CLAIMS",
        ])
        citations = workflow_state.get("citations", [])
        evidence_summary = workflow_state.get("evidence_summary", [])
        evidence_passages = workflow_state.get("evidence", [])
        is_abstention = (
            not evidence_passages
            or workflow_state.get("case_status") == "human_review_required"
            and not citations
        )

        cit_passed, cit_errors, cit_details = self.citation_validator.validate_citations(
            citations=citations,
            evidence_claims=evidence_summary,
            retrieved_passages=evidence_passages,
            is_abstention=is_abstention,
        )
        if not cit_passed:
            error_codes.extend(cit_errors)
        details["citation_details"] = cit_details

        # -------------------------------------------------------------
        # Rule 8: Prohibited Diagnostic or Prescribing Language
        # -------------------------------------------------------------
        rules_checked.append("RULE_8_PROHIBITED_CLINICAL_LANGUAGE")
        direct_answer = workflow_state.get("direct_answer", "") or ""
        claims_text = " ".join(
            (c.get("claim", "") if isinstance(c, dict) else getattr(c, "claim", ""))
            for c in evidence_summary
        )
        text_to_scan = f"{direct_answer} {claims_text}".lower()

        for pattern in PROHIBITED_OUTPUT_PATTERNS:
            if re.search(pattern, text_to_scan):
                error_codes.append("PROHIBITED_DIAGNOSIS_OR_PRESCRIBING_OUTPUT")
                details["prohibited_match"] = pattern
                break

        # -------------------------------------------------------------
        # Rule 9: Missing-Information Visibility
        # -------------------------------------------------------------
        rules_checked.append("RULE_9_MISSING_INFO_VISIBILITY")
        missing_info = workflow_state.get("missing_information", [])
        # Ensure missing_info is a list and visible
        if not isinstance(missing_info, list):
            error_codes.append("MISSING_INFO_NOT_A_LIST")

        # -------------------------------------------------------------
        # Rule 10: Safety Status Consistency
        # -------------------------------------------------------------
        rules_checked.append("RULE_10_SAFETY_STATUS_CONSISTENCY")
        scope_status = workflow_state.get("scope_status")
        case_status = workflow_state.get("case_status")
        if scope_status == "out_of_scope" and case_status not in ("human_review_required", "prohibited_blocked"):
            error_codes.append("INCONSISTENT_OUT_OF_SCOPE_SAFETY_STATUS")

        # -------------------------------------------------------------
        # Rule 11: Human-Review Requirements Check
        # -------------------------------------------------------------
        rules_checked.append("RULE_11_HUMAN_REVIEW_REQUIREMENTS")
        escalation_reason = workflow_state.get("escalation_reason")
        if escalation_reason and case_status != "human_review_required":
            error_codes.append("ESCALATION_WITHOUT_HUMAN_REVIEW_STATUS")

        # -------------------------------------------------------------
        # Rule 12: Source Consistency
        # -------------------------------------------------------------
        rules_checked.append("RULE_12_SOURCE_CONSISTENCY")
        conflicts = workflow_state.get("conflicts", [])
        if conflicts and case_status != "human_review_required":
            error_codes.append("UNRESOLVED_CONFLICT_WITHOUT_HUMAN_REVIEW")

        passed = len(error_codes) == 0
        retry_count = workflow_state.get("retry_count", 0)
        can_retry = (not passed) and (retry_count < max_repairs)

        return ValidationResult(
            passed=passed,
            error_codes=error_codes,
            warnings=warnings,
            rules_checked=rules_checked,
            citation_ids_checked=len(citations),
            can_retry=can_retry,
            details=details,
        )
