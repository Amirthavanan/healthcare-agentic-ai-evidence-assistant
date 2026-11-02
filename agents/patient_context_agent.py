"""Agent 2: Patient Context Agent.
Extracts strictly supplied patient facts, dates, medications, allergies, and history.
Maintains fact provenance and guarantees unknown fields remain unknown (never inferred).
"""
import re
from agents.schemas import FactProvenance, PatientContextInput, PatientContextResult

DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)


class PatientContextAgent:
    """Extracts documented patient record facts without inferring missing clinical details."""

    def execute(self, payload: PatientContextInput) -> PatientContextResult:
        provenance: list[FactProvenance] = []
        warnings: list[FactProvenance] = []
        documented_facts: list[str] = []

        # 1. Documented narrative facts
        for idx, fact_str in enumerate(payload.documented_facts or []):
            clean_fact = fact_str.strip()
            if clean_fact:
                documented_facts.append(clean_fact)
                provenance.append(
                    FactProvenance(
                        field="documented_facts",
                        value=clean_fact,
                        source_location=f"supplied_user_record.facts[{idx}]",
                    )
                )

        # 2. Medications
        medications: list[str] = []
        if payload.medications is not None:
            for idx, med in enumerate(payload.medications):
                clean_med = med.strip()
                if clean_med:
                    medications.append(clean_med)
                    provenance.append(
                        FactProvenance(
                            field="medications",
                            value=clean_med,
                            source_location=f"supplied_user_record.medications[{idx}]",
                        )
                    )

        # 3. Allergies
        allergies: list[str] = []
        if payload.allergies is not None:
            for idx, alg in enumerate(payload.allergies):
                clean_alg = alg.strip()
                if clean_alg:
                    allergies.append(clean_alg)
                    provenance.append(
                        FactProvenance(
                            field="allergies",
                            value=clean_alg,
                            source_location=f"supplied_user_record.allergies[{idx}]",
                        )
                    )

        # 4. Vital signs
        vital_signs = payload.vital_signs or {}
        for k, v in vital_signs.items():
            provenance.append(
                FactProvenance(
                    field=f"vital_signs.{k}",
                    value=str(v),
                    source_location=f"supplied_user_record.vital_signs.{k}",
                )
            )

        # 5. Symptom duration
        symptom_duration = payload.symptom_duration
        if symptom_duration:
            provenance.append(
                FactProvenance(
                    field="symptom_duration",
                    value=symptom_duration,
                    source_location="supplied_user_record.symptom_duration",
                )
            )

        # 6. Relevant history extraction from narrative facts (dates & chronic conditions)
        relevant_history: list[str] = []
        for fact in documented_facts:
            # Check if fact mentions past history, prior diagnosis, or dates
            has_date = bool(DATE_PATTERN.search(fact))
            lower_fact = fact.lower()
            if (
                "history" in lower_fact
                or "diagnosed" in lower_fact
                or "prior" in lower_fact
                or "chronic" in lower_fact
                or has_date
            ):
                relevant_history.append(fact)

        # 7. Identify missing required clinical information (CRITICAL: Never infer them)
        missing_info: list[str] = []
        extraction_warnings: list[str] = []

        if payload.medications is None or len(medications) == 0:
            missing_info.append("Current medication list")
            extraction_warnings.append(
                "Medication list was not provided. In accordance with safety policy, no medications are inferred."
            )

        if payload.allergies is None or len(allergies) == 0:
            missing_info.append("Allergy information")

        if not vital_signs:
            missing_info.append("Vital signs")

        if not symptom_duration:
            missing_info.append("Symptom duration")

        return PatientContextResult(
            documented_facts=documented_facts,
            medications=medications,
            allergies=allergies,
            relevant_history=relevant_history,
            vital_signs=vital_signs,
            symptom_duration=symptom_duration,
            fact_provenance=provenance,
            missing_information=missing_info,
            extraction_warnings=extraction_warnings,
        )
