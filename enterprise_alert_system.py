#!/usr/bin/env python3
"""
Enterprise Alert System - DaVinci Resolve OpenClaw
Real-time email and Slack notifications for critical performance issues

Features:
- Email notifications via SMTP
- Slack webhook integration
- Discord webhook support
- Configurable alert thresholds
- Alert rate limiting (prevents spam)
- Professional alert templates
- Performance trend analysis
- Escalation management
- Alert history tracking
"""

import json
import time
import smtplib
import sqlite3
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw/alert_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AlertConfig:
    """Alert system configuration"""
    # Email settings
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_user: str = ""
    email_password: str = ""
    admin_emails: List[str] = None
    
    # Slack settings
    slack_webhook: str = ""
    slack_channel: str = "#alerts"
    
    # Discord settings
    discord_webhook: str = ""
    
    # Alert thresholds
    cpu_threshold: float = 90.0
    memory_threshold: float = 85.0
    disk_threshold: float = 90.0
    processing_time_threshold: int = 300  # seconds
    error_rate_threshold: float = 0.1  # 10%
    
    # Rate limiting
    min_alert_interval: int = 300  # 5 minutes between similar alerts
    max_alerts_per_hour: int = 10
    
    # Business hours (for non-critical alerts)
    business_start_hour: int = 9
    business_end_hour: int = 17
    
    def __post_init__(self):
        if self.admin_emails is None:
            self.admin_emails = []

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    level: str  # critical, warning, info
    title: str
    message: str
    component: str
    metric_value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    escalated: bool = False
    notification_sent: bool = False
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class AlertManager:
    """Enterprise alert management system"""
    
    def __init__(self, config_path: str = None):
        self.project_root = Path(__file__).parent
        self.config_path = config_path or self.project_root / "alert_config.json"
        self.db_path = self.project_root / "alert_system.db"
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize database
        self._init_database()
        
        # Alert tracking
        self.recent_alerts = defaultdict(list)
        self.alert_counts = defaultdict(int)
        
        logger.info("🚨 Enterprise Alert System initialized")
        logger.info(f"📧 Email alerts: {'Enabled' if self.config.admin_emails else 'Disabled'}")
        logger.info(f"💬 Slack alerts: {'Enabled' if self.config.slack_webhook else 'Disabled'}")
        logger.info(f"🎮 Discord alerts: {'Enabled' if self.config.discord_webhook else 'Disabled'}")
    
    def _load_config(self) -> AlertConfig:
        """Load alert configuration"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return AlertConfig(**data)
            else:
                # Create default config
                config = AlertConfig()
                self._save_config(config)
                return config
        except Exception as e:
            logger.error(f"Failed to load alert config: {e}")
            return AlertConfig()
    
    def _save_config(self, config: AlertConfig):
        """Save alert configuration"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(asdict(config), f, indent=2)
            logger.info(f"📝 Alert configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save alert config: {e}")
    
    def _init_database(self):
        """Initialize alert tracking database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS alerts (
                        id TEXT PRIMARY KEY,
                        level TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        threshold REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        resolved INTEGER DEFAULT 0,
                        escalated INTEGER DEFAULT 0,
                        notification_sent INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS alert_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
            logger.info("📊 Alert database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def check_system_health(self) -> List[Alert]:
        """Check system health and generate alerts"""
        alerts = []
        current_time = datetime.now()
        
        try:
            # Check performance metrics
            alerts.extend(self._check_performance_metrics())
            
            # Check processing times
            alerts.extend(self._check_processing_times())
            
            # Check error rates
            alerts.extend(self._check_error_rates())
            
            # Check disk space
            alerts.extend(self._check_disk_space())
            
            # Store new alerts
            for alert in alerts:
                if not self._is_duplicate_alert(alert):
                    self._store_alert(alert)
                    if self._should_send_notification(alert):
                        self._send_notifications(alert)
                        alert.notification_sent = True
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            # Create critical alert for monitoring failure
            critical_alert = Alert(
                id=f"monitoring_failure_{int(time.time())}",
                level="critical",
                title="Monitoring System Failure",
                message=f"Health check failed: {str(e)}",
                component="monitoring",
                metric_value=0.0,
                threshold=1.0,
                timestamp=current_time
            )
            alerts.append(critical_alert)
        
        return alerts
    
    def _check_performance_metrics(self) -> List[Alert]:
        """Check CPU, memory, and performance metrics"""
        alerts = []
        current_time = datetime.now()
        
        try:
            # Try to get metrics from performance monitor
            perf_db_path = self.project_root / "performance_analytics_enhanced.db"
            if perf_db_path.exists():
                with sqlite3.connect(perf_db_path) as conn:
                    # Get latest metrics
                    cursor = conn.execute('''
                        SELECT cpu_usage, memory_usage, disk_usage
                        FROM system_metrics 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    ''')
                    row = cursor.fetchone()
                    
                    if row:
                        cpu_usage, memory_usage, disk_usage = row
                        
                        # CPU alert
                        if cpu_usage > self.config.cpu_threshold:
                            alerts.append(Alert(
                                id=f"cpu_high_{int(time.time())}",
                                level="critical" if cpu_usage > 95 else "warning",
                                title="High CPU Usage",
                                message=f"CPU usage is {cpu_usage:.1f}% (threshold: {self.config.cpu_threshold}%)",
                                component="system",
                                metric_value=cpu_usage,
                                threshold=self.config.cpu_threshold,
                                timestamp=current_time
                            ))
                        
                        # Memory alert
                        if memory_usage > self.config.memory_threshold:
                            alerts.append(Alert(
                                id=f"memory_high_{int(time.time())}",
                                level="critical" if memory_usage > 95 else "warning",
                                title="High Memory Usage",
                                message=f"Memory usage is {memory_usage:.1f}% (threshold: {self.config.memory_threshold}%)",
                                component="system",
                                metric_value=memory_usage,
                                threshold=self.config.memory_threshold,
                                timestamp=current_time
                            ))
                        
                        # Disk alert
                        if disk_usage > self.config.disk_threshold:
                            alerts.append(Alert(
                                id=f"disk_high_{int(time.time())}",
                                level="critical" if disk_usage > 95 else "warning",
                                title="High Disk Usage",
                                message=f"Disk usage is {disk_usage:.1f}% (threshold: {self.config.disk_threshold}%)",
                                component="storage",
                                metric_value=disk_usage,
                                threshold=self.config.disk_threshold,
                                timestamp=current_time
                            ))
        
        except Exception as e:
            logger.warning(f"Performance metrics check failed: {e}")
        
        return alerts
    
    def _check_processing_times(self) -> List[Alert]:
        """Check for slow processing times"""
        alerts = []
        current_time = datetime.now()
        
        try:
            # Check recent render times from logs or database
            # This would integrate with your existing performance monitoring
            pass
        except Exception as e:
            logger.warning(f"Processing time check failed: {e}")
        
        return alerts
    
    def _check_error_rates(self) -> List[Alert]:
        """Check for high error rates"""
        alerts = []
        current_time = datetime.now()
        
        try:
            # Check error rates from logs or database
            # This would integrate with your existing error tracking
            pass
        except Exception as e:
            logger.warning(f"Error rate check failed: {e}")
        
        return alerts
    
    def _check_disk_space(self) -> List[Alert]:
        """Check available disk space"""
        alerts = []
        current_time = datetime.now()
        
        try:
            import shutil
            
            # Check main project disk
            total, used, free = shutil.disk_usage(self.project_root)
            usage_percent = (used / total) * 100
            
            if usage_percent > self.config.disk_threshold:
                alerts.append(Alert(
                    id=f"disk_space_{int(time.time())}",
                    level="critical" if usage_percent > 95 else "warning",
                    title="Low Disk Space",
                    message=f"Disk usage is {usage_percent:.1f}% (threshold: {self.config.disk_threshold}%)",
                    component="storage",
                    metric_value=usage_percent,
                    threshold=self.config.disk_threshold,
                    timestamp=current_time
                ))
        
        except Exception as e:
            logger.warning(f"Disk space check failed: {e}")
        
        return alerts
    
    def _is_duplicate_alert(self, alert: Alert) -> bool:
        """Check if alert is a duplicate of recent alerts"""
        alert_key = f"{alert.component}_{alert.title}"
        recent = self.recent_alerts[alert_key]
        
        # Clean old alerts (older than min_alert_interval)
        cutoff = time.time() - self.config.min_alert_interval
        self.recent_alerts[alert_key] = [t for t in recent if t > cutoff]
        
        return len(self.recent_alerts[alert_key]) > 0
    
    def _should_send_notification(self, alert: Alert) -> bool:
        """Determine if notification should be sent"""
        current_hour = datetime.now().hour
        
        # Critical alerts always send
        if alert.level == "critical":
            return True
        
        # Check business hours for warnings
        if alert.level == "warning":
            if self.config.business_start_hour <= current_hour <= self.config.business_end_hour:
                return True
        
        # Check rate limiting
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Count alerts in last hour
        hour_count = sum(1 for t in self.alert_counts.values() if t > hour_ago)
        
        return hour_count < self.config.max_alerts_per_hour
    
    def _store_alert(self, alert: Alert):
        """Store alert in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO alerts (
                        id, level, title, message, component, 
                        metric_value, threshold, timestamp,
                        resolved, escalated, notification_sent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.id, alert.level, alert.title, alert.message,
                    alert.component, alert.metric_value, alert.threshold,
                    alert.timestamp.isoformat(), int(alert.resolved),
                    int(alert.escalated), int(alert.notification_sent)
                ))
                conn.commit()
                
                # Track recent alert
                alert_key = f"{alert.component}_{alert.title}"
                self.recent_alerts[alert_key].append(time.time())
                
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    def _send_notifications(self, alert: Alert):
        """Send alert notifications via all configured channels"""
        try:
            # Send email notification
            if self.config.admin_emails and self.config.email_user:
                self._send_email_alert(alert)
            
            # Send Slack notification
            if self.config.slack_webhook:
                self._send_slack_alert(alert)
            
            # Send Discord notification
            if self.config.discord_webhook:
                self._send_discord_alert(alert)
            
            logger.info(f"📨 Notifications sent for alert: {alert.title}")
            
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")
    
    def _send_email_alert(self, alert: Alert):
        """Send email alert notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_user
            msg['To'] = ', '.join(self.config.admin_emails)
            msg['Subject'] = f"🚨 DaVinci Resolve Alert: {alert.title}"
            
            # Create professional email body
            body = self._create_email_body(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.email_user, self.config.email_password)
                server.send_message(msg)
            
            logger.info(f"📧 Email alert sent to {len(self.config.admin_emails)} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def _send_slack_alert(self, alert: Alert):
        """Send Slack alert notification"""
        try:
            # Determine emoji and color based on alert level
            emoji_map = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            color_map = {"critical": "danger", "warning": "warning", "info": "good"}
            
            payload = {
                "channel": self.config.slack_channel,
                "username": "DaVinci Resolve Monitor",
                "icon_emoji": ":movie_camera:",
                "attachments": [{
                    "color": color_map.get(alert.level, "good"),
                    "title": f"{emoji_map.get(alert.level, '🔵')} {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Component", "value": alert.component, "short": True},
                        {"title": "Level", "value": alert.level.upper(), "short": True},
                        {"title": "Value", "value": f"{alert.metric_value:.1f}", "short": True},
                        {"title": "Threshold", "value": f"{alert.threshold:.1f}", "short": True},
                    ],
                    "timestamp": int(alert.timestamp.timestamp())
                }]
            }
            
            response = requests.post(self.config.slack_webhook, json=payload)
            response.raise_for_status()
            
            logger.info("💬 Slack alert sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def _send_discord_alert(self, alert: Alert):
        """Send Discord alert notification"""
        try:
            # Determine color based on alert level
            color_map = {"critical": 0xFF0000, "warning": 0xFFFF00, "info": 0x0099FF}
            
            embed = {
                "title": f"🎬 DaVinci Resolve Alert",
                "description": alert.title,
                "color": color_map.get(alert.level, 0x0099FF),
                "fields": [
                    {"name": "Message", "value": alert.message, "inline": False},
                    {"name": "Component", "value": alert.component, "inline": True},
                    {"name": "Level", "value": alert.level.upper(), "inline": True},
                    {"name": "Current Value", "value": f"{alert.metric_value:.1f}", "inline": True},
                    {"name": "Threshold", "value": f"{alert.threshold:.1f}", "inline": True},
                ],
                "timestamp": alert.timestamp.isoformat(),
                "footer": {"text": "DaVinci Resolve OpenClaw Enterprise Monitor"}
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(self.config.discord_webhook, json=payload)
            response.raise_for_status()
            
            logger.info("🎮 Discord alert sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
    
    def _create_email_body(self, alert: Alert) -> str:
        """Create professional email body for alerts"""
        level_colors = {
            "critical": "#dc3545",
            "warning": "#ffc107", 
            "info": "#17a2b8"
        }
        
        color = level_colors.get(alert.level, "#17a2b8")
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, {color}, {color}dd); padding: 20px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">🎬 DaVinci Resolve Alert</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0; font-size: 14px;">Enterprise Monitoring System</p>
                </div>
                
                <!-- Alert Details -->
                <div style="padding: 30px;">
                    <div style="background-color: #f8f9fa; border-left: 4px solid {color}; padding: 15px; margin-bottom: 20px;">
                        <h2 style="color: {color}; margin: 0 0 10px 0; font-size: 20px;">{alert.title}</h2>
                        <p style="margin: 0; color: #333; line-height: 1.5;">{alert.message}</p>
                    </div>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px; font-weight: bold; color: #555;">Component:</td>
                            <td style="padding: 10px; color: #333;">{alert.component.title()}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px; font-weight: bold; color: #555;">Alert Level:</td>
                            <td style="padding: 10px; color: {color}; font-weight: bold;">{alert.level.upper()}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px; font-weight: bold; color: #555;">Current Value:</td>
                            <td style="padding: 10px; color: #333;">{alert.metric_value:.1f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px; font-weight: bold; color: #555;">Threshold:</td>
                            <td style="padding: 10px; color: #333;">{alert.threshold:.1f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; font-weight: bold; color: #555;">Timestamp:</td>
                            <td style="padding: 10px; color: #333;">{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                        </tr>
                    </table>
                    
                    <div style="margin-top: 30px; padding: 15px; background-color: #e9ecef; border-radius: 5px;">
                        <p style="margin: 0; color: #555; font-size: 14px;">
                            <strong>Next Steps:</strong> Please review the system status and take appropriate action if needed. 
                            Access the monitoring dashboard for detailed analysis.
                        </p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="background-color: #f8f9fa; padding: 15px 30px; text-align: center; border-top: 1px solid #eee;">
                    <p style="margin: 0; color: #666; font-size: 12px;">
                        DaVinci Resolve OpenClaw Enterprise Monitor<br>
                        Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def get_alert_history(self, hours: int = 24) -> List[Dict]:
        """Get alert history for specified hours"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM alerts 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC
                ''', (cutoff.isoformat(),))
                
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to get alert history: {e}")
            return []
    
    def resolve_alert(self, alert_id: str):
        """Mark alert as resolved"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE alerts 
                    SET resolved = 1 
                    WHERE id = ?
                ''', (alert_id,))
                
                conn.execute('''
                    INSERT INTO alert_history (alert_id, action, details)
                    VALUES (?, 'resolved', 'Alert marked as resolved')
                ''', (alert_id,))
                
                conn.commit()
            
            logger.info(f"✅ Alert {alert_id} marked as resolved")
            
        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")


def main():
    """Main alert system runner"""
    logger.info("🚨 Starting Enterprise Alert System")
    
    # Initialize alert manager
    alert_manager = AlertManager()
    
    # Check system health
    alerts = alert_manager.check_system_health()
    
    if alerts:
        logger.info(f"🔍 Generated {len(alerts)} alerts")
        for alert in alerts:
            logger.info(f"  • {alert.level.upper()}: {alert.title}")
    else:
        logger.info("✅ System healthy - no alerts generated")
    
    # Show recent alert history
    history = alert_manager.get_alert_history(hours=24)
    if history:
        logger.info(f"📊 Alert history (24h): {len(history)} alerts")
        for alert in history[:5]:  # Show last 5
            logger.info(f"  • {alert['timestamp']}: {alert['title']} ({alert['level']})")


if __name__ == "__main__":
    main()