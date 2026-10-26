# SRE Runbook: Cloud Cost Anomalies & Idle Resource Rightsizing

**ID:** `RUNBOOK-COST-006`  
**Domain:** Cloud FinOps & Cost Optimization  
**Applies To:** AWS EC2, GCP Compute Engine, Azure VMs, Idle Staging Hosts  
**Severity:** Medium  

## 1. Symptom Profile
- Unexpected spike in daily or monthly projected infrastructure spend (> 20% over 30-day baseline).
- Cost recommendation engine flags instances with sustained low utilization (< 10% CPU and memory) over 7+ days.
- Orphaned cloud assets: Unattached EBS/persistent volumes, unassociated Elastic IPs, or idle load balancers.
- Staging and development environments running 24/7 over non-business hours and weekends.

## 2. Root Cause Classification
- **Over-Provisioned Instance SKU:** Workload running on larger instance size (e.g. `c5.4xlarge`) than required by actual CPU/RAM peaks.
- **Abandoned Test Bench / Proof-of-Concept:** Temporary benchmarking instances left running indefinitely after project completion.
- **Continuous Runaway Auto-Scaling:** Faulty scale-down policy preventing replica reduction after traffic peak passes.
- **Unattached Storage Volumes:** Storage volumes retained after instance termination without retention justification.

## 3. Immediate Diagnostic Commands
```bash
# Query active CloudOps Intel Cost Optimization recommendations
SELECT host_id, recommendation_type, current_cost_usd, recommended_cost_usd, estimated_monthly_savings_usd 
FROM cost_recommendations 
WHERE status = 'open' 
ORDER BY estimated_monthly_savings_usd DESC;

# Identify candidate instances with average CPU < 10% over last 7 days
SELECT host_id, AVG(cpu_percent) as avg_cpu 
FROM metrics 
WHERE timestamp >= datetime('now', '-7 days') 
GROUP BY host_id 
HAVING avg_cpu < 10.0;
```

## 4. Remediation Steps
1. **Downsize Over-Provisioned Compute:**
   - Review workload peak usage and resize instances (e.g., migrate from `t3.large` to `t3.medium`).
2. **Schedule Automated Off-Hours Shutdown:**
   - Configure cron/lambda schedules to stop development and staging instances outside business hours (08:00–18:00 Mon–Fri) to save ~65% monthly run rate.
3. **Purge Orphaned Storage Volumes:**
   - Snapshot and delete unattached volumes older than 14 days.
4. **Implement AWS/GCP Budget Alerts:**
   - Establish automated spending threshold alerts at 80%, 100%, and 120% of monthly budget forecast.
