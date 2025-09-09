"""Monitoring and observability for Azure FinOps MCP Server."""

import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and manages application metrics."""

    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of metric points to keep in history
        """
        self.metrics = defaultdict(lambda: deque(maxlen=max_history))
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.timers = defaultdict(list)
        self.start_time = time.time()

    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict] = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self.counters[key] += value
        self._record_metric("counter", name, self.counters[key], tags)

    def set_gauge(self, name: str, value: float, tags: Optional[Dict] = None):
        """Set a gauge metric value."""
        key = self._make_key(name, tags)
        self.gauges[key] = value
        self._record_metric("gauge", name, value, tags)

    def record_timer(self, name: str, duration: float, tags: Optional[Dict] = None):
        """Record a timer metric."""
        key = self._make_key(name, tags)
        self.timers[key].append(duration)
        self._record_metric("timer", name, duration, tags)

    def _make_key(self, name: str, tags: Optional[Dict] = None) -> str:
        """Create a unique key for a metric."""
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{name}[{tag_str}]"
        return name

    def _record_metric(self, metric_type: str, name: str, value: Any, tags: Optional[Dict] = None):
        """Record a metric point."""
        metric_point = {
            "timestamp": datetime.now().isoformat(),
            "type": metric_type,
            "name": name,
            "value": value,
            "tags": tags or {},
        }
        self.metrics[name].append(metric_point)

        # Log metrics at debug level
        logger.debug(f"Metric: {json.dumps(metric_point)}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected metrics."""
        uptime = time.time() - self.start_time

        summary = {"uptime_seconds": uptime, "counters": dict(self.counters), "gauges": dict(self.gauges), "timers": {}}

        # Calculate timer statistics
        for key, values in self.timers.items():
            if values:
                summary["timers"][key] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "p50": self._percentile(values, 50),
                    "p95": self._percentile(values, 95),
                    "p99": self._percentile(values, 99),
                }

        return summary

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]


# Global metrics collector instance
metrics = MetricsCollector()


def track_metrics(operation: str):
    """
    Decorator to track metrics for a function.

    Args:
        operation: Name of the operation being tracked
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                # Increment call counter
                metrics.increment_counter(f"{operation}.calls")

                # Execute function
                result = func(*args, **kwargs)

                # Record success
                metrics.increment_counter(f"{operation}.success")

                return result

            except Exception as e:
                # Record failure
                metrics.increment_counter(f"{operation}.failures")
                metrics.increment_counter(f"errors.{type(e).__name__}")
                raise

            finally:
                # Record duration
                duration = time.time() - start_time
                metrics.record_timer(f"{operation}.duration", duration)

        return wrapper

    return decorator


def track_metrics_async(operation: str):
    """
    Decorator to track metrics for async functions.

    Args:
        operation: Name of the operation being tracked
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                metrics.increment_counter(f"{operation}.calls")
                result = await func(*args, **kwargs)
                metrics.increment_counter(f"{operation}.success")
                return result

            except Exception as e:
                metrics.increment_counter(f"{operation}.failures")
                metrics.increment_counter(f"errors.{type(e).__name__}")
                raise

            finally:
                duration = time.time() - start_time
                metrics.record_timer(f"{operation}.duration", duration)

        return wrapper

    return decorator


class AlertManager:
    """Manages alerting based on metrics thresholds."""

    def __init__(self):
        """Initialize alert manager."""
        self.alerts = []
        self.thresholds = {}
        self.alert_callbacks = []

    def set_threshold(self, metric: str, threshold: float, comparison: str = "gt", window_seconds: int = 60):
        """
        Set an alert threshold for a metric.

        Args:
            metric: Metric name to monitor
            threshold: Threshold value
            comparison: Comparison operator ('gt', 'lt', 'eq', 'gte', 'lte')
            window_seconds: Time window for evaluation
        """
        self.thresholds[metric] = {
            "threshold": threshold,
            "comparison": comparison,
            "window_seconds": window_seconds,
            "last_check": time.time(),
        }

    def check_alerts(self, metrics_summary: Dict[str, Any]):
        """
        Check metrics against thresholds and trigger alerts.

        Args:
            metrics_summary: Current metrics summary
        """
        current_time = time.time()

        for metric_name, config in self.thresholds.items():
            # Get metric value
            value = self._get_metric_value(metrics_summary, metric_name)
            if value is None:
                continue

            # Check threshold
            if self._evaluate_threshold(value, config["threshold"], config["comparison"]):
                alert = {
                    "timestamp": datetime.now().isoformat(),
                    "metric": metric_name,
                    "value": value,
                    "threshold": config["threshold"],
                    "comparison": config["comparison"],
                    "severity": self._determine_severity(metric_name, value, config["threshold"]),
                }

                self.alerts.append(alert)
                self._trigger_alert(alert)

    def _get_metric_value(self, metrics_summary: Dict, metric_name: str) -> Optional[float]:
        """Extract metric value from summary."""
        # Handle different metric types
        if metric_name in metrics_summary.get("counters", {}):
            return metrics_summary["counters"][metric_name]
        elif metric_name in metrics_summary.get("gauges", {}):
            return metrics_summary["gauges"][metric_name]
        elif "." in metric_name:
            # Handle nested metrics like "timer.mean"
            parts = metric_name.split(".")
            if parts[0] in metrics_summary.get("timers", {}):
                timer_data = metrics_summary["timers"][parts[0]]
                if len(parts) > 1 and parts[1] in timer_data:
                    return timer_data[parts[1]]
        return None

    def _evaluate_threshold(self, value: float, threshold: float, comparison: str) -> bool:
        """Evaluate if value crosses threshold."""
        comparisons = {
            "gt": value > threshold,
            "lt": value < threshold,
            "eq": value == threshold,
            "gte": value >= threshold,
            "lte": value <= threshold,
        }
        return comparisons.get(comparison, False)

    def _determine_severity(self, metric: str, value: float, threshold: float) -> str:
        """Determine alert severity."""
        # Calculate how far value is from threshold
        if "error" in metric.lower() or "failure" in metric.lower():
            return "CRITICAL"
        elif "warning" in metric.lower():
            return "WARNING"
        else:
            diff_percent = abs((value - threshold) / threshold * 100) if threshold != 0 else 0
            if diff_percent > 50:
                return "CRITICAL"
            elif diff_percent > 25:
                return "HIGH"
            elif diff_percent > 10:
                return "MEDIUM"
            else:
                return "LOW"

    def _trigger_alert(self, alert: Dict[str, Any]):
        """Trigger alert callbacks."""
        logger.warning(f"ALERT: {json.dumps(alert)}")

        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {str(e)}")

    def register_callback(self, callback: Callable):
        """Register an alert callback function."""
        self.alert_callbacks.append(callback)

    def get_active_alerts(self, since: Optional[datetime] = None) -> List[Dict]:
        """Get active alerts since a given time."""
        if since:
            since_str = since.isoformat()
            return [a for a in self.alerts if a["timestamp"] >= since_str]
        return self.alerts


# Global alert manager instance
alert_manager = AlertManager()

# Set default alert thresholds
alert_manager.set_threshold("errors.total", 10, "gt", window_seconds=300)
alert_manager.set_threshold("api.failures", 5, "gt", window_seconds=60)
alert_manager.set_threshold("get_cost.duration.p95", 10.0, "gt", window_seconds=300)
alert_manager.set_threshold("memory_usage_mb", 500, "gt", window_seconds=60)


class HealthCheck:
    """Health check system for operational monitoring."""

    def __init__(self):
        """Initialize health check system."""
        self.checks = {}
        self.last_check_time = {}
        self.check_results = {}

    def register_check(self, name: str, check_func: Callable, interval_seconds: int = 60):
        """
        Register a health check.

        Args:
            name: Name of the health check
            check_func: Function that returns (bool, message)
            interval_seconds: How often to run the check
        """
        self.checks[name] = {"func": check_func, "interval": interval_seconds}
        self.last_check_time[name] = 0

    def run_checks(self) -> Dict[str, Any]:
        """Run all due health checks."""
        current_time = time.time()
        results = {}

        for name, config in self.checks.items():
            # Check if it's time to run this check
            if current_time - self.last_check_time[name] >= config["interval"]:
                try:
                    success, message = config["func"]()
                    results[name] = {
                        "status": "healthy" if success else "unhealthy",
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.check_results[name] = results[name]
                    self.last_check_time[name] = current_time

                    # Track health check metrics
                    metrics.set_gauge(f"health.{name}", 1 if success else 0)

                except Exception as e:
                    results[name] = {"status": "error", "message": str(e), "timestamp": datetime.now().isoformat()}
                    metrics.set_gauge(f"health.{name}", 0)

        return results

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        unhealthy = [name for name, result in self.check_results.items() if result.get("status") != "healthy"]

        return {
            "status": "healthy" if not unhealthy else "unhealthy",
            "healthy_checks": len(self.check_results) - len(unhealthy),
            "unhealthy_checks": len(unhealthy),
            "total_checks": len(self.check_results),
            "details": self.check_results,
        }


# Global health check instance
health_check = HealthCheck()


# Register default health checks
def check_azure_connection():
    """Check Azure connection health."""
    try:
        from .helpers.subscription_manager import get_azure_subscriptions

        subs = get_azure_subscriptions()
        if subs:
            return True, f"Connected to {len(subs)} subscription(s)"
        return False, "No Azure subscriptions available"
    except Exception as e:
        return False, f"Azure connection failed: {str(e)}"


def check_memory_usage():
    """Check memory usage."""
    import psutil

    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    metrics.set_gauge("memory_usage_mb", memory_mb)

    if memory_mb > 500:
        return False, f"High memory usage: {memory_mb:.1f}MB"
    return True, f"Memory usage: {memory_mb:.1f}MB"


health_check.register_check("azure_connection", check_azure_connection, 300)
health_check.register_check("memory_usage", check_memory_usage, 60)
