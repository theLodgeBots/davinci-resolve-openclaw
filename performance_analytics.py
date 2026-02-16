#!/usr/bin/env python3
"""
Performance Analytics System for DaVinci Resolve OpenClaw
Enterprise-grade metrics, monitoring, and reporting system

Features:
- Detailed performance metrics collection and analysis
- Real-time system monitoring and alerting
- Comprehensive reporting and dashboards
- Resource utilization tracking
- SLA monitoring and compliance reporting
- Predictive performance modeling
"""

import json
import os
import time
import psutil
import GPUtil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import statistics
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System resource metrics snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    gpu_usage: List[float]  # Usage per GPU
    gpu_memory: List[float]  # Memory usage per GPU
    network_sent_mb: float
    network_recv_mb: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class ProcessingMetrics:
    """Processing workflow performance metrics"""
    project_id: str
    client_id: str
    start_time: datetime
    end_time: datetime
    total_duration: float
    video_count: int
    total_video_size_mb: float
    processing_stages: Dict[str, float]  # stage -> duration in seconds
    quality_score: float
    success: bool
    error_message: Optional[str]
    resource_peak: Dict[str, float]  # peak resource usage during processing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data

class PerformanceAnalytics:
    def __init__(self, db_path: str = "performance_analytics.db"):
        """Initialize performance analytics system"""
        self.db_path = db_path
        self.analytics_dir = Path("performance_analytics")
        self.analytics_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # System monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        self.monitoring_interval = 30  # seconds
        self.system_metrics_buffer = deque(maxlen=2880)  # 24 hours at 30s intervals
        
        # Performance thresholds
        self.performance_thresholds = {
            'cpu_warning': 80.0,
            'memory_warning': 85.0,
            'disk_warning': 90.0,
            'gpu_warning': 90.0,
            'processing_time_warning': 600.0,  # 10 minutes
            'quality_score_minimum': 0.7
        }
        
        # SLA targets
        self.sla_targets = {
            'processing_time_max': 900,  # 15 minutes
            'quality_score_min': 0.8,
            'success_rate_min': 0.95,
            'availability_target': 0.99
        }
        
        logger.info("Performance Analytics System initialized")
    
    def _init_database(self):
        """Initialize SQLite database for metrics storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # System metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        memory_used_gb REAL,
                        memory_total_gb REAL,
                        disk_usage_percent REAL,
                        disk_free_gb REAL,
                        gpu_usage TEXT,  -- JSON array
                        gpu_memory TEXT,  -- JSON array
                        network_sent_mb REAL,
                        network_recv_mb REAL
                    )
                ''')
                
                # Processing metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processing_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        client_id TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        total_duration REAL,
                        video_count INTEGER,
                        total_video_size_mb REAL,
                        processing_stages TEXT,  -- JSON
                        quality_score REAL,
                        success BOOLEAN,
                        error_message TEXT,
                        resource_peak TEXT  -- JSON
                    )
                ''')
                
                # Performance alerts table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS performance_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at TEXT
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
        
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def start_monitoring(self):
        """Start continuous system monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                metrics = self._collect_system_metrics()
                self._store_system_metrics(metrics)
                self._check_performance_thresholds(metrics)
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Brief pause on error
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network
            network = psutil.net_io_counters()
            
            # GPU (if available)
            gpu_usage = []
            gpu_memory = []
            try:
                gpus = GPUtil.getGPUs()
                gpu_usage = [gpu.load * 100 for gpu in gpus]
                gpu_memory = [gpu.memoryUtil * 100 for gpu in gpus]
            except Exception:
                pass  # GPU monitoring not available
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=memory.used / (1024**3),
                memory_total_gb=memory.total / (1024**3),
                disk_usage_percent=disk.percent,
                disk_free_gb=disk.free / (1024**3),
                gpu_usage=gpu_usage,
                gpu_memory=gpu_memory,
                network_sent_mb=network.bytes_sent / (1024**2),
                network_recv_mb=network.bytes_recv / (1024**2)
            )
        
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    def _store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics in database"""
        if not metrics:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_metrics 
                    (timestamp, cpu_percent, memory_percent, memory_used_gb, memory_total_gb,
                     disk_usage_percent, disk_free_gb, gpu_usage, gpu_memory, 
                     network_sent_mb, network_recv_mb)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.timestamp.isoformat(),
                    metrics.cpu_percent,
                    metrics.memory_percent,
                    metrics.memory_used_gb,
                    metrics.memory_total_gb,
                    metrics.disk_usage_percent,
                    metrics.disk_free_gb,
                    json.dumps(metrics.gpu_usage),
                    json.dumps(metrics.gpu_memory),
                    metrics.network_sent_mb,
                    metrics.network_recv_mb
                ))
                conn.commit()
        
        except Exception as e:
            logger.error(f"Error storing system metrics: {e}")
    
    def _check_performance_thresholds(self, metrics: SystemMetrics):
        """Check metrics against performance thresholds and generate alerts"""
        if not metrics:
            return
        
        alerts = []
        
        # CPU threshold
        if metrics.cpu_percent > self.performance_thresholds['cpu_warning']:
            alerts.append({
                'type': 'cpu_high',
                'severity': 'warning',
                'message': f'High CPU usage: {metrics.cpu_percent:.1f}%'
            })
        
        # Memory threshold
        if metrics.memory_percent > self.performance_thresholds['memory_warning']:
            alerts.append({
                'type': 'memory_high',
                'severity': 'warning',
                'message': f'High memory usage: {metrics.memory_percent:.1f}% ({metrics.memory_used_gb:.1f}GB)'
            })
        
        # Disk threshold
        if metrics.disk_usage_percent > self.performance_thresholds['disk_warning']:
            alerts.append({
                'type': 'disk_high',
                'severity': 'warning',
                'message': f'High disk usage: {metrics.disk_usage_percent:.1f}% (Free: {metrics.disk_free_gb:.1f}GB)'
            })
        
        # GPU thresholds
        for i, usage in enumerate(metrics.gpu_usage):
            if usage > self.performance_thresholds['gpu_warning']:
                alerts.append({
                    'type': 'gpu_high',
                    'severity': 'warning',
                    'message': f'High GPU {i} usage: {usage:.1f}%'
                })
        
        # Store alerts
        for alert in alerts:
            self._store_alert(alert)
    
    def _store_alert(self, alert: Dict[str, str]):
        """Store performance alert in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO performance_alerts (timestamp, alert_type, severity, message)
                    VALUES (?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    alert['type'],
                    alert['severity'],
                    alert['message']
                ))
                conn.commit()
                logger.warning(f"Performance alert: {alert['message']}")
        
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    def record_processing_metrics(self, metrics: ProcessingMetrics):
        """Record processing workflow metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO processing_metrics 
                    (project_id, client_id, start_time, end_time, total_duration, 
                     video_count, total_video_size_mb, processing_stages, quality_score, 
                     success, error_message, resource_peak)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.project_id,
                    metrics.client_id,
                    metrics.start_time.isoformat(),
                    metrics.end_time.isoformat(),
                    metrics.total_duration,
                    metrics.video_count,
                    metrics.total_video_size_mb,
                    json.dumps(metrics.processing_stages),
                    metrics.quality_score,
                    metrics.success,
                    metrics.error_message,
                    json.dumps(metrics.resource_peak)
                ))
                conn.commit()
                
            logger.info(f"Processing metrics recorded for project {metrics.project_id}")
            
            # Check SLA compliance
            self._check_sla_compliance(metrics)
        
        except Exception as e:
            logger.error(f"Error recording processing metrics: {e}")
    
    def _check_sla_compliance(self, metrics: ProcessingMetrics):
        """Check processing metrics against SLA targets"""
        violations = []
        
        if metrics.total_duration > self.sla_targets['processing_time_max']:
            violations.append(f"Processing time exceeded: {metrics.total_duration}s > {self.sla_targets['processing_time_max']}s")
        
        if metrics.quality_score < self.sla_targets['quality_score_min']:
            violations.append(f"Quality score below target: {metrics.quality_score} < {self.sla_targets['quality_score_min']}")
        
        if not metrics.success:
            violations.append("Processing failed")
        
        # Store SLA violations as critical alerts
        for violation in violations:
            self._store_alert({
                'type': 'sla_violation',
                'severity': 'critical',
                'message': f"SLA violation for {metrics.project_id}: {violation}"
            })
    
    def generate_performance_report(self, hours_back: int = 24) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        report = {
            "report_generated": end_time.isoformat(),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours_back
            },
            "system_performance": self._get_system_performance_summary(start_time, end_time),
            "processing_performance": self._get_processing_performance_summary(start_time, end_time),
            "sla_compliance": self._get_sla_compliance_summary(start_time, end_time),
            "alerts_summary": self._get_alerts_summary(start_time, end_time),
            "recommendations": []
        }
        
        # Add recommendations based on analysis
        report["recommendations"] = self._generate_recommendations(report)
        
        return report
    
    def _get_system_performance_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get system performance summary for time range"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT cpu_percent, memory_percent, disk_usage_percent, gpu_usage
                    FROM system_metrics
                    WHERE timestamp BETWEEN ? AND ?
                ''', (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return {"status": "no_data"}
                
                cpu_values = [row[0] for row in rows if row[0] is not None]
                memory_values = [row[1] for row in rows if row[1] is not None]
                disk_values = [row[2] for row in rows if row[2] is not None]
                
                return {
                    "status": "success",
                    "sample_count": len(rows),
                    "cpu": {
                        "average": statistics.mean(cpu_values) if cpu_values else 0,
                        "max": max(cpu_values) if cpu_values else 0,
                        "min": min(cpu_values) if cpu_values else 0
                    },
                    "memory": {
                        "average": statistics.mean(memory_values) if memory_values else 0,
                        "max": max(memory_values) if memory_values else 0,
                        "min": min(memory_values) if memory_values else 0
                    },
                    "disk": {
                        "average": statistics.mean(disk_values) if disk_values else 0,
                        "max": max(disk_values) if disk_values else 0,
                        "min": min(disk_values) if disk_values else 0
                    }
                }
        
        except Exception as e:
            logger.error(f"Error getting system performance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_processing_performance_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get processing performance summary for time range"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_duration, quality_score, success, video_count, total_video_size_mb
                    FROM processing_metrics
                    WHERE start_time BETWEEN ? AND ?
                ''', (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return {"status": "no_data"}
                
                durations = [row[0] for row in rows if row[0] is not None]
                quality_scores = [row[1] for row in rows if row[1] is not None]
                successes = [row[2] for row in rows if row[2] is not None]
                video_counts = [row[3] for row in rows if row[3] is not None]
                
                success_rate = sum(successes) / len(successes) if successes else 0
                
                return {
                    "status": "success",
                    "total_projects": len(rows),
                    "success_rate": success_rate,
                    "processing_time": {
                        "average": statistics.mean(durations) if durations else 0,
                        "max": max(durations) if durations else 0,
                        "min": min(durations) if durations else 0
                    },
                    "quality_score": {
                        "average": statistics.mean(quality_scores) if quality_scores else 0,
                        "max": max(quality_scores) if quality_scores else 0,
                        "min": min(quality_scores) if quality_scores else 0
                    },
                    "total_videos_processed": sum(video_counts) if video_counts else 0
                }
        
        except Exception as e:
            logger.error(f"Error getting processing performance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_sla_compliance_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get SLA compliance summary"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get processing metrics for SLA analysis
                cursor.execute('''
                    SELECT total_duration, quality_score, success
                    FROM processing_metrics
                    WHERE start_time BETWEEN ? AND ?
                ''', (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return {"status": "no_data"}
                
                total_projects = len(rows)
                time_compliant = sum(1 for row in rows if row[0] <= self.sla_targets['processing_time_max'])
                quality_compliant = sum(1 for row in rows if row[1] >= self.sla_targets['quality_score_min'])
                success_compliant = sum(1 for row in rows if row[2])
                
                return {
                    "status": "success",
                    "total_projects": total_projects,
                    "sla_targets": self.sla_targets,
                    "compliance_rates": {
                        "processing_time": time_compliant / total_projects if total_projects > 0 else 0,
                        "quality_score": quality_compliant / total_projects if total_projects > 0 else 0,
                        "success_rate": success_compliant / total_projects if total_projects > 0 else 0
                    }
                }
        
        except Exception as e:
            logger.error(f"Error getting SLA compliance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_alerts_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get alerts summary for time range"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT alert_type, severity, COUNT(*) as count
                    FROM performance_alerts
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY alert_type, severity
                ''', (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                
                alert_counts = defaultdict(lambda: defaultdict(int))
                total_alerts = 0
                
                for row in rows:
                    alert_type, severity, count = row
                    alert_counts[alert_type][severity] = count
                    total_alerts += count
                
                return {
                    "status": "success",
                    "total_alerts": total_alerts,
                    "alert_counts": dict(alert_counts)
                }
        
        except Exception as e:
            logger.error(f"Error getting alerts summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on performance analysis"""
        recommendations = []
        
        # System performance recommendations
        sys_perf = report.get("system_performance", {})
        if sys_perf.get("status") == "success":
            cpu_avg = sys_perf.get("cpu", {}).get("average", 0)
            memory_avg = sys_perf.get("memory", {}).get("average", 0)
            
            if cpu_avg > 70:
                recommendations.append("High CPU usage detected. Consider upgrading CPU or distributing workload.")
            
            if memory_avg > 80:
                recommendations.append("High memory usage detected. Consider adding more RAM or optimizing memory usage.")
        
        # Processing performance recommendations
        proc_perf = report.get("processing_performance", {})
        if proc_perf.get("status") == "success":
            success_rate = proc_perf.get("success_rate", 1.0)
            avg_quality = proc_perf.get("quality_score", {}).get("average", 1.0)
            
            if success_rate < 0.95:
                recommendations.append(f"Success rate ({success_rate:.1%}) below target. Investigate failure causes.")
            
            if avg_quality < 0.8:
                recommendations.append(f"Average quality score ({avg_quality:.2f}) below target. Review quality settings.")
        
        # SLA compliance recommendations
        sla_compliance = report.get("sla_compliance", {})
        if sla_compliance.get("status") == "success":
            compliance_rates = sla_compliance.get("compliance_rates", {})
            
            for metric, rate in compliance_rates.items():
                if rate < 0.95:
                    recommendations.append(f"SLA compliance for {metric} ({rate:.1%}) needs improvement.")
        
        return recommendations
    
    def export_performance_report(self, hours_back: int = 24, output_file: Optional[str] = None) -> bool:
        """Export performance report to file"""
        try:
            report = self.generate_performance_report(hours_back)
            
            if output_file is None:
                output_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            output_path = self.analytics_dir / output_file
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Performance report exported to {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting performance report: {e}")
            return False

def demo_performance_analytics():
    """Demo performance analytics system"""
    analytics = PerformanceAnalytics()
    
    print("🚀 Starting performance analytics demo...")
    
    # Start monitoring
    analytics.start_monitoring()
    print("📊 System monitoring started")
    
    # Simulate some processing metrics
    demo_metrics = ProcessingMetrics(
        project_id="demo_project_001",
        client_id="demo_client_001",
        start_time=datetime.now() - timedelta(minutes=10),
        end_time=datetime.now(),
        total_duration=300.0,  # 5 minutes
        video_count=5,
        total_video_size_mb=500.0,
        processing_stages={
            "ingest": 30.0,
            "transcribe": 120.0,
            "script": 60.0,
            "timeline": 90.0
        },
        quality_score=0.85,
        success=True,
        error_message=None,
        resource_peak={
            "cpu": 75.0,
            "memory": 60.0,
            "gpu": 80.0
        }
    )
    
    analytics.record_processing_metrics(demo_metrics)
    print("✅ Processing metrics recorded")
    
    # Wait a moment for monitoring
    time.sleep(5)
    
    # Generate report
    report = analytics.generate_performance_report(hours_back=1)
    print(f"📄 Performance report generated: {len(report)} sections")
    
    # Export report
    success = analytics.export_performance_report(hours_back=1)
    if success:
        print("💾 Report exported successfully")
    
    # Stop monitoring
    analytics.stop_monitoring()
    print("🛑 Monitoring stopped")
    
    return report

if __name__ == "__main__":
    demo_performance_analytics()