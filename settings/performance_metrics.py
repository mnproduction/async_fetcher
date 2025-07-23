"""
Performance Metrics Tracking and Logging

This module provides comprehensive performance tracking for the async fetching service,
including fetch durations, job durations, and statistical analysis.

Features:
- Track individual fetch durations
- Track job completion times
- Periodic statistical logging
- Performance trend analysis
- Memory usage tracking
- Error rate monitoring
"""

import time
import statistics
from typing import List, Dict, Any, Optional
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .logger import get_logger


@dataclass
class PerformanceStats:
    """Performance statistics for a set of measurements."""
    count: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    median_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    total_duration_ms: float


class PerformanceMetrics:
    """
    Track performance metrics for the application.
    
    This class provides methods to record and analyze performance data
    for both individual fetches and overall jobs.
    """
    
    def __init__(self, max_samples: int = 1000):
        """
        Initialize performance metrics tracker.
        
        Args:
            max_samples: Maximum number of samples to keep in memory
        """
        self.logger = get_logger("settings.performance_metrics")
        self.max_samples = max_samples
        
        # Fetch performance tracking
        self.fetch_durations: deque = deque(maxlen=max_samples)
        self.fetch_errors: deque = deque(maxlen=max_samples)
        self.fetch_successes: deque = deque(maxlen=max_samples)
        
        # Job performance tracking
        self.job_durations: deque = deque(maxlen=max_samples)
        self.job_errors: deque = deque(maxlen=max_samples)
        self.job_successes: deque = deque(maxlen=max_samples)
        
        # Timing for periodic logging
        self.last_fetch_stats_time = time.time()
        self.last_job_stats_time = time.time()
        self.stats_interval = 60  # Log stats every 60 seconds
        
        # Performance thresholds for alerts
        self.slow_fetch_threshold_ms = 10000  # 10 seconds
        self.slow_job_threshold_ms = 300000   # 5 minutes
        
        self.logger.info(
            "Performance metrics initialized",
            max_samples=max_samples,
            stats_interval=self.stats_interval
        )
    
    def record_fetch_duration(self, duration_ms: float, success: bool = True, error_type: Optional[str] = None) -> None:
        """
        Record a fetch operation duration.
        
        Args:
            duration_ms: Duration of the fetch operation in milliseconds
            success: Whether the fetch was successful
            error_type: Type of error if the fetch failed
        """
        self.fetch_durations.append(duration_ms)
        
        if success:
            self.fetch_successes.append(duration_ms)
        else:
            self.fetch_errors.append(duration_ms)
        
        # Log slow fetches
        if duration_ms > self.slow_fetch_threshold_ms:
            self.logger.warning(
                "Slow fetch detected",
                duration_ms=round(duration_ms, 2),
                success=success,
                error_type=error_type,
                threshold_ms=self.slow_fetch_threshold_ms
            )
        
        # Log statistics periodically
        current_time = time.time()
        if current_time - self.last_fetch_stats_time >= self.stats_interval:
            self._log_fetch_stats()
            self.last_fetch_stats_time = current_time
    
    def record_job_duration(self, duration_ms: float, success: bool = True, url_count: int = 0) -> None:
        """
        Record a job completion duration.
        
        Args:
            duration_ms: Duration of the job in milliseconds
            success: Whether the job completed successfully
            url_count: Number of URLs processed in the job
        """
        self.job_durations.append(duration_ms)
        
        if success:
            self.job_successes.append(duration_ms)
        else:
            self.job_errors.append(duration_ms)
        
        # Log slow jobs
        if duration_ms > self.slow_job_threshold_ms:
            self.logger.warning(
                "Slow job detected",
                duration_ms=round(duration_ms, 2),
                success=success,
                url_count=url_count,
                threshold_ms=self.slow_job_threshold_ms
            )
        
        # Log job statistics
        self._log_job_stats()
    
    def get_fetch_stats(self) -> Optional[PerformanceStats]:
        """Get current fetch performance statistics."""
        if not self.fetch_durations:
            return None
        
        durations = list(self.fetch_durations)
        return self._calculate_stats(durations)
    
    def get_job_stats(self) -> Optional[PerformanceStats]:
        """Get current job performance statistics."""
        if not self.job_durations:
            return None
        
        durations = list(self.job_durations)
        return self._calculate_stats(durations)
    
    def get_error_rate(self) -> Dict[str, float]:
        """Get current error rates for fetches and jobs."""
        fetch_error_rate = 0.0
        job_error_rate = 0.0
        
        if self.fetch_durations:
            fetch_error_rate = len(self.fetch_errors) / len(self.fetch_durations) * 100
        
        if self.job_durations:
            job_error_rate = len(self.job_errors) / len(self.job_durations) * 100
        
        return {
            "fetch_error_rate_percent": round(fetch_error_rate, 2),
            "job_error_rate_percent": round(job_error_rate, 2)
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a comprehensive performance summary."""
        fetch_stats = self.get_fetch_stats()
        job_stats = self.get_job_stats()
        error_rates = self.get_error_rate()
        
        summary = {
            "fetch_stats": fetch_stats.__dict__ if fetch_stats else None,
            "job_stats": job_stats.__dict__ if job_stats else None,
            "error_rates": error_rates,
            "total_fetches": len(self.fetch_durations),
            "total_jobs": len(self.job_durations),
            "sample_count": len(self.fetch_durations)
        }
        
        return summary
    
    def _calculate_stats(self, durations: List[float]) -> PerformanceStats:
        """Calculate performance statistics from a list of durations."""
        if not durations:
            return None
        
        sorted_durations = sorted(durations)
        count = len(durations)
        total = sum(durations)
        avg = total / count
        min_val = min(durations)
        max_val = max(durations)
        median = statistics.median(durations)
        
        # Calculate percentiles
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        p95 = sorted_durations[p95_idx] if p95_idx < count else max_val
        p99 = sorted_durations[p99_idx] if p99_idx < count else max_val
        
        return PerformanceStats(
            count=count,
            avg_duration_ms=round(avg, 2),
            min_duration_ms=round(min_val, 2),
            max_duration_ms=round(max_val, 2),
            median_duration_ms=round(median, 2),
            p95_duration_ms=round(p95, 2),
            p99_duration_ms=round(p99, 2),
            total_duration_ms=round(total, 2)
        )
    
    def _log_fetch_stats(self) -> None:
        """Log fetch performance statistics."""
        stats = self.get_fetch_stats()
        if not stats:
            return
        
        error_rates = self.get_error_rate()
        
        self.logger.info(
            "Fetch performance metrics",
            avg_duration_ms=stats.avg_duration_ms,
            max_duration_ms=stats.max_duration_ms,
            min_duration_ms=stats.min_duration_ms,
            median_duration_ms=stats.median_duration_ms,
            p95_duration_ms=stats.p95_duration_ms,
            p99_duration_ms=stats.p99_duration_ms,
            sample_size=stats.count,
            error_rate_percent=error_rates["fetch_error_rate_percent"]
        )
    
    def _log_job_stats(self) -> None:
        """Log job performance statistics."""
        stats = self.get_job_stats()
        if not stats:
            return
        
        error_rates = self.get_error_rate()
        
        self.logger.info(
            "Job performance metrics",
            avg_duration_ms=stats.avg_duration_ms,
            max_duration_ms=stats.max_duration_ms,
            min_duration_ms=stats.min_duration_ms,
            median_duration_ms=stats.median_duration_ms,
            p95_duration_ms=stats.p95_duration_ms,
            p99_duration_ms=stats.p99_duration_ms,
            sample_size=stats.count,
            error_rate_percent=error_rates["job_error_rate_percent"]
        )
    
    def reset_stats(self) -> None:
        """Reset all performance statistics."""
        self.fetch_durations.clear()
        self.fetch_errors.clear()
        self.fetch_successes.clear()
        self.job_durations.clear()
        self.job_errors.clear()
        self.job_successes.clear()
        
        self.logger.info("Performance statistics reset")


# Create a singleton instance
performance_metrics = PerformanceMetrics()


def record_fetch_duration(duration_ms: float, success: bool = True, error_type: Optional[str] = None) -> None:
    """Record a fetch operation duration."""
    performance_metrics.record_fetch_duration(duration_ms, success, error_type)


def record_job_duration(duration_ms: float, success: bool = True, url_count: int = 0) -> None:
    """Record a job completion duration."""
    performance_metrics.record_job_duration(duration_ms, success, url_count)


def get_performance_summary() -> Dict[str, Any]:
    """Get a comprehensive performance summary."""
    return performance_metrics.get_performance_summary()


def get_error_rate() -> Dict[str, float]:
    """Get current error rates."""
    return performance_metrics.get_error_rate()


def reset_stats() -> None:
    """Reset all performance statistics."""
    performance_metrics.reset_stats()


# Export main interface
__all__ = [
    'PerformanceMetrics',
    'PerformanceStats',
    'record_fetch_duration',
    'record_job_duration',
    'get_performance_summary',
    'get_error_rate',
    'reset_stats',
    'performance_metrics'
] 