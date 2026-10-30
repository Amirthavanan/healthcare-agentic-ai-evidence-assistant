import os
import re
from typing import Any

DISCLAIMER = (
    "Educational and clinical review prototype only. Not for clinical decision-making, "
    "diagnosis, triage, or prescribing. Real-world decisions require qualified clinical review."
)


def extract_salient_points(text: str, query_tokens: list[str], max_points: int = 4) -> list[str]:
    """Extract sentences from text that overlap most with query tokens."""
    # Split text into sentences or bullet items
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n- |\n\*\s+", text)
    scored = []
    for s in raw_sentences:
        s_clean = s.strip().removeprefix("- ").removeprefix("* ").strip()
        if len(s_clean) < 25 or len(s_clean) > 350:
            continue
        words = set(re.findall(r"[a-z0-9]+", s_clean.lower()))
        overlap = len(words.intersection(query_tokens))
        if overlap > 0:
            scored.append((overlap, s_clean))

    scored.sort(key=lambda x: x[0], reverse=True)
    points = []
    seen = set()
    for _, sent in scored:
        normalized = sent.lower()[:60]
        if normalized not in seen:
            seen.add(normalized)
            points.append(sent)
        if len(points) >= max_points:
            break
    return points


def generate_grounded_answer(
    question: str,
    patient_facts: list[str],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Synthesize an evidence-grounded answer from retrieved document chunks."""
    if not evidence:
        return {
            "direct_answer": "No relevant supporting evidence was found in the indexed source documents.",
            "key_findings": ["No supporting documents retrieved matching the query terms."],
            "evidence_summary": [
                {
                    "claim": "No supported evidence claim can be made from the current source collection.",
                    "source_id": "NONE",
                    "section": "N/A",
                    "source_version": "N/A",
                    "page": None,
                }
            ],
            "citations": [],
            "generation_mode": "deterministic_fallback_no_evidence",
        }

    q_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))

    # Build structured key findings from retrieved chunks
    findings = []
    evidence_summary = []
    citations = []

    for item in evidence:
        source_id = item.get("source_id") or item.get("id", "UNKNOWN")
        title = item.get("title", "Clinical Document")
        section = item.get("section", "General")
        page = item.get("page")
        version = item.get("version", "2021")
        text = item.get("excerpt") or item.get("text", "")

        citations.append({
            "source_id": source_id,
            "title": title,
            "page": page,
            "section": section,
            "version": version,
        })

        salient = extract_salient_points(text, q_tokens, max_points=2)
        if salient:
            for pt in salient:
                findings.append(f"{pt} [{title}, {section}]")
                evidence_summary.append({
                    "claim": pt,
                    "source_id": source_id,
                    "section": section,
                    "source_version": version,
                    "page": page,
                })
        else:
            # Fallback concise claim
            short_excerpt = text[:180].replace("\n", " ").strip() + "..."
            findings.append(f"{short_excerpt} [{title}, {section}]")
            evidence_summary.append({
                "claim": f"Evidence documented in {section}: {short_excerpt}",
                "source_id": source_id,
                "section": section,
                "source_version": version,
                "page": page,
            })

    # Direct Answer Synthesis
    top_source = evidence[0].get("title", "the retrieved guidelines")
    top_section = evidence[0].get("section", "")
    top_excerpt = (evidence[0].get("excerpt") or evidence[0].get("text", ""))[:300].replace("\n", " ").strip()

    direct_answer = (
        f"Based on {top_source} ({top_section}), the available evidence indicates: "
        f"{top_excerpt}... This evidence summary is derived directly from the indexed WHO sources."
    )

    if patient_facts:
        direct_answer += f" Evaluated in the context of documented patient facts: {', '.join(patient_facts)}."

    return {
        "direct_answer": direct_answer,
        "key_findings": findings[:6],
        "evidence_summary": evidence_summary[:8],
        "citations": citations,
        "generation_mode": "deterministic_grounded_extractive",
    }
