#!/usr/bin/env python3
"""
Real-Time Performance Dashboard for DaVinci Resolve OpenClaw
Professional web interface for enterprise performance monitoring

Features:
- Live system metrics with auto-refresh
- Interactive performance charts and graphs
- Real-time alert monitoring and management
- System health overview with status indicators
- Performance optimization recommendations
- Historical trend analysis
- Client-ready professional interface

Integrates with: advanced_performance_monitor.py
Port: 8081 (separate from main dashboard on 8080)
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs
import statistics

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceDashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the real-time performance dashboard"""
    
    def do_GET(self):
        """Handle GET requests"""
        url_path = urlparse(self.path).path
        query_params = parse_qs(urlparse(self.path).query)
        
        if url_path == '/':
            self.serve_dashboard()
        elif url_path == '/api/metrics':
            self.serve_metrics_api()
        elif url_path == '/api/alerts':
            self.serve_alerts_api()
        elif url_path == '/api/recommendations':
            self.serve_recommendations_api()
        elif url_path == '/api/system_status':
            self.serve_system_status_api()
        elif url_path == '/api/performance_history':
            hours = int(query_params.get('hours', [24])[0])
            self.serve_performance_history_api(hours)
        else:
            self.send_error(404)
    
    def serve_dashboard(self):
        """Serve the main dashboard HTML"""
        html_content = self.generate_dashboard_html()
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())
    
    def serve_metrics_api(self):
        """Serve current system metrics as JSON"""
        try:
            metrics = self.get_latest_metrics()
            self.send_json_response(metrics)
        except Exception as e:
            logger.error(f"Error serving metrics: {e}")
            self.send_json_response({"error": str(e)}, 500)
    
    def serve_alerts_api(self):
        """Serve active alerts as JSON"""
        try:
            alerts = self.get_active_alerts()
            self.send_json_response(alerts)
        except Exception as e:
            logger.error(f"Error serving alerts: {e}")
            self.send_json_response({"error": str(e)}, 500)
    
    def serve_recommendations_api(self):
        """Serve optimization recommendations as JSON"""
        try:
            recommendations = self.get_recommendations()
            self.send_json_response(recommendations)
        except Exception as e:
            logger.error(f"Error serving recommendations: {e}")
            self.send_json_response(recommendations)
    
    def serve_system_status_api(self):
        """Serve overall system status as JSON"""
        try:
            status = self.get_system_status()
            self.send_json_response(status)
        except Exception as e:
            logger.error(f"Error serving system status: {e}")
            self.send_json_response({"error": str(e)}, 500)
    
    def serve_performance_history_api(self, hours=24):
        """Serve performance history for specified hours"""
        try:
            history = self.get_performance_history(hours)
            self.send_json_response(history)
        except Exception as e:
            logger.error(f"Error serving performance history: {e}")
            self.send_json_response({"error": str(e)}, 500)
    
    def send_json_response(self, data, status_code=200):
        """Send JSON response with CORS headers"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def get_latest_metrics(self):
        """Get latest performance metrics from database"""
        db_path = 'performance_analytics_enhanced.db'
        if not os.path.exists(db_path):
            return {"error": "Performance database not found"}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get latest metrics
            cursor.execute("""
                SELECT * FROM performance_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return {"error": "No metrics available"}
            
            # Get column names
            columns = [description[0] for description in cursor.description]
            metrics = dict(zip(columns, row))
            
            conn.close()
            return metrics
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            return {"error": f"Database error: {e}"}
    
    def get_active_alerts(self):
        """Get active alerts from database"""
        db_path = 'performance_analytics_enhanced.db'
        if not os.path.exists(db_path):
            return []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get recent alerts (last 24 hours)
            yesterday = datetime.now() - timedelta(days=1)
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC
            """, (yesterday.isoformat(),))
            
            columns = [description[0] for description in cursor.description]
            alerts = []
            for row in cursor.fetchall():
                alerts.append(dict(zip(columns, row)))
            
            conn.close()
            return alerts
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []
    
    def get_recommendations(self):
        """Get optimization recommendations from database"""
        db_path = 'performance_analytics_enhanced.db'
        if not os.path.exists(db_path):
            return []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get recent recommendations (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            cursor.execute("""
                SELECT * FROM recommendations 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC
                LIMIT 10
            """, (week_ago.isoformat(),))
            
            columns = [description[0] for description in cursor.description]
            recommendations = []
            for row in cursor.fetchall():
                recommendations.append(dict(zip(columns, row)))
            
            conn.close()
            return recommendations
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            return []
    
    def get_system_status(self):
        """Get overall system health status"""
        try:
            metrics = self.get_latest_metrics()
            if "error" in metrics:
                return {"status": "error", "message": metrics["error"]}
            
            # Calculate overall health score
            health_score = 100
            status_issues = []
            
            # Check CPU usage
            if metrics.get('cpu_percent', 0) > 80:
                health_score -= 20
                status_issues.append(f"High CPU usage: {metrics['cpu_percent']:.1f}%")
            
            # Check memory usage
            if metrics.get('memory_percent', 0) > 85:
                health_score -= 15
                status_issues.append(f"High memory usage: {metrics['memory_percent']:.1f}%")
            
            # Check disk usage
            if metrics.get('disk_percent', 0) > 90:
                health_score -= 10
                status_issues.append(f"High disk usage: {metrics['disk_percent']:.1f}%")
            
            # Determine status level
            if health_score >= 90:
                status_level = "excellent"
            elif health_score >= 70:
                status_level = "good"
            elif health_score >= 50:
                status_level = "warning"
            else:
                status_level = "critical"
            
            return {
                "status": status_level,
                "health_score": health_score,
                "issues": status_issues,
                "last_updated": metrics.get('timestamp', 'unknown'),
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Error calculating system status: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_performance_history(self, hours=24):
        """Get performance history for specified number of hours"""
        db_path = 'performance_analytics_enhanced.db'
        if not os.path.exists(db_path):
            return {"error": "Performance database not found"}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get metrics from specified time period
            start_time = datetime.now() - timedelta(hours=hours)
            cursor.execute("""
                SELECT timestamp, cpu_percent, memory_percent, disk_percent
                FROM performance_metrics 
                WHERE timestamp > ? 
                ORDER BY timestamp ASC
            """, (start_time.isoformat(),))
            
            rows = cursor.fetchall()
            
            history = {
                "timestamps": [],
                "cpu_usage": [],
                "memory_usage": [],
                "disk_usage": []
            }
            
            for row in rows:
                timestamp, cpu, memory, disk = row
                history["timestamps"].append(timestamp)
                history["cpu_usage"].append(cpu)
                history["memory_usage"].append(memory)
                history["disk_usage"].append(disk)
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            return {"error": f"Database error: {e}"}
    
    def generate_dashboard_html(self):
        """Generate the dashboard HTML with embedded CSS and JavaScript"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DaVinci Resolve OpenClaw - Performance Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            color: #ffffff;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 1rem 2rem;
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .header h1 {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(45deg, #ff6b35, #f7931e);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header .subtitle {
            color: #aaa;
            margin-top: 0.5rem;
            font-size: 1.1rem;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        .card h3 {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #ff6b35;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .metric-label {
            color: #aaa;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-excellent { background-color: #4CAF50; }
        .status-good { background-color: #8BC34A; }
        .status-warning { background-color: #FF9800; }
        .status-critical { background-color: #F44336; }
        .status-error { background-color: #9E9E9E; }
        
        .chart-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1rem;
        }
        
        .chart {
            width: 100%;
            height: 300px;
        }
        
        .alert-item {
            background: rgba(244, 67, 54, 0.1);
            border: 1px solid rgba(244, 67, 54, 0.3);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.5rem;
        }
        
        .alert-time {
            color: #aaa;
            font-size: 0.8rem;
        }
        
        .recommendation-item {
            background: rgba(76, 175, 80, 0.1);
            border: 1px solid rgba(76, 175, 80, 0.3);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.5rem;
        }
        
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            border-top-color: #ff6b35;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .auto-refresh {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(255, 107, 53, 0.9);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        
        .auto-refresh:hover {
            background: rgba(255, 107, 53, 1);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 DaVinci Resolve OpenClaw</h1>
        <div class="subtitle">Real-Time Performance Dashboard • Enterprise Monitoring</div>
    </div>
    
    <div class="container">
        <div class="grid">
            <div class="card">
                <h3>System Status</h3>
                <div id="system-status">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>CPU Usage</h3>
                <div id="cpu-usage">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>Memory Usage</h3>
                <div id="memory-usage">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>Disk Usage</h3>
                <div id="disk-usage">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Performance History (24 Hours)</h3>
            <canvas id="performance-chart" class="chart"></canvas>
        </div>
        
        <div class="grid" style="margin-top: 2rem;">
            <div class="card">
                <h3>Active Alerts</h3>
                <div id="active-alerts">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>Optimization Recommendations</h3>
                <div id="recommendations">
                    <div class="loading">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <button id="auto-refresh-btn" class="auto-refresh">Auto-refresh: ON</button>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        let autoRefresh = true;
        let refreshInterval;
        let performanceChart;
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            loadDashboardData();
            initializeChart();
            startAutoRefresh();
            
            // Auto-refresh toggle
            document.getElementById('auto-refresh-btn').addEventListener('click', function() {
                autoRefresh = !autoRefresh;
                this.textContent = `Auto-refresh: ${autoRefresh ? 'ON' : 'OFF'}`;
                if (autoRefresh) {
                    startAutoRefresh();
                } else {
                    clearInterval(refreshInterval);
                }
            });
        });
        
        function loadDashboardData() {
            loadSystemStatus();
            loadMetrics();
            loadAlerts();
            loadRecommendations();
            loadPerformanceHistory();
        }
        
        function loadSystemStatus() {
            fetch('/api/system_status')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('system-status');
                    const statusClass = `status-${data.status}`;
                    
                    container.innerHTML = `
                        <div>
                            <span class="status-indicator ${statusClass}"></span>
                            <span style="font-size: 1.2rem; font-weight: 600; text-transform: uppercase;">${data.status}</span>
                        </div>
                        <div class="metric-value" style="font-size: 2rem;">${data.health_score}%</div>
                        <div class="metric-label">Health Score</div>
                        ${data.issues.length > 0 ? `<div style="margin-top: 1rem; font-size: 0.9rem; color: #ffab40;">${data.issues.join(', ')}</div>` : ''}
                    `;
                })
                .catch(error => {
                    document.getElementById('system-status').innerHTML = `<div style="color: #f44336;">Error loading status</div>`;
                });
        }
        
        function loadMetrics() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        ['cpu-usage', 'memory-usage', 'disk-usage'].forEach(id => {
                            document.getElementById(id).innerHTML = `<div style="color: #f44336;">No data</div>`;
                        });
                        return;
                    }
                    
                    // CPU Usage
                    document.getElementById('cpu-usage').innerHTML = `
                        <div class="metric-value" style="color: ${data.cpu_percent > 80 ? '#f44336' : data.cpu_percent > 60 ? '#ff9800' : '#4caf50'}">${data.cpu_percent.toFixed(1)}%</div>
                        <div class="metric-label">Current Usage</div>
                    `;
                    
                    // Memory Usage
                    document.getElementById('memory-usage').innerHTML = `
                        <div class="metric-value" style="color: ${data.memory_percent > 85 ? '#f44336' : data.memory_percent > 70 ? '#ff9800' : '#4caf50'}">${data.memory_percent.toFixed(1)}%</div>
                        <div class="metric-label">Current Usage</div>
                    `;
                    
                    // Disk Usage
                    document.getElementById('disk-usage').innerHTML = `
                        <div class="metric-value" style="color: ${data.disk_percent > 90 ? '#f44336' : data.disk_percent > 75 ? '#ff9800' : '#4caf50'}">${data.disk_percent.toFixed(1)}%</div>
                        <div class="metric-label">Current Usage</div>
                    `;
                })
                .catch(error => {
                    ['cpu-usage', 'memory-usage', 'disk-usage'].forEach(id => {
                        document.getElementById(id).innerHTML = `<div style="color: #f44336;">Error loading</div>`;
                    });
                });
        }
        
        function loadAlerts() {
            fetch('/api/alerts')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('active-alerts');
                    
                    if (data.length === 0) {
                        container.innerHTML = '<div style="color: #4caf50;">No active alerts</div>';
                        return;
                    }
                    
                    container.innerHTML = data.map(alert => `
                        <div class="alert-item">
                            <div style="font-weight: 600;">${alert.message}</div>
                            <div class="alert-time">${new Date(alert.timestamp).toLocaleString()}</div>
                        </div>
                    `).join('');
                })
                .catch(error => {
                    document.getElementById('active-alerts').innerHTML = `<div style="color: #f44336;">Error loading alerts</div>`;
                });
        }
        
        function loadRecommendations() {
            fetch('/api/recommendations')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('recommendations');
                    
                    if (data.length === 0) {
                        container.innerHTML = '<div style="color: #aaa;">No recommendations available</div>';
                        return;
                    }
                    
                    container.innerHTML = data.slice(0, 5).map(rec => `
                        <div class="recommendation-item">
                            <div style="font-weight: 600;">${rec.recommendation}</div>
                            <div class="alert-time">${new Date(rec.timestamp).toLocaleString()}</div>
                        </div>
                    `).join('');
                })
                .catch(error => {
                    document.getElementById('recommendations').innerHTML = `<div style="color: #f44336;">Error loading recommendations</div>`;
                });
        }
        
        function initializeChart() {
            const ctx = document.getElementById('performance-chart').getContext('2d');
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU Usage (%)',
                            data: [],
                            borderColor: '#ff6b35',
                            backgroundColor: 'rgba(255, 107, 53, 0.1)',
                            tension: 0.4
                        },
                        {
                            label: 'Memory Usage (%)',
                            data: [],
                            borderColor: '#4caf50',
                            backgroundColor: 'rgba(76, 175, 80, 0.1)',
                            tension: 0.4
                        },
                        {
                            label: 'Disk Usage (%)',
                            data: [],
                            borderColor: '#2196f3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#ffffff'
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                color: '#aaaaaa'
                            },
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                color: '#aaaaaa'
                            },
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            }
                        }
                    }
                }
            });
        }
        
        function loadPerformanceHistory() {
            fetch('/api/performance_history?hours=24')
                .then(response => response.json())
                .then(data => {
                    if (data.error) return;
                    
                    const labels = data.timestamps.map(ts => {
                        const date = new Date(ts);
                        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    });
                    
                    performanceChart.data.labels = labels;
                    performanceChart.data.datasets[0].data = data.cpu_usage;
                    performanceChart.data.datasets[1].data = data.memory_usage;
                    performanceChart.data.datasets[2].data = data.disk_usage;
                    performanceChart.update();
                })
                .catch(error => {
                    console.error('Error loading performance history:', error);
                });
        }
        
        function startAutoRefresh() {
            refreshInterval = setInterval(() => {
                if (autoRefresh) {
                    loadDashboardData();
                }
            }, 5000); // Refresh every 5 seconds
        }
    </script>
</body>
</html>
        """

def start_dashboard_server(port=8081):
    """Start the real-time dashboard server"""
    try:
        with socketserver.TCPServer(("", port), PerformanceDashboardHandler) as httpd:
            logger.info(f"🚀 Real-Time Performance Dashboard started on http://localhost:{port}")
            logger.info(f"📊 Professional interface for enterprise monitoring")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error starting dashboard server: {e}")

if __name__ == "__main__":
    start_dashboard_server()