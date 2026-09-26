"""
Cost Optimization Service.

Calculates instance spend, detects idle/underutilized assets, and serves
actionable rightsizing recommendations (M3).
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.cost import CostRecommendation, PricingCatalog
from backend.app.schemas.cost import (
    CostRecommendationRead,
    CostRecommendationAction,
    CostByResource,
    CostSummaryResponse,
)
from cost_engine.calculator import CostCalculator, STANDARD_PRICING_CATALOG

_calculator = CostCalculator()


def generate_fleet_cost_analysis(db: Session) -> CostSummaryResponse:
    """
    Computes spend across all registered hosts based on their instance types
    and historical CPU/memory utilization.
    """
    hosts = list(db.scalars(select(Host).where(Host.is_active == True)).all())
    
    total_monthly_spend = 0.0
    total_potential_savings = 0.0
    idle_count = 0
    underutilized_count = 0
    spend_by_env: Dict[str, float] = {}
    resource_costs: List[CostByResource] = []

    for h in hosts:
        cost = _calculator.get_instance_monthly_cost(h.instance_type)
        total_monthly_spend += cost
        
        env = h.environment or "default"
        spend_by_env[env] = spend_by_env.get(env, 0.0) + cost

        # Fetch recent metrics for host
        metrics = list(
            db.scalars(
                select(Metric)
                .where(Metric.host_id == h.id)
                .order_by(desc(Metric.timestamp))
                .limit(60)
            ).all()
        )

        avg_cpu = sum(m.cpu_percent for m in metrics) / len(metrics) if metrics else 45.0
        peak_cpu = max((m.cpu_percent for m in metrics), default=avg_cpu)
        avg_mem = sum(m.memory_percent for m in metrics) / len(metrics) if metrics else 50.0
        peak_mem = max((m.memory_percent for m in metrics), default=avg_mem)

        # Check for rightsizing
        rec_data = _calculator.evaluate_rightsizing(
            hostname=h.hostname,
            instance_type=h.instance_type,
            avg_cpu=avg_cpu,
            peak_cpu=peak_cpu,
            avg_memory=avg_mem,
            peak_memory=peak_mem,
        )

        savings = 0.0
        if rec_data:
            savings = rec_data["estimated_monthly_savings_usd"]
            total_potential_savings += savings
            if rec_data["recommendation_type"] == "IDLE_TERMINATION":
                idle_count += 1
            else:
                underutilized_count += 1

            # Sync to DB if not already present
            existing_rec = db.scalars(
                select(CostRecommendation)
                .where(CostRecommendation.host_id == h.id, CostRecommendation.status == "open")
            ).first()
            if not existing_rec:
                rec_obj = CostRecommendation(
                    host_id=h.id,
                    recommendation_type=rec_data["recommendation_type"],
                    current_instance_type=rec_data["current_instance_type"],
                    suggested_instance_type=rec_data["suggested_instance_type"],
                    current_monthly_spend_usd=rec_data["current_monthly_spend_usd"],
                    estimated_monthly_spend_usd=rec_data["estimated_monthly_spend_usd"],
                    estimated_monthly_savings_usd=rec_data["estimated_monthly_savings_usd"],
                    rationale=rec_data["rationale"],
                    status="open",
                    confidence_score=rec_data["confidence_score"],
                )
                db.add(rec_obj)
                db.commit()

        resource_costs.append(
            CostByResource(
                host_id=h.id,
                hostname=h.hostname,
                environment=env,
                instance_type=h.instance_type or "t3.medium",
                monthly_spend_usd=cost,
                utilization_score=round(avg_cpu, 1),
                optimization_potential=round(savings, 2),
            )
        )

    # Fetch all active recommendations from DB
    recs = list(
        db.scalars(
            select(CostRecommendation)
            .where(CostRecommendation.status == "open")
            .order_by(desc(CostRecommendation.estimated_monthly_savings_usd))
        ).all()
    )

    rec_reads = [
        CostRecommendationRead(
            id=r.id,
            host_id=r.host_id,
            hostname=r.host.hostname if r.host else None,
            recommendation_type=r.recommendation_type,
            current_instance_type=r.current_instance_type,
            suggested_instance_type=r.suggested_instance_type,
            current_monthly_spend_usd=r.current_monthly_spend_usd,
            estimated_monthly_spend_usd=r.estimated_monthly_spend_usd,
            estimated_monthly_savings_usd=r.estimated_monthly_savings_usd,
            rationale=r.rationale,
            status=r.status,
            confidence_score=r.confidence_score,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in recs
    ]

    resource_costs.sort(key=lambda x: x.monthly_spend_usd, reverse=True)

    return CostSummaryResponse(
        estimated_monthly_spend_usd=round(total_monthly_spend, 2),
        estimated_potential_savings_usd=round(total_potential_savings, 2),
        total_monitored_resources=len(hosts),
        idle_resources_count=idle_count,
        underutilized_resources_count=underutilized_count,
        currency="USD",
        billing_status="Estimated (Telemetry Driven)",
        spend_by_environment={k: round(v, 2) for k, v in spend_by_env.items()},
        top_cost_resources=resource_costs,
        active_recommendations=rec_reads,
    )


def update_recommendation_status(
    db: Session,
    recommendation_id: int,
    action: CostRecommendationAction,
) -> Optional[CostRecommendation]:
    """Updates the status of a cost recommendation (e.g. accepted, dismissed)."""
    rec = db.get(CostRecommendation, recommendation_id)
    if not rec:
        return None
    rec.status = action.status
    rec.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec
