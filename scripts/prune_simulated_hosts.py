"""
Prune Redundant Test/Simulated Hosts for Production-Ready Dashboard.
Preserves representative simulated production/staging nodes and real lab/workstation agents.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database.session import SessionLocal
from backend.app.models.host import Host
from backend.app.models.metric import Metric
from backend.app.models.alert import Alert, AlertFeedback
from backend.app.models.security import SecurityEvent
from backend.app.models.cost import CostRecommendation
from RAG_System.pipeline import RAGPipeline

def prune_hosts():
    db = SessionLocal()
    try:
        # Hosts to prune (redundant or inactive test artifacts)
        prune_hostnames = [
            "dev-sandbox-01",
            "VM",
            "prod-web-healthy-01",
            "prod-db-cluster-node-99",
            "prod-db-e2e-node-corr",
            "prod-api-01",
            "prod-web-02",
        ]

        hosts_to_delete = db.query(Host).filter(Host.hostname.in_(prune_hostnames)).all()
        host_ids = [h.id for h in hosts_to_delete]
        print(f"Found {len(hosts_to_delete)} hosts to prune: {[h.hostname for h in hosts_to_delete]}")

        if host_ids:
            # 1. Delete associated alerts and feedback
            alert_ids = [a.id for a in db.query(Alert).filter(Alert.host_id.in_(host_ids)).all()]
            if alert_ids:
                db.query(AlertFeedback).filter(AlertFeedback.alert_id.in_(alert_ids)).delete(synchronize_session=False)
                deleted_alerts = db.query(Alert).filter(Alert.host_id.in_(host_ids)).delete(synchronize_session=False)
                print(f"Deleted {deleted_alerts} alerts for pruned hosts.")

            # 2. Delete associated metrics
            deleted_metrics = db.query(Metric).filter(Metric.host_id.in_(host_ids)).delete(synchronize_session=False)
            print(f"Deleted {deleted_metrics} metrics for pruned hosts.")

            # 3. Delete associated security events
            deleted_sec = db.query(SecurityEvent).filter(SecurityEvent.host_id.in_(host_ids)).delete(synchronize_session=False)
            print(f"Deleted {deleted_sec} security events for pruned hosts.")

            # 4. Delete associated cost recommendations
            deleted_cost = db.query(CostRecommendation).filter(CostRecommendation.host_id.in_(host_ids)).delete(synchronize_session=False)
            print(f"Deleted {deleted_cost} cost recommendations for pruned hosts.")

            # 5. Delete hosts
            for h in hosts_to_delete:
                db.delete(h)
            db.commit()
            print("Successfully deleted pruned hosts and committed transaction.")

        remaining = db.query(Host).all()
        print("\n--- Remaining Active Dashboard Fleet ---")
        for h in remaining:
            print(f"ID: {h.id} | {h.hostname:<20} | Env: {h.environment:<12} | Source: {h.source_type}")

        # Re-index RAG vector store to ensure clean embeddings
        print("\nRe-indexing RAG knowledge base & clearing stale telemetry vectors...")
        pipeline = RAGPipeline.get_instance()
        pipeline.store.chunks = []
        pipeline.store.chunk_ids = []
        pipeline.store.embeddings_matrix = None
        pipeline.index_runbooks()
        print(f"RAG vector store re-indexed cleanly with {pipeline.store.count()} runbook chunks.")

    finally:
        db.close()

if __name__ == "__main__":
    prune_hosts()
