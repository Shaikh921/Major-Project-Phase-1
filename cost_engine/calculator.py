"""
Cloud Cost Optimization & Rightsizing Engine (Module 3).

Calculates estimated spend based on cloud instance catalogs and derives
actionable rightsizing recommendations from observed peak and average utilization.
"""

from typing import Dict, List, Any, Optional, Tuple


# Standard reference pricing catalog (Hourly rates USD)
STANDARD_PRICING_CATALOG: Dict[str, Dict[str, Any]] = {
    "t3.nano": {"vcpus": 2, "memory_gb": 0.5, "hourly_usd": 0.0052, "monthly_usd": 3.75},
    "t3.micro": {"vcpus": 2, "memory_gb": 1.0, "hourly_usd": 0.0104, "monthly_usd": 7.49},
    "t3.small": {"vcpus": 2, "memory_gb": 2.0, "hourly_usd": 0.0208, "monthly_usd": 14.98},
    "t3.medium": {"vcpus": 2, "memory_gb": 4.0, "hourly_usd": 0.0416, "monthly_usd": 29.95},
    "t3.large": {"vcpus": 2, "memory_gb": 8.0, "hourly_usd": 0.0832, "monthly_usd": 59.90},
    "t3.xlarge": {"vcpus": 4, "memory_gb": 16.0, "hourly_usd": 0.1664, "monthly_usd": 119.81},
    "t3.2xlarge": {"vcpus": 8, "memory_gb": 32.0, "hourly_usd": 0.3328, "monthly_usd": 239.62},
    "c5.large": {"vcpus": 2, "memory_gb": 4.0, "hourly_usd": 0.0850, "monthly_usd": 61.20},
    "c5.xlarge": {"vcpus": 4, "memory_gb": 8.0, "hourly_usd": 0.1700, "monthly_usd": 122.40},
    "c5.2xlarge": {"vcpus": 8, "memory_gb": 16.0, "hourly_usd": 0.3400, "monthly_usd": 244.80},
    "c5.4xlarge": {"vcpus": 16, "memory_gb": 32.0, "hourly_usd": 0.6800, "monthly_usd": 489.60},
    "m5.large": {"vcpus": 2, "memory_gb": 8.0, "hourly_usd": 0.0960, "monthly_usd": 69.12},
    "m5.xlarge": {"vcpus": 4, "memory_gb": 16.0, "hourly_usd": 0.1920, "monthly_usd": 138.24},
    "m5.2xlarge": {"vcpus": 8, "memory_gb": 32.0, "hourly_usd": 0.3840, "monthly_usd": 276.48},
    "r5.large": {"vcpus": 2, "memory_gb": 16.0, "hourly_usd": 0.1260, "monthly_usd": 90.72},
    "r5.xlarge": {"vcpus": 4, "memory_gb": 32.0, "hourly_usd": 0.2520, "monthly_usd": 181.44},
    "Standard_D2s_v3": {"vcpus": 2, "memory_gb": 8.0, "hourly_usd": 0.0960, "monthly_usd": 69.12},
    "Standard_D4s_v3": {"vcpus": 4, "memory_gb": 16.0, "hourly_usd": 0.1920, "monthly_usd": 138.24},
    "e2-standard-2": {"vcpus": 2, "memory_gb": 8.0, "hourly_usd": 0.0670, "monthly_usd": 48.24},
    "e2-standard-4": {"vcpus": 4, "memory_gb": 16.0, "hourly_usd": 0.1340, "monthly_usd": 96.48},
}


class CostCalculator:
    """
    Evaluates resource consumption and generates rightsizing and spend recommendations.
    """

    def get_instance_monthly_cost(self, instance_type: Optional[str]) -> float:
        """Looks up instance type monthly cost in catalog with fallback."""
        if instance_type and instance_type in STANDARD_PRICING_CATALOG:
            return STANDARD_PRICING_CATALOG[instance_type]["monthly_usd"]
        return 45.00  # Default baseline monthly estimate for unmapped/default instances

    def evaluate_rightsizing(
        self,
        hostname: str,
        instance_type: Optional[str],
        avg_cpu: float,
        peak_cpu: float,
        avg_memory: float,
        peak_memory: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Determines if a host is severely underutilized (idle) or over-provisioned.
        """
        itype = instance_type or "t3.medium"
        current_cost = self.get_instance_monthly_cost(itype)

        # 1. Idle host detection (avg CPU < 5% and avg Mem < 25%)
        if avg_cpu < 5.0 and avg_memory < 25.0:
            return {
                "recommendation_type": "IDLE_TERMINATION",
                "current_instance_type": itype,
                "suggested_instance_type": None,
                "current_monthly_spend_usd": current_cost,
                "estimated_monthly_spend_usd": 0.0,
                "estimated_monthly_savings_usd": current_cost,
                "rationale": (
                    f"Host {hostname} exhibits average CPU of {avg_cpu:.1f}% and Memory of {avg_memory:.1f}% "
                    f"over historical window. Candidate for idle shutdown or container consolidation."
                ),
                "confidence_score": 0.95,
            }

        # 2. Over-provisioned host rightsizing (e.g. c5.2xlarge -> c5.large)
        if "2xlarge" in itype and peak_cpu < 40.0 and peak_memory < 45.0:
            downsized_type = itype.replace("2xlarge", "large")
            new_cost = self.get_instance_monthly_cost(downsized_type)
            savings = max(0.0, current_cost - new_cost)
            return {
                "recommendation_type": "RIGHTSIZE_DOWN",
                "current_instance_type": itype,
                "suggested_instance_type": downsized_type,
                "current_monthly_spend_usd": current_cost,
                "estimated_monthly_spend_usd": new_cost,
                "estimated_monthly_savings_usd": savings,
                "rationale": (
                    f"Observed peak CPU is {peak_cpu:.1f}% on {itype}. Downsizing to {downsized_type} "
                    f"maintains adequate headroom while reducing monthly cloud spend."
                ),
                "confidence_score": 0.88,
            }
        
        if "xlarge" in itype and peak_cpu < 30.0 and peak_memory < 40.0:
            downsized_type = itype.replace("xlarge", "medium") if "t3" in itype else itype.replace("xlarge", "large")
            new_cost = self.get_instance_monthly_cost(downsized_type)
            savings = max(0.0, current_cost - new_cost)
            return {
                "recommendation_type": "RIGHTSIZE_DOWN",
                "current_instance_type": itype,
                "suggested_instance_type": downsized_type,
                "current_monthly_spend_usd": current_cost,
                "estimated_monthly_spend_usd": new_cost,
                "estimated_monthly_savings_usd": savings,
                "rationale": (
                    f"Observed peak CPU is {peak_cpu:.1f}% on {itype}. Downsizing to {downsized_type} "
                    f"saves approximately ${savings:.2f}/month."
                ),
                "confidence_score": 0.85,
            }

        return None
