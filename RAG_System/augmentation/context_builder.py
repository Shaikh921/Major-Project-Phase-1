"""
Context builder formatting retrieved knowledge chunks and live telemetry into grounded prompts.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from ..retrieval.retriever import RetrievedChunk
from .prompt_templates import SYSTEM_SRE_PROMPT, build_user_prompt


@dataclass
class AugmentedPrompt:
    system_prompt: str
    user_prompt: str
    citations: List[str]
    retrieved_chunks: List[RetrievedChunk]


class ContextBuilder:
    """
    Assembles retrieved runbooks and live operational records into an augmented prompt.
    """

    def build_context(
        self,
        query: str,
        retrieved_chunks: List[RetrievedChunk],
        live_signals: Dict[str, Any],
        time_window_minutes: int = 60,
    ) -> AugmentedPrompt:
        """
        Builds the complete grounded prompt and list of citations.
        """
        # Format Runbooks / Knowledge context
        context_blocks = []
        citations = []

        for idx, chunk in enumerate(retrieved_chunks, 1):
            ref_tag = chunk.reference_id or f"DOC-{idx}"
            citations.append(chunk.to_citation())
            context_blocks.append(
                f"--- DOCUMENT {idx} [{ref_tag}]: {chunk.title} ---\n"
                f"{chunk.content}\n"
            )

        context_text = "\n".join(context_blocks)

        # Format live telemetry signals
        telemetry_lines = []
        alerts = live_signals.get("alerts", [])
        sec_events = live_signals.get("security_events", [])
        cost_recs = live_signals.get("cost_recommendations", [])
        hosts = live_signals.get("hosts", [])

        if hosts:
            host_names = [h.get("hostname", str(h.get("id"))) for h in hosts]
            telemetry_lines.append(f"Target Hosts Monitored ({len(hosts)}): {', '.join(host_names)}")

        if alerts:
            telemetry_lines.append(f"\nActive Alerts ({len(alerts)}):")
            for a in alerts[:10]:
                ref = f"ALERT-#{a.get('id', 'N/A')}"
                citations.append(f"[{ref}] Host {a.get('hostname', 'unknown')}: {a.get('metric')}={a.get('value', 0):.1f} ({a.get('severity')})")
                telemetry_lines.append(
                    f"  - [{ref}] Severity: {a.get('severity', 'info').upper()} | Host: {a.get('hostname', 'unknown')} | "
                    f"Metric: {a.get('metric')}={a.get('value', 0):.1f} (Threshold: {a.get('threshold', 0):.1f}) | Message: {a.get('message', '')}"
                )

        if sec_events:
            telemetry_lines.append(f"\nRecent Security Events ({len(sec_events)}):")
            for s in sec_events[:10]:
                ref = f"SECURITY-#{s.get('id', 'N/A')}"
                citations.append(f"[{ref}] {s.get('event_type')}: {s.get('description')}")
                telemetry_lines.append(
                    f"  - [{ref}] Type: {s.get('event_type')} | Severity: {s.get('severity')} | Host: {s.get('hostname', 'perimeter')} | Detail: {s.get('description')}"
                )

        if cost_recs:
            telemetry_lines.append(f"\nCost Optimization Opportunities ({len(cost_recs)}):")
            for c in cost_recs[:5]:
                ref = f"COST-#{c.get('id', 'N/A')}"
                citations.append(f"[{ref}] {c.get('recommendation_type')} (Savings: ${c.get('savings', 0):.2f}/mo)")
                telemetry_lines.append(
                    f"  - [{ref}] Type: {c.get('recommendation_type')} | Host: {c.get('hostname', 'cloud')} | Potential Savings: ${c.get('savings', 0):.2f}/mo"
                )

        telemetry_summary = "\n".join(telemetry_lines)

        user_prompt = build_user_prompt(
            query=query,
            context_text=context_text,
            telemetry_summary=telemetry_summary,
            time_window_minutes=time_window_minutes,
        )

        return AugmentedPrompt(
            system_prompt=SYSTEM_SRE_PROMPT,
            user_prompt=user_prompt,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
        )
