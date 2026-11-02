"""Agent 5: Safety & Policy Agent.
Enforces strict healthcare safety policies, prompt-injection defense against untrusted retrieval content,
privacy sanitization, and human-review escalation routing.
"""
import re
from typing import Any
from agents.schemas import (
    EvidenceQualityResult,
    IntakeResult,
    PatientContextResult,
    SafetyResult,
)

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"disregard\s+(?:the\s+)?system\s+prompt",
    r"you\s+are\s+now\s+(?:an?\s+unrestricted|in\s+developer\s+mode|dan)",
    r"override\s+system\s+(?:policy|rules)",
    r"ignore\s+safety\s+(?:checks|disclaimers)",
    r"act\s+as\s+a\s+doctor\s+and\s+prescribe",
]

SENSITIVE_DATA_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # US SSN
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b",  # Credit Card
]


class SafetyPolicyAgent:
    """Enforces clinical boundaries, prompt injection resistance, and privacy safety."""

    def detect_prompt_injection(self, text: str) -> bool:
        """Scan text for adversarial prompt injection attempts."""
        if not text:
            return False
        lower = text.lower()
        return any(re.search(pat, lower) for pat in PROMPT_INJECTION_PATTERNS)

    def detect_sensitive_data(self, text: str) -> bool:
        """Scan text for sensitive identification numbers (SSN, payment card)."""
        if not text:
            return False
        return any(re.search(pat, text) for pat in SENSITIVE_DATA_PATTERNS)

    def execute(
        self,
        intake_result: IntakeResult,
        context_result: PatientContextResult,
        quality_result: EvidenceQualityResult,
        retrieved_raw_texts: list[str] | None = None,
    ) -> SafetyResult:
        reason_codes: list[str] = []
        policy_violations: list[str] = []
        review_required = False
        prompt_injection_flag = False
        sensitive_data_flag = False

        # 1. Scope Boundary Enforcement
        if intake_result.scope_status == "out_of_scope":
            review_required = True
            policy_violations.append(f"Scope violation: Request is classified as '{intake_result.request_type}'.")
            reason_codes.append("OUT_OF_SCOPE_REQUEST")

        # 2. Prompt Injection Defense on Untrusted Retrieved Documents
        for raw_text in (retrieved_raw_texts or []):
            if self.detect_prompt_injection(raw_text):
                prompt_injection_flag = True
                policy_violations.append(
                    "Prompt injection pattern detected in retrieved document content. "
                    "Untrusted document instructions have been quarantined and neutralized."
                )
                reason_codes.append("PROMPT_INJECTION_NEUTRALIZED")
                break

        # Also check question for prompt injection
        if self.detect_prompt_injection(intake_result.normalized_question):
            prompt_injection_flag = True
            review_required = True
            policy_violations.append("Adversarial prompt injection detected in user clinical query.")
            reason_codes.append("USER_PROMPT_INJECTION")

        # 3. Privacy / Sensitive Data Screening
        combined_text = (
            intake_result.normalized_question
            + " "
            + " ".join(context_result.documented_facts)
        )
        if self.detect_sensitive_data(combined_text):
            sensitive_data_flag = True
            reason_codes.append("SENSITIVE_DATA_MINIMIZED")

        # 4. Incomplete Patient Context
        if context_result.missing_information:
            review_required = True
            reason_codes.append("CONTEXT_INCOMPLETE")

        # 5. Evidence Quality & Conflict Escalation
        if quality_result.evidence_quality_status == "insufficient":
            review_required = True
            reason_codes.append("INSUFFICIENT_EVIDENCE")
        elif quality_result.evidence_quality_status == "conflicting":
            review_required = True
            reason_codes.append("CONFLICTING_SOURCES_REQUIRE_HUMAN_REVIEW")
        elif quality_result.evidence_quality_status == "mixed":
            reason_codes.append("EVIDENCE_FRESHNESS_WARNING")

        # Determine overall safety status and safe next step
        if prompt_injection_flag and intake_result.scope_status == "out_of_scope":
            safety_status = "prohibited_blocked"
            safe_next_step = "Reject prohibited query. Instruct user to contact clinical provider directly."
            escalation_reason = "Query attempts prohibited medical action with adversarial injection."
        elif review_required:
            safety_status = "human_review_required"
            escalation_reasons = []
            if "OUT_OF_SCOPE_REQUEST" in reason_codes:
                escalation_reasons.append("Clinical scope limits reached (prohibited diagnosis/prescribing).")
            if "CONTEXT_INCOMPLETE" in reason_codes:
                escalation_reasons.append(f"Incomplete patient facts ({', '.join(context_result.missing_information)}).")
            if "INSUFFICIENT_EVIDENCE" in reason_codes:
                escalation_reasons.append("Zero supporting guidelines retrieved.")
            if "CONFLICTING_SOURCES_REQUIRE_HUMAN_REVIEW" in reason_codes:
                escalation_reasons.append("Retrieved guidelines disagree or contain conflicting recommendations.")
            escalation_reason = " ".join(escalation_reasons)
            safe_next_step = (
                "Route to qualified healthcare professional. Do not rely autonomously on generated summary."
            )
        else:
            safety_status = "safe"
            escalation_reason = None
            safe_next_step = "Qualified healthcare professional may review grounded guideline evidence."

        return SafetyResult(
            safety_status=safety_status,
            review_required=review_required,
            reason_codes=list(set(reason_codes)),
            escalation_reason=escalation_reason,
            safe_next_step=safe_next_step,
            policy_violations=policy_violations,
            prompt_injection_detected=prompt_injection_flag,
            sensitive_data_flagged=sensitive_data_flag,
        )
