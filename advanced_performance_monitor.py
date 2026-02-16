#!/usr/bin/env python3
"""
📊 DaVinci Resolve OpenClaw - Advanced Performance Monitor
Real-time performance monitoring and optimization system
Created: February 15, 2026 - 7:35 AM EST (Cron Hour 14)
"""

import json
import time
import psutil
import sqlite3
import threading
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedPerformanceMonitor:
    """Real-time performance monitoring and optimization system"""
    
    def __init__(self, db_path: str = "performance_analytics_enhanced.db"):
        self.db_path = db_path
        self.monitoring_active = False
        self.monitoring_thread = None
        self.metrics_buffer = deque(maxlen=1000)  # Keep last 1000 metrics
        self.alert_thresholds = {
            'cpu_percent': 90.0,
            'memory_percent': 85.0,
            'disk_usage_percent': 90.0,
            'response_time_ms': 5000,
            'error_rate_percent': 5.0
        }
        self.performance_history = defaultdict(list)
        self.optimization_suggestions = []
        
        # Initialize database
        self.init_database()
        
    def init_database(self):
        """Initialize enhanced performance database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create enhanced metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    datetime_str TEXT,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_available_gb REAL,
                    disk_usage_percent REAL,
                    disk_free_gb REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    active_processes INTEGER,
                    gpu_usage_percent REAL,
                    temperature_celsius REAL,
                    power_consumption_watts REAL,
                    render_queue_size INTEGER,
                    active_timelines INTEGER,
                    api_response_time_ms REAL,
                    error_count INTEGER,
                    warning_count INTEGER,
                    optimization_score REAL
                )
            ''')
            
            # Create alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    datetime_str TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    threshold REAL,
                    message TEXT,
                    resolved BOOLEAN DEFAULT 0
                )
            ''')
            
            # Create optimization recommendations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    datetime_str TEXT,
                    category TEXT,
                    priority TEXT,
                    recommendation TEXT,
                    estimated_improvement_percent REAL,
                    implementation_difficulty TEXT,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Create workflow performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    datetime_str TEXT,
                    workflow_name TEXT,
                    stage TEXT,
                    duration_seconds REAL,
                    input_size_mb REAL,
                    output_size_mb REAL,
                    cpu_usage_percent REAL,
                    memory_usage_gb REAL,
                    success BOOLEAN,
                    error_message TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"📊 Performance database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system performance metrics"""
        try:
            # Basic system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            # Process information
            active_processes = len(psutil.pids())
            
            # Advanced metrics (with fallbacks)
            gpu_usage = self.get_gpu_usage()
            temperature = self.get_system_temperature()
            power_consumption = self.get_power_consumption()
            
            # Application-specific metrics
            render_queue_size = self.get_render_queue_size()
            active_timelines = self.get_active_timelines()
            api_response_time = self.measure_api_response_time()
            
            # Error tracking
            error_count, warning_count = self.get_error_counts()
            
            # Calculate optimization score
            optimization_score = self.calculate_optimization_score(
                cpu_percent, memory.percent, disk.percent
            )
            
            metrics = {
                'timestamp': time.time(),
                'datetime_str': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_usage_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3),
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'active_processes': active_processes,
                'gpu_usage_percent': gpu_usage,
                'temperature_celsius': temperature,
                'power_consumption_watts': power_consumption,
                'render_queue_size': render_queue_size,
                'active_timelines': active_timelines,
                'api_response_time_ms': api_response_time,
                'error_count': error_count,
                'warning_count': warning_count,
                'optimization_score': optimization_score
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {}

    def get_gpu_usage(self) -> float:
        """Get GPU usage percentage (with fallback)"""
        try:
            # Try nvidia-smi for NVIDIA GPUs
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0.0  # Fallback

    def get_system_temperature(self) -> float:
        """Get system temperature (with fallback)"""
        try:
            # Try to get CPU temperature on macOS
            if sys.platform == 'darwin':
                # macOS temperature reading would require additional tools
                pass
            # Try Linux thermal zones
            elif sys.platform.startswith('linux'):
                thermal_zones = Path('/sys/class/thermal')
                if thermal_zones.exists():
                    for zone in thermal_zones.glob('thermal_zone*/temp'):
                        temp = int(zone.read_text().strip()) / 1000
                        return temp
        except:
            pass
        return 0.0  # Fallback

    def get_power_consumption(self) -> float:
        """Get power consumption (with fallback)"""
        try:
            # This would require platform-specific implementations
            # For now, estimate based on CPU usage
            cpu_percent = psutil.cpu_percent()
            base_power = 50  # Base system power in watts
            cpu_power = (cpu_percent / 100) * 100  # Max 100W for CPU
            return base_power + cpu_power
        except:
            pass
        return 0.0  # Fallback

    def get_render_queue_size(self) -> int:
        """Get current render queue size"""
        try:
            # Check for render queue files or DaVinci Resolve status
            renders_dir = Path('renders')
            if renders_dir.exists():
                # Count .partial or .rendering files
                rendering_files = list(renders_dir.glob('*.partial')) + \
                                list(renders_dir.glob('*.rendering'))
                return len(rendering_files)
        except:
            pass
        return 0

    def get_active_timelines(self) -> int:
        """Get number of active timelines"""
        try:
            # This would connect to DaVinci Resolve API
            # For now, estimate based on project files
            return 1  # Placeholder
        except:
            pass
        return 0

    def measure_api_response_time(self) -> float:
        """Measure API response time"""
        try:
            start_time = time.time()
            # Simulate API call or health check
            # In real implementation, this would call actual API endpoints
            time.sleep(0.001)  # Simulate minimal response time
            return (time.time() - start_time) * 1000  # Convert to milliseconds
        except:
            pass
        return 0.0

    def get_error_counts(self) -> tuple:
        """Get error and warning counts from logs"""
        try:
            error_count = 0
            warning_count = 0
            
            # Check recent log files
            log_files = ['performance_monitor.log', 'health_check.log']
            cutoff_time = datetime.now() - timedelta(minutes=5)
            
            for log_file in log_files:
                if Path(log_file).exists():
                    with open(log_file, 'r') as f:
                        for line in f:
                            if 'ERROR' in line:
                                error_count += 1
                            elif 'WARNING' in line:
                                warning_count += 1
                                
            return error_count, warning_count
        except:
            pass
        return 0, 0

    def calculate_optimization_score(self, cpu: float, memory: float, disk: float) -> float:
        """Calculate overall system optimization score (0-100)"""
        try:
            # Weight different factors
            cpu_score = max(0, 100 - cpu)  # Lower CPU usage = higher score
            memory_score = max(0, 100 - memory)
            disk_score = max(0, 100 - disk)
            
            # Weighted average
            overall_score = (cpu_score * 0.4 + memory_score * 0.4 + disk_score * 0.2)
            return round(overall_score, 2)
        except:
            return 50.0  # Neutral score

    def store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO performance_metrics (
                    timestamp, datetime_str, cpu_percent, memory_percent,
                    memory_available_gb, disk_usage_percent, disk_free_gb,
                    network_bytes_sent, network_bytes_recv, active_processes,
                    gpu_usage_percent, temperature_celsius, power_consumption_watts,
                    render_queue_size, active_timelines, api_response_time_ms,
                    error_count, warning_count, optimization_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics['timestamp'], metrics['datetime_str'], 
                metrics['cpu_percent'], metrics['memory_percent'],
                metrics['memory_available_gb'], metrics['disk_usage_percent'],
                metrics['disk_free_gb'], metrics['network_bytes_sent'],
                metrics['network_bytes_recv'], metrics['active_processes'],
                metrics['gpu_usage_percent'], metrics['temperature_celsius'],
                metrics['power_consumption_watts'], metrics['render_queue_size'],
                metrics['active_timelines'], metrics['api_response_time_ms'],
                metrics['error_count'], metrics['warning_count'],
                metrics['optimization_score']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")

    def check_alert_conditions(self, metrics: Dict[str, Any]):
        """Check for alert conditions and store alerts"""
        try:
            alerts = []
            
            # Check each threshold
            if metrics['cpu_percent'] > self.alert_thresholds['cpu_percent']:
                alerts.append({
                    'type': 'performance',
                    'severity': 'high',
                    'metric': 'cpu_percent',
                    'value': metrics['cpu_percent'],
                    'threshold': self.alert_thresholds['cpu_percent'],
                    'message': f"High CPU usage: {metrics['cpu_percent']:.1f}%"
                })
                
            if metrics['memory_percent'] > self.alert_thresholds['memory_percent']:
                alerts.append({
                    'type': 'performance',
                    'severity': 'high',
                    'metric': 'memory_percent',
                    'value': metrics['memory_percent'],
                    'threshold': self.alert_thresholds['memory_percent'],
                    'message': f"High memory usage: {metrics['memory_percent']:.1f}%"
                })
                
            if metrics['disk_usage_percent'] > self.alert_thresholds['disk_usage_percent']:
                alerts.append({
                    'type': 'storage',
                    'severity': 'high',
                    'metric': 'disk_usage_percent',
                    'value': metrics['disk_usage_percent'],
                    'threshold': self.alert_thresholds['disk_usage_percent'],
                    'message': f"High disk usage: {metrics['disk_usage_percent']:.1f}%"
                })
                
            if metrics['api_response_time_ms'] > self.alert_thresholds['response_time_ms']:
                alerts.append({
                    'type': 'performance',
                    'severity': 'medium',
                    'metric': 'api_response_time_ms',
                    'value': metrics['api_response_time_ms'],
                    'threshold': self.alert_thresholds['response_time_ms'],
                    'message': f"Slow API response: {metrics['api_response_time_ms']:.1f}ms"
                })
            
            # Store alerts in database
            if alerts:
                self.store_alerts(alerts, metrics['timestamp'])
                
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to check alert conditions: {e}")
            return []

    def store_alerts(self, alerts: List[Dict], timestamp: float):
        """Store alerts in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for alert in alerts:
                cursor.execute('''
                    INSERT INTO performance_alerts (
                        timestamp, datetime_str, alert_type, severity,
                        metric_name, metric_value, threshold, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp, datetime.fromtimestamp(timestamp).isoformat(),
                    alert['type'], alert['severity'], alert['metric'],
                    alert['value'], alert['threshold'], alert['message']
                ))
                
            conn.commit()
            conn.close()
            
            # Log alerts
            for alert in alerts:
                logger.warning(f"🚨 ALERT: {alert['message']}")
                
        except Exception as e:
            logger.error(f"Failed to store alerts: {e}")

    def generate_optimization_recommendations(self, metrics: Dict[str, Any]):
        """Generate optimization recommendations based on current metrics"""
        try:
            recommendations = []
            
            # CPU optimization recommendations
            if metrics['cpu_percent'] > 80:
                recommendations.append({
                    'category': 'cpu',
                    'priority': 'high',
                    'recommendation': 'Consider reducing parallel processing workers or optimizing CPU-intensive operations',
                    'estimated_improvement': 15.0,
                    'difficulty': 'medium'
                })
                
            # Memory optimization recommendations
            if metrics['memory_percent'] > 75:
                recommendations.append({
                    'category': 'memory',
                    'priority': 'high',
                    'recommendation': 'Implement memory cleanup routines and optimize data structures',
                    'estimated_improvement': 20.0,
                    'difficulty': 'medium'
                })
                
            # Disk optimization recommendations
            if metrics['disk_usage_percent'] > 80:
                recommendations.append({
                    'category': 'storage',
                    'priority': 'medium',
                    'recommendation': 'Clean up temporary files and old render outputs',
                    'estimated_improvement': 10.0,
                    'difficulty': 'easy'
                })
                
            # API performance recommendations
            if metrics['api_response_time_ms'] > 1000:
                recommendations.append({
                    'category': 'api',
                    'priority': 'medium',
                    'recommendation': 'Implement API response caching and optimize database queries',
                    'estimated_improvement': 25.0,
                    'difficulty': 'medium'
                })
            
            # Store recommendations
            if recommendations:
                self.store_optimization_recommendations(recommendations, metrics['timestamp'])
                
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate optimization recommendations: {e}")
            return []

    def store_optimization_recommendations(self, recommendations: List[Dict], timestamp: float):
        """Store optimization recommendations in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for rec in recommendations:
                cursor.execute('''
                    INSERT INTO optimization_recommendations (
                        timestamp, datetime_str, category, priority,
                        recommendation, estimated_improvement_percent,
                        implementation_difficulty
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp, datetime.fromtimestamp(timestamp).isoformat(),
                    rec['category'], rec['priority'], rec['recommendation'],
                    rec['estimated_improvement'], rec['difficulty']
                ))
                
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store optimization recommendations: {e}")

    def monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("🔄 Starting performance monitoring loop")
        
        while self.monitoring_active:
            try:
                # Collect metrics
                metrics = self.collect_system_metrics()
                if metrics:
                    # Store metrics
                    self.store_metrics(metrics)
                    
                    # Check for alerts
                    alerts = self.check_alert_conditions(metrics)
                    
                    # Generate recommendations (less frequently)
                    if int(time.time()) % 60 == 0:  # Every minute
                        recommendations = self.generate_optimization_recommendations(metrics)
                    
                    # Add to buffer for real-time access
                    self.metrics_buffer.append(metrics)
                    
                    # Log summary every 10 cycles
                    if len(self.metrics_buffer) % 10 == 0:
                        logger.info(f"📊 CPU: {metrics['cpu_percent']:.1f}% | "
                                  f"Memory: {metrics['memory_percent']:.1f}% | "
                                  f"Score: {metrics['optimization_score']:.1f}/100")
                
                time.sleep(5)  # Monitor every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)

    def start_monitoring(self):
        """Start performance monitoring in background thread"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info("✅ Performance monitoring started")

    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
            
        logger.info("⏹️  Performance monitoring stopped")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current performance status"""
        try:
            if not self.metrics_buffer:
                return {'status': 'no_data'}
                
            latest_metrics = self.metrics_buffer[-1]
            
            # Get recent alerts
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM performance_alerts 
                WHERE timestamp > ? AND resolved = 0
            ''', (time.time() - 300,))  # Last 5 minutes
            
            active_alerts = cursor.fetchone()[0]
            conn.close()
            
            status = {
                'timestamp': latest_metrics['timestamp'],
                'cpu_percent': latest_metrics['cpu_percent'],
                'memory_percent': latest_metrics['memory_percent'],
                'disk_usage_percent': latest_metrics['disk_usage_percent'],
                'optimization_score': latest_metrics['optimization_score'],
                'active_alerts': active_alerts,
                'monitoring_active': self.monitoring_active,
                'buffer_size': len(self.metrics_buffer)
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get current status: {e}")
            return {'status': 'error', 'error': str(e)}

    def generate_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = time.time() - (hours * 3600)
            
            # Get average metrics
            cursor.execute('''
                SELECT AVG(cpu_percent), AVG(memory_percent), AVG(disk_usage_percent),
                       AVG(optimization_score), AVG(api_response_time_ms),
                       COUNT(*) as samples
                FROM performance_metrics 
                WHERE timestamp > ?
            ''', (cutoff_time,))
            
            avg_metrics = cursor.fetchone()
            
            # Get alerts summary
            cursor.execute('''
                SELECT alert_type, severity, COUNT(*) 
                FROM performance_alerts 
                WHERE timestamp > ?
                GROUP BY alert_type, severity
            ''', (cutoff_time,))
            
            alerts_summary = cursor.fetchall()
            
            # Get optimization recommendations
            cursor.execute('''
                SELECT category, priority, COUNT(*) 
                FROM optimization_recommendations 
                WHERE timestamp > ?
                GROUP BY category, priority
            ''', (cutoff_time,))
            
            recommendations_summary = cursor.fetchall()
            
            conn.close()
            
            report = {
                'period_hours': hours,
                'generated_at': datetime.now().isoformat(),
                'averages': {
                    'cpu_percent': round(avg_metrics[0] or 0, 2),
                    'memory_percent': round(avg_metrics[1] or 0, 2),
                    'disk_usage_percent': round(avg_metrics[2] or 0, 2),
                    'optimization_score': round(avg_metrics[3] or 0, 2),
                    'api_response_time_ms': round(avg_metrics[4] or 0, 2),
                    'total_samples': avg_metrics[5] or 0
                },
                'alerts': [{'type': a[0], 'severity': a[1], 'count': a[2]} for a in alerts_summary],
                'recommendations': [{'category': r[0], 'priority': r[1], 'count': r[2]} for r in recommendations_summary]
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
            return {'error': str(e)}

def main():
    """Main function for standalone execution"""
    monitor = AdvancedPerformanceMonitor()
    
    try:
        print("🚀 Starting Advanced Performance Monitor")
        print("Press Ctrl+C to stop monitoring\n")
        
        monitor.start_monitoring()
        
        # Keep running and show periodic updates
        while True:
            time.sleep(30)
            status = monitor.get_current_status()
            if status.get('status') != 'error':
                print(f"💡 Status: CPU {status['cpu_percent']:.1f}% | "
                      f"Memory {status['memory_percent']:.1f}% | "
                      f"Score {status['optimization_score']:.1f}/100 | "
                      f"Alerts: {status['active_alerts']}")
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        monitor.stop_monitoring()
        
        # Generate final report
        report = monitor.generate_performance_report(1)  # Last hour
        print("\n📊 Final Performance Report:")
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()