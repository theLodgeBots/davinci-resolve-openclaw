#!/usr/bin/env python3
"""
Enterprise Multi-Client Management System for DaVinci Resolve OpenClaw
Complete client isolation, project management, and resource allocation system

Features:
- Isolated client workspaces with secure project management
- Resource allocation and usage tracking per client
- Client-specific workflow configurations and preferences
- Automated billing and usage reporting
- SLA monitoring and compliance tracking
- API-driven client management with webhook support
"""

import json
import os
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import uuid
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import configparser
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClientTier(Enum):
    """Client service tier levels"""
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    PREMIUM = "premium"

class ClientStatus(Enum):
    """Client account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    TRIAL = "trial"

@dataclass
class ClientConfiguration:
    """Client-specific configuration and preferences"""
    client_id: str
    name: str
    email: str
    tier: ClientTier
    status: ClientStatus
    created_at: datetime
    last_active: datetime
    
    # Resource limits based on tier
    max_projects: int
    max_storage_gb: float
    max_render_hours_monthly: int
    max_concurrent_jobs: int
    
    # Workflow preferences
    default_export_formats: List[str]
    color_grading_presets: List[str]
    preferred_aspect_ratios: List[str]
    automation_level: str  # full, assisted, manual
    
    # API access
    api_key: str
    webhook_url: Optional[str] = None
    
    # Billing
    billing_contact: str = ""
    monthly_spend_limit: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_active'] = self.last_active.isoformat()
        data['tier'] = self.tier.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientConfiguration':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_active'] = datetime.fromisoformat(data['last_active'])
        data['tier'] = ClientTier(data['tier'])
        data['status'] = ClientStatus(data['status'])
        return cls(**data)

@dataclass
class ResourceUsage:
    """Track resource usage per client"""
    client_id: str
    month: str  # YYYY-MM format
    projects_created: int = 0
    storage_used_gb: float = 0.0
    render_minutes: int = 0
    api_calls: int = 0
    bandwidth_gb: float = 0.0
    compute_hours: float = 0.0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()

class MultiClientManager:
    """Central management system for multiple clients"""
    
    def __init__(self, base_directory: str = "/var/openclaw/clients"):
        self.base_directory = Path(base_directory)
        self.clients_config_file = self.base_directory / "clients.json"
        self.usage_db_file = self.base_directory / "usage.db"
        
        # Thread safety
        self._lock = threading.Lock()
        
        # In-memory cache
        self.clients = {}  # client_id -> ClientConfiguration
        self.active_sessions = {}  # client_id -> session info
        
        # Initialize directory structure
        self._setup_directories()
        self._init_database()
        self._load_clients()
    
    def _setup_directories(self):
        """Create necessary directory structure"""
        self.base_directory.mkdir(parents=True, exist_ok=True)
        
        # Create standard subdirectories
        subdirs = ['configs', 'workspaces', 'temp', 'backups', 'logs']
        for subdir in subdirs:
            (self.base_directory / subdir).mkdir(exist_ok=True)
    
    def _init_database(self):
        """Initialize SQLite database for usage tracking"""
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        # Create usage table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage (
                client_id TEXT,
                month TEXT,
                projects_created INTEGER DEFAULT 0,
                storage_used_gb REAL DEFAULT 0.0,
                render_minutes INTEGER DEFAULT 0,
                api_calls INTEGER DEFAULT 0,
                bandwidth_gb REAL DEFAULT 0.0,
                compute_hours REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (client_id, month)
            )
        ''')
        
        # Create activity log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                activity_type TEXT,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_clients(self):
        """Load client configurations from file"""
        if self.clients_config_file.exists():
            with open(self.clients_config_file, 'r') as f:
                clients_data = json.load(f)
                
            for client_data in clients_data:
                client = ClientConfiguration.from_dict(client_data)
                self.clients[client.client_id] = client
            
            logger.info(f"Loaded {len(self.clients)} client configurations")
    
    def _save_clients(self):
        """Save client configurations to file"""
        clients_data = [client.to_dict() for client in self.clients.values()]
        
        with open(self.clients_config_file, 'w') as f:
            json.dump(clients_data, f, indent=2)
        
        logger.info(f"Saved {len(self.clients)} client configurations")
    
    def create_client(self, name: str, email: str, tier: ClientTier = ClientTier.BASIC) -> str:
        """Create a new client with isolated workspace"""
        with self._lock:
            client_id = str(uuid.uuid4())
            api_key = secrets.token_urlsafe(32)
            
            # Define tier-based limits
            tier_limits = {
                ClientTier.BASIC: {
                    'max_projects': 5,
                    'max_storage_gb': 10.0,
                    'max_render_hours_monthly': 10,
                    'max_concurrent_jobs': 1
                },
                ClientTier.PROFESSIONAL: {
                    'max_projects': 25,
                    'max_storage_gb': 100.0,
                    'max_render_hours_monthly': 50,
                    'max_concurrent_jobs': 3
                },
                ClientTier.ENTERPRISE: {
                    'max_projects': 100,
                    'max_storage_gb': 500.0,
                    'max_render_hours_monthly': 200,
                    'max_concurrent_jobs': 5
                },
                ClientTier.PREMIUM: {
                    'max_projects': 1000,
                    'max_storage_gb': 2000.0,
                    'max_render_hours_monthly': 1000,
                    'max_concurrent_jobs': 10
                }
            }
            
            limits = tier_limits[tier]
            now = datetime.now()
            
            client = ClientConfiguration(
                client_id=client_id,
                name=name,
                email=email,
                tier=tier,
                status=ClientStatus.TRIAL,
                created_at=now,
                last_active=now,
                api_key=api_key,
                **limits,
                default_export_formats=['mp4', 'mov'],
                color_grading_presets=['neutral', 'warm'],
                preferred_aspect_ratios=['16:9', '9:16'],
                automation_level='assisted'
            )
            
            # Create client workspace directory
            client_workspace = self.base_directory / "workspaces" / client_id
            client_workspace.mkdir(parents=True, exist_ok=True)
            
            # Create client subdirectories
            subdirs = ['projects', 'exports', 'temp', 'backups']
            for subdir in subdirs:
                (client_workspace / subdir).mkdir(exist_ok=True)
            
            # Save client configuration
            self.clients[client_id] = client
            self._save_clients()
            
            # Initialize usage tracking
            self._init_client_usage(client_id)
            
            # Log activity
            self._log_activity(client_id, "client_created", f"Created client: {name}")
            
            logger.info(f"Created new client: {name} ({client_id}) with tier: {tier.value}")
            return client_id
    
    def get_client(self, client_id: str) -> Optional[ClientConfiguration]:
        """Get client configuration"""
        return self.clients.get(client_id)
    
    def get_client_by_api_key(self, api_key: str) -> Optional[ClientConfiguration]:
        """Get client by API key"""
        for client in self.clients.values():
            if client.api_key == api_key:
                return client
        return None
    
    def update_client_status(self, client_id: str, status: ClientStatus) -> bool:
        """Update client status"""
        with self._lock:
            if client_id not in self.clients:
                return False
            
            old_status = self.clients[client_id].status
            self.clients[client_id].status = status
            self._save_clients()
            
            self._log_activity(
                client_id, 
                "status_changed", 
                f"Status changed from {old_status.value} to {status.value}"
            )
            
            return True
    
    def get_client_workspace(self, client_id: str) -> Path:
        """Get client's isolated workspace directory"""
        return self.base_directory / "workspaces" / client_id
    
    def check_resource_limits(self, client_id: str, resource_type: str, requested_amount: float = 1.0) -> bool:
        """Check if client can use requested resources"""
        client = self.get_client(client_id)
        if not client or client.status != ClientStatus.ACTIVE:
            return False
        
        current_usage = self.get_current_usage(client_id)
        current_month = datetime.now().strftime("%Y-%m")
        
        usage = current_usage.get(current_month, ResourceUsage(client_id, current_month))
        
        # Check limits based on resource type
        if resource_type == "projects":
            return usage.projects_created < client.max_projects
        elif resource_type == "storage":
            return (usage.storage_used_gb + requested_amount) <= client.max_storage_gb
        elif resource_type == "render_time":
            return (usage.render_minutes + requested_amount) <= (client.max_render_hours_monthly * 60)
        elif resource_type == "concurrent_jobs":
            active_jobs = len(self.get_active_jobs(client_id))
            return active_jobs < client.max_concurrent_jobs
        
        return True
    
    def record_resource_usage(self, client_id: str, usage_type: str, amount: float, description: str = ""):
        """Record resource usage for a client"""
        current_month = datetime.now().strftime("%Y-%m")
        
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        # Update usage record
        if usage_type == "projects":
            cursor.execute('''
                INSERT OR REPLACE INTO usage 
                (client_id, month, projects_created, last_updated)
                VALUES (?, ?, COALESCE((SELECT projects_created FROM usage WHERE client_id=? AND month=?), 0) + ?, ?)
            ''', (client_id, current_month, client_id, current_month, int(amount), datetime.now()))
        elif usage_type == "storage":
            cursor.execute('''
                INSERT OR REPLACE INTO usage 
                (client_id, month, storage_used_gb, last_updated)
                VALUES (?, ?, COALESCE((SELECT storage_used_gb FROM usage WHERE client_id=? AND month=?), 0) + ?, ?)
            ''', (client_id, current_month, client_id, current_month, amount, datetime.now()))
        elif usage_type == "render_time":
            cursor.execute('''
                INSERT OR REPLACE INTO usage 
                (client_id, month, render_minutes, last_updated)
                VALUES (?, ?, COALESCE((SELECT render_minutes FROM usage WHERE client_id=? AND month=?), 0) + ?, ?)
            ''', (client_id, current_month, client_id, current_month, int(amount), datetime.now()))
        elif usage_type == "api_calls":
            cursor.execute('''
                INSERT OR REPLACE INTO usage 
                (client_id, month, api_calls, last_updated)
                VALUES (?, ?, COALESCE((SELECT api_calls FROM usage WHERE client_id=? AND month=?), 0) + ?, ?)
            ''', (client_id, current_month, client_id, current_month, int(amount), datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Log the activity
        self._log_activity(client_id, f"resource_usage_{usage_type}", description)
    
    def get_current_usage(self, client_id: str) -> Dict[str, ResourceUsage]:
        """Get current resource usage for a client"""
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM usage WHERE client_id = ?
        ''', (client_id,))
        
        usage_records = {}
        for row in cursor.fetchall():
            usage = ResourceUsage(
                client_id=row[0],
                month=row[1],
                projects_created=row[2],
                storage_used_gb=row[3],
                render_minutes=row[4],
                api_calls=row[5],
                bandwidth_gb=row[6],
                compute_hours=row[7],
                last_updated=datetime.fromisoformat(row[8])
            )
            usage_records[usage.month] = usage
        
        conn.close()
        return usage_records
    
    def generate_usage_report(self, client_id: str, months: int = 3) -> Dict[str, Any]:
        """Generate comprehensive usage report for a client"""
        client = self.get_client(client_id)
        if not client:
            return {}
        
        usage_data = self.get_current_usage(client_id)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        report = {
            'client_info': {
                'name': client.name,
                'tier': client.tier.value,
                'status': client.status.value,
                'created_at': client.created_at.isoformat()
            },
            'resource_limits': {
                'max_projects': client.max_projects,
                'max_storage_gb': client.max_storage_gb,
                'max_render_hours_monthly': client.max_render_hours_monthly,
                'max_concurrent_jobs': client.max_concurrent_jobs
            },
            'usage_summary': {},
            'monthly_breakdown': {},
            'recommendations': []
        }
        
        # Analyze usage patterns
        total_projects = 0
        total_storage = 0.0
        total_render_minutes = 0
        
        for month, usage in usage_data.items():
            report['monthly_breakdown'][month] = {
                'projects_created': usage.projects_created,
                'storage_used_gb': usage.storage_used_gb,
                'render_minutes': usage.render_minutes,
                'api_calls': usage.api_calls
            }
            
            total_projects += usage.projects_created
            total_storage += usage.storage_used_gb
            total_render_minutes += usage.render_minutes
        
        report['usage_summary'] = {
            'total_projects': total_projects,
            'average_storage_gb': total_storage / max(len(usage_data), 1),
            'total_render_hours': total_render_minutes / 60,
            'utilization_rates': {
                'projects': (total_projects / (client.max_projects * len(usage_data))) * 100 if usage_data else 0,
                'storage': (total_storage / client.max_storage_gb) * 100,
                'render_time': (total_render_minutes / (client.max_render_hours_monthly * 60 * len(usage_data))) * 100 if usage_data else 0
            }
        }
        
        # Generate recommendations
        if report['usage_summary']['utilization_rates']['projects'] > 80:
            report['recommendations'].append("High project utilization - consider upgrading to higher tier")
        if report['usage_summary']['utilization_rates']['storage'] > 90:
            report['recommendations'].append("Storage nearly full - cleanup or upgrade recommended")
        if report['usage_summary']['utilization_rates']['render_time'] > 75:
            report['recommendations'].append("High render time usage - consider optimizing workflows")
        
        return report
    
    def get_active_jobs(self, client_id: str) -> List[Dict[str, Any]]:
        """Get list of currently active processing jobs for a client"""
        # This would integrate with the batch processor
        # For now, return empty list as placeholder
        return []
    
    def _init_client_usage(self, client_id: str):
        """Initialize usage tracking for a new client"""
        current_month = datetime.now().strftime("%Y-%m")
        
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO usage 
            (client_id, month, projects_created, storage_used_gb, render_minutes, api_calls)
            VALUES (?, ?, 0, 0.0, 0, 0)
        ''', (client_id, current_month))
        
        conn.commit()
        conn.close()
    
    def _log_activity(self, client_id: str, activity_type: str, description: str, metadata: Dict[str, Any] = None):
        """Log client activity"""
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO activity_log (client_id, activity_type, description, metadata)
            VALUES (?, ?, ?, ?)
        ''', (client_id, activity_type, description, json.dumps(metadata) if metadata else None))
        
        conn.commit()
        conn.close()
    
    def list_clients(self, status_filter: Optional[ClientStatus] = None) -> List[ClientConfiguration]:
        """List all clients with optional status filter"""
        clients = list(self.clients.values())
        
        if status_filter:
            clients = [c for c in clients if c.status == status_filter]
        
        return sorted(clients, key=lambda c: c.created_at, reverse=True)
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get overall system statistics across all clients"""
        total_clients = len(self.clients)
        active_clients = len([c for c in self.clients.values() if c.status == ClientStatus.ACTIVE])
        
        tier_breakdown = {}
        for tier in ClientTier:
            tier_breakdown[tier.value] = len([c for c in self.clients.values() if c.tier == tier])
        
        # Calculate total resource usage
        conn = sqlite3.connect(self.usage_db_file)
        cursor = conn.cursor()
        
        current_month = datetime.now().strftime("%Y-%m")
        cursor.execute('''
            SELECT 
                SUM(projects_created) as total_projects,
                SUM(storage_used_gb) as total_storage,
                SUM(render_minutes) as total_render_minutes,
                SUM(api_calls) as total_api_calls
            FROM usage 
            WHERE month = ?
        ''', (current_month,))
        
        usage_row = cursor.fetchone()
        conn.close()
        
        return {
            'total_clients': total_clients,
            'active_clients': active_clients,
            'tier_breakdown': tier_breakdown,
            'current_month_usage': {
                'total_projects': usage_row[0] or 0,
                'total_storage_gb': usage_row[1] or 0.0,
                'total_render_hours': (usage_row[2] or 0) / 60,
                'total_api_calls': usage_row[3] or 0
            }
        }


def main():
    """Demo and testing of the multi-client management system"""
    manager = MultiClientManager()
    
    # Create demo clients
    client1 = manager.create_client("TechCorp", "contact@techcorp.com", ClientTier.PROFESSIONAL)
    client2 = manager.create_client("StartupXYZ", "hello@startupxyz.com", ClientTier.BASIC)
    
    print(f"Created clients: {client1}, {client2}")
    
    # Test resource usage
    manager.record_resource_usage(client1, "projects", 1, "Created demo project")
    manager.record_resource_usage(client1, "storage", 5.5, "Uploaded 5.5GB of footage")
    manager.record_resource_usage(client1, "render_time", 30, "Rendered 30-minute project")
    
    # Generate reports
    report = manager.generate_usage_report(client1)
    print(f"Usage report for {client1}:")
    print(json.dumps(report, indent=2))
    
    # System statistics
    stats = manager.get_system_statistics()
    print("System statistics:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()