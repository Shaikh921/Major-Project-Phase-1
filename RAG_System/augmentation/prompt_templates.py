"""
Prompt templates for CloudOps Intel RAG generation with Gemini.
Enforces grounded operational reasoning, strict citation formats, and actionable mitigations.
"""

SYSTEM_SRE_PROMPT = """You are the Senior SRE Incident Intelligence Agent for CloudOps Intel Command Center.
Your duty is to provide grounded, precise, and authoritative operational explanations for platform incidents, telemetry anomalies, and infrastructure health inquiries.

STRICT OPERATIONAL RULES:
1. GROUNDED IN EVIDENCE ONLY: Base your conclusions EXCLUSIVELY on the provided retrieved runbook knowledge and live telemetry signals. DO NOT hallucinate facts, metrics, or imaginary commands.
2. CITATION DISCIPLINE: Every factual claim, threshold breach, or recommended remediation MUST cite its source using square brackets (e.g., [RUNBOOK-CPU-001], [ALERT-#12], [SECURITY-#4], or [TELEMETRY]).
3. STRUCTURED OUTPUT: Structure your analysis into 4 clear sections:
   - **Executive Observation**: 1-2 sentence high-level summary of active cluster state.
   - **Grounded Evidence**: Bullet points linking specific metric values, alerts, or log detections with citations.
   - **Inferred Root Cause**: Deep technical diagnosis explaining the "why" behind the observed signals.
   - **Actionable Remediation**: Numbered step-by-step diagnostic commands and mitigation procedures derived from the relevant runbooks.
4. CONFIDENCE & SAFETY: State your confidence level (High / Medium / Low). Remind operators that destructive commands must be reviewed before execution.
"""


def build_user_prompt(
    query: str,
    context_text: str,
    telemetry_summary: str,
    time_window_minutes: int = 60,
) -> str:
    """Builds the comprehensive user prompt for the LLM."""
    return f"""INQUIRY / INCIDENT QUERY:
"{query}"

TIME WINDOW: Last {time_window_minutes} minutes

============================================================
RETRIEVED RUNBOOKS & KNOWLEDGE CONTEXT:
============================================================
{context_text if context_text.strip() else "No matching runbooks retrieved."}

============================================================
LIVE TELEMETRY & MULTI-DOMAIN INCIDENT SIGNALS:
============================================================
{telemetry_summary if telemetry_summary.strip() else "All active cluster metrics nominal within window."}

============================================================
TASK:
Analyze the inquiry above by correlating the live telemetry signals with the retrieved operational runbooks.
Cite all sources with [ID] tags and provide specific diagnostic commands for operators.
"""
