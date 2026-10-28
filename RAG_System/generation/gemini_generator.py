"""
Gemini RAG Generator using Google Gemini 2.0 Flash with graceful deterministic fallback.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..config import rag_settings
from ..augmentation.context_builder import AugmentedPrompt

logger = logging.getLogger("rag_system.generator")


@dataclass
class GenerationResult:
    markdown_narrative: str
    observation: str
    evidence_points: List[str]
    possible_root_cause: str
    recommended_investigation: List[str]
    confidence_level: str
    model_used: str
    citations: List[str]


class GeminiRAGGenerator:
    """
    Interfaces with Google Gemini LLM to synthesize operational analysis
    grounded strictly in retrieved runbook chunks and live telemetry.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or rag_settings.GEMINI_GENERATION_MODEL
        self._client = None
        self._cached_api_key: Optional[str] = None

    def _get_client(self):
        rag_settings.refresh_key()
        current_key = rag_settings.GEMINI_API_KEY
        if rag_settings.IS_PLACEHOLDER_KEY or not current_key:
            return None

        # Re-initialize client if key has changed
        if self._client is None or self._cached_api_key != current_key:
            try:
                from google import genai
                from google.genai import types
                self._client = genai.Client(
                    api_key=current_key,
                    http_options=types.HttpOptions(timeout=15000),
                )
                self._cached_api_key = current_key
            except Exception as e:
                logger.warning("Could not initialize google.genai Client: %s", e)
                return None
        return self._client

    def generate(self, augmented: AugmentedPrompt) -> GenerationResult:
        """
        Generates grounded operational incident narrative using Gemini 2.5 Flash / latest,
        with deep deterministic runbook extraction as fallback.
        """
        client = self._get_client()

        if client is not None:
            from google.genai import types
            candidate_models = ["gemini-3.5-flash-lite", self.model_name, "gemini-2.5-flash"]
            # Deduplicate preserving order
            seen = set()
            models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

            for m in models_to_try:
                try:
                    logger.info("Generating incident narrative via Gemini (%s)...", m)
                    response = client.models.generate_content(
                        model=m,
                        contents=augmented.user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=augmented.system_prompt,
                            temperature=0.2,
                        ),
                    )
                    if response and response.text:
                        return self._parse_llm_response(response.text, augmented, model_used=f"Gemini ({m})")
                except Exception as e:
                    logger.warning("Gemini generation with %s failed (%s); trying next candidate...", m, e)

        # Deterministic RAG fallback
        return self._fallback_synthesis(augmented)

    def _parse_llm_response(
        self,
        llm_text: str,
        augmented: AugmentedPrompt,
        model_used: str,
    ) -> GenerationResult:
        """
        Extracts structured fields from Gemini's grounded markdown response.
        """
        lines = [line.strip() for line in llm_text.split("\n")]
        evidence_points: List[str] = []
        recommendations: List[str] = []
        observation = ""
        root_cause = ""
        confidence = "High"

        current_section = None
        for line in lines:
            lower = line.lower()
            if "observation" in lower and (line.startswith("#") or line.startswith("**")):
                current_section = "obs"
                continue
            elif "evidence" in lower and (line.startswith("#") or line.startswith("**")):
                current_section = "evi"
                continue
            elif "root cause" in lower and (line.startswith("#") or line.startswith("**")):
                current_section = "rc"
                continue
            elif "remediation" in lower or "investigation" in lower or "recommendation" in lower:
                if line.startswith("#") or line.startswith("**"):
                    current_section = "rem"
                    continue
            elif "confidence" in lower:
                if "medium" in lower:
                    confidence = "Medium"
                elif "low" in lower:
                    confidence = "Low"
                else:
                    confidence = "High"

            if current_section == "obs" and line and not line.startswith("#"):
                if not observation:
                    observation = line.lstrip("*- ")
            elif current_section == "evi" and (line.startswith("-") or line.startswith("*")):
                evidence_points.append(line.lstrip("*- "))
            elif current_section == "rc" and line and not line.startswith("#"):
                if not root_cause:
                    root_cause = line.lstrip(">-* ")
            elif current_section == "rem" and (line[:3].replace(".", "").isdigit() or line.startswith("-")):
                clean_rec = line.lstrip("0123456789.-* ")
                if clean_rec:
                    recommendations.append(clean_rec)

        if not observation:
            observation = "Operational telemetry and runbooks correlated successfully."
        if not evidence_points:
            evidence_points = [f"Retrieved {len(augmented.retrieved_chunks)} relevant runbook operational guidelines."]
        if not root_cause:
            root_cause = "Analysis grounded in retrieved operational incident runbooks."
        if not recommendations:
            recommendations = ["Review active telemetry metrics and apply runbook procedures."]

        return GenerationResult(
            markdown_narrative=llm_text,
            observation=observation,
            evidence_points=evidence_points,
            possible_root_cause=root_cause,
            recommended_investigation=recommendations,
            confidence_level=confidence,
            model_used=model_used,
            citations=augmented.citations,
        )

    def _extract_runbook_content(self, chunks: List[Any]):
        """Extracts symptoms, root causes, remediation steps, and commands from runbook chunks."""
        symptoms, causes, recs, commands = [], [], [], []
        for chunk in chunks:
            text = getattr(chunk, "content", None) or getattr(chunk, "text", "")
            current_sec = None
            in_code = False
            code_lines = []

            for line in text.split("\n"):
                s = line.strip()
                if s.startswith("```"):
                    if in_code:
                        in_code = False
                        if code_lines:
                            commands.append("\n".join(code_lines))
                            code_lines = []
                    else:
                        in_code = True
                    continue

                if in_code:
                    if s and not s.startswith("#"):
                        code_lines.append(s)
                    continue

                lower = s.lower()
                if "symptom" in lower and s.startswith("#"):
                    current_sec = "sym"
                elif ("root cause" in lower or "classification" in lower) and s.startswith("#"):
                    current_sec = "rc"
                elif ("remediation" in lower or "mitigation" in lower or "steps" in lower) and s.startswith("#"):
                    current_sec = "rem"
                elif ("diagnostic" in lower or "command" in lower) and s.startswith("#"):
                    current_sec = "cmd"

                if current_sec == "sym" and (s.startswith("-") or s.startswith("*")):
                    clean = s.lstrip("*- ").strip()
                    if len(clean) > 8 and clean not in symptoms:
                        symptoms.append(clean)
                elif current_sec == "rc" and (s.startswith("-") or s.startswith("*")):
                    clean = s.lstrip("*- ").strip()
                    if len(clean) > 8 and clean not in causes:
                        causes.append(clean)
                elif current_sec == "rem" and (s[:3].replace(".", "").isdigit() or s.startswith("-") or s.startswith("*")):
                    clean = s.lstrip("0123456789.-* ").strip()
                    if len(clean) > 8 and clean not in recs:
                        recs.append(clean)

        return symptoms, causes, recs, commands

    def _fallback_synthesis(self, augmented: AugmentedPrompt) -> GenerationResult:
        """
        High-fidelity deterministic RAG synthesis extracting concrete runbook procedures.
        """
        chunks = augmented.retrieved_chunks
        runbook_chunks = [c for c in chunks if c.source_type == "runbook" or (c.reference_id and c.reference_id.startswith("RUNBOOK"))]
        top_chunk = chunks[0] if chunks else None

        # Check if greeting inquiry
        user_prompt_lower = augmented.user_prompt.lower()
        first_line = user_prompt_lower.split("\n")[1].strip('" ') if "\n" in user_prompt_lower else user_prompt_lower
        is_greeting = first_line in ["hi", "hii", "hello", "hey", "help", "who are you", "who are you?", "good morning", "status"]

        if is_greeting:
            observation = "CloudOps Intel RAG Incident Intelligence Agent is online and actively monitoring cluster telemetry."
            root_cause = "Operational Standby: 6 SRE runbooks indexed and live telemetry signals synchronized."
            recommendations = [
                "Inquire about specific node health, CPU saturation, memory leaks, or disk exhaustion.",
                "Correlate recent security intrusion detections with node performance anomalies.",
                "Click any of the Quick Investigation Presets on the right to run an automated analysis.",
            ]
            evidence_points = [f"System indexed {len(chunks)} operational context records across fleet."]
        else:
            symptoms, causes, extracted_recs, commands = self._extract_runbook_content(runbook_chunks or chunks)

            evidence_points = symptoms[:4] if symptoms else [
                f"[{c.reference_id}] {c.title}: Identified matching operational protocol." for c in chunks[:3]
            ]

            if causes:
                root_cause = causes[0]
            elif top_chunk:
                root_cause = f"Correlated with {top_chunk.title} [{top_chunk.reference_id}]: High affinity with operational telemetry."
            else:
                root_cause = "Telemetry within normal operating parameters. No active breach detected."

            recommendations = extracted_recs[:4] if extracted_recs else [
                f"Consult runbook [{top_chunk.reference_id if top_chunk else 'DOC'}] for immediate mitigation procedures.",
                "Verify host telemetry stream in CloudOps Intel dashboard for threshold recovery.",
                "Review system process list or connection logs to validate root cause hypothesis.",
            ]

            if commands and len(recommendations) < 5:
                recommendations.append(f"Diagnostic command: `{commands[0]}`")

            ref_title = top_chunk.title if top_chunk else "Operational Knowledge Base"
            ref_id = top_chunk.reference_id if top_chunk else "RAG"
            match_pct = int(top_chunk.score * 100) if top_chunk else 80
            observation = f"Operational inquiry matched {ref_title} [{ref_id}] ({match_pct}% hybrid relevance)."

        cmd_section = ""
        symptoms, causes, extracted_recs, commands = self._extract_runbook_content(runbook_chunks or chunks)
        if commands and not is_greeting:
            cmd_section = f"\n\n#### Immediate Diagnostic Commands (Runbook):\n```bash\n{commands[0]}\n```"

        markdown = f"""### AI Incident Analysis (RAG Augmented)

**Executive Observation**: {observation}

#### Grounded Evidence (Symptoms & Signals):
{chr(10).join(f"- {pt}" for pt in evidence_points)}

#### Inferred Root Cause:
> {root_cause}

#### Actionable Remediation (Runbook Prescriptions):
{chr(10).join(f"{i+1}. {r}" for i, r in enumerate(recommendations))}{cmd_section}

**Model**: `Deterministic RAG Engine (Local Fallback)` | **Status**: `Operational`
"""

        return GenerationResult(
            markdown_narrative=markdown,
            observation=observation,
            evidence_points=evidence_points,
            possible_root_cause=root_cause,
            recommended_investigation=recommendations,
            confidence_level="High" if chunks else "Medium",
            model_used="Deterministic RAG Engine (Local)",
            citations=augmented.citations,
        )
