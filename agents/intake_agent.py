"""Agent 1: Intake & Scope Agent.
Classifies requests, normalizes questions, checks prototype boundaries, and enforces deterministic scope rules.
"""
import re
from agents.schemas import IntakeInput, IntakeResult

# Deterministic boundary keywords
PROHIBITED_DIAGNOSIS_PATTERNS = [
    r"\bdiagnose\s+(?:me|my|this\s+patient)\b",
    r"\bwhat\s+(?:disease|illness|condition)\s+do\s+i\s+have\b",
    r"\bgive\s+(?:me\s+)?a\s+diagnosis\b",
    r"\bdo\s+i\s+have\s+(?:cancer|pneumonia|asthma|diabetes|covid|heart\s+attack)\b",
]

PROHIBITED_PRESCRIBING_PATTERNS = [
    r"\bprescribe\b",
    r"\bwhat\s+(?:medication|drug|pill|dose)\s+should\s+(?:i|we)\s+(?:take|give|prescribe|start)\b",
    r"\bchange\s+(?:my|the)\s+medication\b",
    r"\bincrease\s+(?:my|the)\s+dosage\b",
    r"\bstop\s+taking\s+(?:my|the)\s+medication\b",
]

PROHIBITED_TRIAGE_PATTERNS = [
    r"\bshould\s+i\s+go\s+to\s+the\s+er\b",
    r"\bis\s+this\s+a\s+medical\s+emergency\b",
    r"\btriage\s+(?:me|this\s+case)\b",
]


class IntakeScopeAgent:
    """Enforces clinical boundaries and structures the intake query."""

    def normalize_question(self, question: str) -> str:
        """Sanitize control chars, normalize whitespace, and trim."""
        if not question:
            return ""
        # Remove null bytes or non-printable chars
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", question)
        # Collapse multiple spaces and line breaks
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def execute(self, payload: IntakeInput) -> IntakeResult:
        raw_q = payload.question or ""
        normalized = self.normalize_question(raw_q)
        q_lower = normalized.lower()

        reason_codes = []
        is_diag = any(re.search(pat, q_lower) for pat in PROHIBITED_DIAGNOSIS_PATTERNS)
        is_prescribe = any(re.search(pat, q_lower) for pat in PROHIBITED_PRESCRIBING_PATTERNS)
        is_triage = any(re.search(pat, q_lower) for pat in PROHIBITED_TRIAGE_PATTERNS)

        required_fields = ["question", "case_id"]
        missing_fields = []
        if len(normalized) < 5:
            missing_fields.append("clinical_query_substance")
            reason_codes.append("QUERY_TOO_SHORT")

        if is_diag:
            reason_codes.append("PROHIBITED_DIAGNOSTIC_REQUEST")
            return IntakeResult(
                request_type="definitive_diagnosis_request",
                normalized_question=normalized,
                scope_status="out_of_scope",
                required_fields=required_fields,
                missing_fields=missing_fields,
                clarification_prompt=(
                    "The system cannot provide definitive medical diagnoses. "
                    "Please reframe the request to ask for published guidelines or clinical evidence regarding symptoms or conditions."
                ),
                reason_codes=reason_codes,
            )

        if is_prescribe:
            reason_codes.append("PROHIBITED_PRESCRIBING_REQUEST")
            return IntakeResult(
                request_type="medication_prescribing_request",
                normalized_question=normalized,
                scope_status="out_of_scope",
                required_fields=required_fields,
                missing_fields=missing_fields,
                clarification_prompt=(
                    "The system cannot prescribe, adjust dosages, or recommend specific medication changes. "
                    "Please consult a licensed prescriber or request general medication safety guidelines."
                ),
                reason_codes=reason_codes,
            )

        if is_triage:
            reason_codes.append("PROHIBITED_TRIAGE_REQUEST")
            return IntakeResult(
                request_type="triage_request",
                normalized_question=normalized,
                scope_status="out_of_scope",
                required_fields=required_fields,
                missing_fields=missing_fields,
                clarification_prompt=(
                    "The system cannot perform acute patient triage or emergency assessment. "
                    "For acute or life-threatening symptoms, immediate emergency medical attention is required."
                ),
                reason_codes=reason_codes,
            )

        # Within scope
        reason_codes.append("CLINICAL_EVIDENCE_SCOPE_VALID")
        return IntakeResult(
            request_type="clinical_evidence_summary",
            normalized_question=normalized,
            scope_status="within_prototype_scope",
            required_fields=required_fields,
            missing_fields=missing_fields,
            clarification_prompt=None,
            reason_codes=reason_codes,
        )
