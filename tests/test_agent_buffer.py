"""
Unit Tests for Monitoring Agent and Local Buffer.
"""

from unittest.mock import patch, MagicMock
from monitoring_agent.collector import SystemCollector
from monitoring_agent.buffer import MetricBuffer


def test_system_collector():
    """Tests that the SystemCollector returns correctly structured metric samples."""
    collector = SystemCollector()
    sample = collector.collect()

    assert "hostname" in sample
    assert "cpu_percent" in sample
    assert "memory_percent" in sample
    assert "disk_percent" in sample
    assert "network_sent_mb" in sample
    assert "network_received_mb" in sample
    assert isinstance(sample["cpu_percent"], float)
    assert 0.0 <= sample["cpu_percent"] <= 100.0


def test_metric_buffer_push_and_overflow():
    """Tests ring buffer insertion and max capacity limit."""
    buffer = MetricBuffer(ingest_url="http://mock-server/api/v1/metrics", max_size=3)

    buffer.push({"sample": 1})
    buffer.push({"sample": 2})
    buffer.push({"sample": 3})
    assert buffer.size() == 3

    # Adding a 4th item drops the oldest item (1)
    buffer.push({"sample": 4})
    assert buffer.size() == 3


@patch("requests.post")
def test_metric_buffer_flush_success(mock_post):
    """Tests successful flush and clearing of buffered items."""
    mock_post.return_value = MagicMock(status_code=201)

    buffer = MetricBuffer(ingest_url="http://mock-server/api/v1/metrics")
    buffer.push({"cpu_percent": 30.0})
    buffer.push({"cpu_percent": 35.0})
    assert buffer.size() == 2

    success = buffer.flush()
    assert success is True
    assert buffer.size() == 0
    assert buffer.get_backoff_delay() == 0.0


@patch("requests.post")
def test_metric_buffer_flush_failure_and_backoff(mock_post):
    """Tests that network failures preserve buffer and calculate exponential backoff."""
    mock_post.side_effect = Exception("Connection refused")

    buffer = MetricBuffer(ingest_url="http://mock-server/api/v1/metrics")
    buffer.push({"cpu_percent": 50.0})

    # First failure
    success = buffer.flush()
    assert success is False
    assert buffer.size() == 1
    assert buffer.get_backoff_delay() > 0.0
