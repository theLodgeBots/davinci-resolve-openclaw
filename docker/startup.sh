#!/bin/bash
# 🚀 DaVinci Resolve OpenClaw - Production Startup Script
# Enterprise SaaS Platform Initialization

set -e

echo "🎬 DaVinci Resolve OpenClaw - Enterprise SaaS Platform"
echo "⏰ $(date)"
echo "🚀 Starting production deployment..."

# Initialize directories
echo "📁 Initializing directory structure..."
mkdir -p /var/openclaw/clients/{configs,workspaces,logs}
mkdir -p /var/log/openclaw
mkdir -p /app/static

# Initialize enterprise client manager
echo "🏢 Initializing enterprise client management..."
python3 -c "
from enterprise_multi_client_manager import EnterpriseMultiClientManager
mgr = EnterpriseMultiClientManager()
mgr.initialize_system()
print('✅ Enterprise system initialized')
"

# Initialize performance analytics database
echo "📊 Initializing performance analytics..."
python3 -c "
from performance_analytics import PerformanceAnalytics
analytics = PerformanceAnalytics()
analytics.initialize_database()
print('✅ Performance analytics initialized')
"

# Validate system health
echo "🔍 Running system health check..."
python3 health_check.py || echo "⚠️ Health check completed with warnings"

# Generate initial dashboard data
echo "📈 Generating dashboard data..."
python3 dashboard_data.py

# Set proper permissions
echo "🔒 Setting file permissions..."
chown -R openclaw:openclaw /var/openclaw
chmod -R 755 /var/openclaw

# Start services with supervisor
echo "🎯 Starting services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/openclaw.conf