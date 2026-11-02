"""Agent 6: Summary Agent.
Generates structured, citation-grounded clinical evidence summaries using GroqCloud LLM.
Enforces strict boundaries: answers ONLY from verified facts and retrieved evidence,
never diagnoses or prescribes, explicitly abstains when evidence is missing,
and provides a controlled deterministic fallback when the LLM provider is unavailable.
"""
import logging
from typing import Any
from agents.generation import extract_salient_points
from agents.schemas import (
    CitationReference,
    EvidenceClaim,
    EvidenceQualityResult,
    PatientContextResult,
    RetrievedPassage,
    SafetyResult,
    SummaryDraftResult,
)
from llm.base import BaseLLMProvider
from llm.exceptions import LLMError
from llm.factory import get_llm_provider
from llm.schemas import LLMMessage

logger = logging.getLogger("healthcare_agentic_ai.agents.summary")

SYSTEM_PROMPT = """You are a specialized Clinical Evidence Summary Assistant in an educational decision-support prototype.
Your role is to prepare a structured clinical evidence draft strictly for review by a qualified healthcare professional.

MANDATORY CLINICAL GOVERNANCE RULES:
1. Ground every claim STRICTLY in the retrieved approved sources provided. Do not use outside medical knowledge.
2. Ground all patient context STRICTLY in the verified documented facts provided. NEVER invent, extrapolate, or infer missing patient facts (e.g. medications, vitals, allergies).
3. Under NO circumstances provide a medical diagnosis, medication prescription, dosage recommendation, or treatment alteration.
4. If the retrieved evidence is insufficient, explicitly state that in limitations and abstain from making ungrounded claims.
5. Every evidence claim MUST cite the exact 'source_id', 'section', and 'page' where it appears.
6. Return your response as a valid JSON object matching the requested schema.
"""


_DEFAULT_PROVIDER = object()


class SummaryAgent:
    """Orchestrates structured clinical summary generation via GroqCloud LLM with deterministic fallback."""

    def __init__(self, llm_provider: Any = _DEFAULT_PROVIDER, enable_llm: bool = True):
        self.enable_llm = enable_llm
        if not enable_llm or llm_provider is None:
            self.llm = None
        elif llm_provider is not _DEFAULT_PROVIDER:
            self.llm = llm_provider
        else:
            try:
                self.llm = get_llm_provider()
            except Exception as exc:
                logger.warning("Could not initialize default LLM provider: %s", exc)
                self.llm = None

    def _generate_deterministic_fallback(
        self,
        question: str,
        patient_facts: list[str],
        missing_info: list[str],
        evidence: list[RetrievedPassage],
        fallback_reason: str,
    ) -> SummaryDraftResult:
        """Deterministic extractive grounding used when LLM provider is unavailable or fails."""
        limitations = [
            "Educational decision-support prototype only. Not for clinical decision-making or diagnosis.",
            "All substantive claims must be verified by a licensed clinician against the original source documents.",
            f"Summary generation executed in deterministic extractive mode: {fallback_reason}",
        ]

        if not evidence:
            return SummaryDraftResult(
                direct_answer="No relevant supporting guidelines or biomedical literature were retrieved for this query.",
                key_findings=["No supporting source passages found in current index."],
                evidence_summary=[
                    EvidenceClaim(
                        claim="No supported evidence claim can be made from the indexed collection.",
                        source_id="NONE",
                        section="N/A",
                        page=None,
                        source_version="N/A",
                    )
                ],
                citations=[],
                limitations=limitations + ["Abstaining from clinical claims due to complete absence of retrieved evidence."],
                uncertainty_notes=["Total lack of supporting evidence in indexed guidelines."],
                missing_information=missing_info,
                human_review_recommendation="Escalate to clinical professional for direct literature and guideline search.",
                generation_mode=f"deterministic_extractive_abstention ({fallback_reason})",
            )

        citations = [
            CitationReference(
                source_id=e.source_id,
                title=e.document_title,
                section=e.section,
                page=e.page_number,
                version=e.version,
            )
            for e in evidence
        ]

        q_tokens = set(question.lower().split())
        findings: list[str] = []
        claims: list[EvidenceClaim] = []

        for e in evidence:
            salient = extract_salient_points(e.excerpt, list(q_tokens), max_points=2)
            if salient:
                for pt in salient:
                    findings.append(f"{pt} [{e.document_title}, p.{e.page_number or 'N/A'}]")
                    claims.append(
                        EvidenceClaim(
                            claim=pt,
                            source_id=e.source_id,
                            section=e.section,
                            page=e.page_number,
                            source_version=e.version,
                        )
                    )
            else:
                short_text = e.excerpt[:160].replace("\n", " ").strip() + "..."
                findings.append(f"{short_text} [{e.document_title}]")
                claims.append(
                    EvidenceClaim(
                        claim=f"Guideline excerpt from {e.section}: {short_text}",
                        source_id=e.source_id,
                        section=e.section,
                        page=e.page_number,
                        source_version=e.version,
                    )
                )

        top_doc = evidence[0].document_title
        top_sec = evidence[0].section
        top_text = evidence[0].excerpt[:240].replace("\n", " ").strip()
        direct_answer = (
            f"Based on {top_doc} ({top_sec}), the relevant guideline states: {top_text}... "
            "This summary is strictly extracted from approved WHO guidelines for clinician review."
        )
        if patient_facts:
            direct_answer += f" Evaluated in the context of verified patient facts: {', '.join(patient_facts)}."

        return SummaryDraftResult(
            direct_answer=direct_answer,
            key_findings=findings[:6],
            evidence_summary=claims[:8],
            citations=citations,
            limitations=limitations,
            uncertainty_notes=["Extractive synthesis without autonomous generative inference."],
            missing_information=missing_info,
            human_review_recommendation="Human clinician review required before taking any care coordination action.",
            generation_mode=f"deterministic_grounded_extractive ({fallback_reason})",
        )

    def execute(
        self,
        question: str,
        context_result: PatientContextResult,
        quality_result: EvidenceQualityResult,
        safety_result: SafetyResult,
    ) -> SummaryDraftResult:
        patient_facts = context_result.documented_facts
        missing_info = context_result.missing_information
        accepted_evidence = quality_result.accepted_evidence

        # If no approved evidence was retrieved, explicitly abstain rather than risk hallucination
        if not accepted_evidence:
            return self._generate_deterministic_fallback(
                question,
                patient_facts,
                missing_info,
                accepted_evidence,
                fallback_reason="No relevant approved evidence retrieved in index",
            )

        # Check if LLM provider is available
        if self.llm is None:
            return self._generate_deterministic_fallback(
                question,
                patient_facts,
                missing_info,
                accepted_evidence,
                fallback_reason="LLM provider uninitialized",
            )

        health = self.llm.health_check()
        if not health.available:
            return self._generate_deterministic_fallback(
                question,
                patient_facts,
                missing_info,
                accepted_evidence,
                fallback_reason=f"LLM provider unavailable: {health.message}",
            )

        # Build prompt for GroqCloud LLM structured generation
        evidence_text_blocks = []
        for idx, ev in enumerate(accepted_evidence, start=1):
            evidence_text_blocks.append(
                f"[Source {idx}]: ID={ev.source_id} | Title={ev.document_title} | Version={ev.version} | "
                f"Page={ev.page_number} | Section={ev.section}\nExcerpt: {ev.excerpt}\n"
            )

        user_content = (
            f"CLINICAL / SAFETY QUESTION: {question}\n\n"
            f"DOCUMENTED PATIENT FACTS (verified from record):\n"
            + ("\n".join(f"- {f}" for f in patient_facts) if patient_facts else "None supplied.\n")
            + f"\nCRITICAL MISSING INFORMATION (must NOT be inferred):\n"
            + ("\n".join(f"- {m}" for m in missing_info) if missing_info else "None detected.\n")
            + f"\nSAFETY RESTRICTIONS & POLICY REASONS:\n"
            + (f"Safety status: {safety_result.safety_status}. Escalation: {safety_result.escalation_reason or 'None'}\n")
            + f"\nRETRIEVED APPROVED EVIDENCE:\n"
            + ("\n".join(evidence_text_blocks) if evidence_text_blocks else "NO EVIDENCE RETRIEVED.\n")
        )

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        try:
            parsed_summary, response = self.llm.generate_structured(
                messages=messages,
                schema=SummaryDraftResult,
            )
            # Ensure model metadata and tokens are tracked
            parsed_summary.model_name = response.model
            parsed_summary.token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            parsed_summary.generation_mode = f"groq_llm_structured ({response.model})"
            return parsed_summary

        except LLMError as exc:
            logger.warning("GroqCloud LLM call failed (%s). Falling back safely to deterministic extractive mode.", exc)
            fallback = self._generate_deterministic_fallback(
                question,
                patient_facts,
                missing_info,
                accepted_evidence,
                fallback_reason=f"GroqCloud invocation failed safely: {exc.message}",
            )
            return fallback
        except Exception as exc:
            logger.error("Unexpected error in SummaryAgent: %s", exc)
            fallback = self._generate_deterministic_fallback(
                question,
                patient_facts,
                missing_info,
                accepted_evidence,
                fallback_reason=f"Unexpected summary generation failure: {exc}",
            )
            return fallback
