# 🐳 Docker Deployment Guide - DaVinci Resolve OpenClaw
**Enterprise SaaS Platform Production Deployment**

---

## 🎯 Overview

This guide covers the complete production deployment of DaVinci Resolve OpenClaw using Docker containers. The system is designed for enterprise SaaS deployment with multi-client architecture, professional API, and comprehensive monitoring.

---

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+ and Docker Compose 2.0+
- 8GB+ RAM, 100GB+ storage
- NVIDIA GPU (optional, for GPU acceleration)
- OpenAI API key
- Domain name (for production)

### Basic Deployment
```bash
# Clone the repository
git clone <repository-url>
cd davinci-resolve-openclaw

# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"

# Build and start services
docker-compose up -d

# Check service status
docker-compose ps
docker-compose logs openclaw-app
```

### Access Points
- **API Server**: http://localhost:8080/api/v1/
- **Web Dashboard**: http://localhost/dashboard/
- **Health Check**: http://localhost/health
- **API Documentation**: http://localhost:8080/api/v1/docs

---

## 🏗️ Architecture Components

### Core Services

#### 1. **openclaw-app** (Main Application)
- **Image**: Built from Dockerfile
- **Ports**: 80 (HTTP), 8080 (API)
- **Services**: API server, enterprise manager, performance monitor
- **Health Check**: Automated with 30s intervals

#### 2. **redis** (Caching & Job Queue)
- **Image**: redis:7-alpine
- **Purpose**: Session storage, job queuing, caching
- **Persistence**: Append-only file for durability

#### 3. **postgres** (Enterprise Database)
- **Image**: postgres:15-alpine
- **Purpose**: Client data, usage analytics, audit logs
- **Optional**: Can use SQLite for smaller deployments

---

## 🔧 Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your-openai-api-key-here

# Optional
POSTGRES_PASSWORD=secure-password
GRAFANA_PASSWORD=admin-password
OPENCLAW_ENV=production
API_PORT=8080
```

### Volume Mounts
- **openclaw_data**: Client workspaces and configurations
- **openclaw_logs**: Application and service logs
- **renders/**: Video render outputs (mounted from host)
- **exports/**: Client export directory (mounted from host)

---

## 📊 Service Profiles

### Development Profile (Default)
```bash
docker-compose up -d
```
Includes: App + Redis + PostgreSQL

### Production Profile
```bash
docker-compose --profile production up -d
```
Includes: All services + Load balancer + SSL

### Monitoring Profile
```bash
docker-compose --profile monitoring up -d
```
Includes: All services + Prometheus + Grafana

---

## 🛡️ Security Configuration

### SSL/TLS Setup
```bash
# Create SSL certificates directory
mkdir -p docker/ssl

# Generate self-signed certificate (development)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/server.key \
  -out docker/ssl/server.crt

# Or copy your production certificates
cp your-cert.pem docker/ssl/server.crt
cp your-key.pem docker/ssl/server.key
```

### API Security
- **Authentication**: API key + JWT tokens
- **Rate Limiting**: Tier-based limits per client
- **CORS**: Configurable cross-origin policies
- **File Upload**: 16GB max with security validation

---

## 📈 Monitoring & Analytics

### Health Monitoring
```bash
# Check application health
curl http://localhost:8080/api/v1/health

# View service logs
docker-compose logs -f openclaw-app

# Monitor resource usage
docker stats openclaw-enterprise
```

### Performance Metrics (with Prometheus/Grafana)
- **API Response Times**: Request/response metrics
- **Resource Utilization**: CPU, memory, storage
- **Client Usage**: Per-client analytics and billing
- **System Health**: Service availability and errors

---

## 🏢 Multi-Client Configuration

### Client Tier Configuration
The system supports 4 service tiers:

| Tier | Projects | Storage | Render Hours | Concurrent Jobs |
|------|----------|---------|--------------|-----------------|
| Basic | 5 | 10GB | 10/month | 1 |
| Professional | 25 | 100GB | 50/month | 3 |
| Enterprise | 100 | 500GB | 200/month | 5 |
| Premium | 1000 | 2TB | 1000/month | 10 |

### Adding New Clients
```bash
# Use the API to create new clients
curl -X POST http://localhost:8080/api/v1/admin/clients \
  -H "X-API-Key: admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Example Agency",
    "tier": "professional",
    "contact_email": "admin@example.com"
  }'
```

---

## 🚀 Scaling & Production

### Horizontal Scaling
```yaml
# docker-compose.scale.yml
version: '3.8'
services:
  openclaw-app:
    deploy:
      replicas: 3
    environment:
      - INSTANCE_ID=${HOSTNAME}
```

```bash
# Scale to multiple instances
docker-compose -f docker-compose.yml -f docker-compose.scale.yml up -d --scale openclaw-app=3
```

### Load Balancer Configuration
```nginx
# docker/nginx-lb.conf
upstream openclaw_backend {
    least_conn;
    server openclaw-app:8080 max_fails=3 fail_timeout=30s;
    server openclaw-app_2:8080 max_fails=3 fail_timeout=30s;
    server openclaw-app_3:8080 max_fails=3 fail_timeout=30s;
}
```

### Database Migration (SQLite → PostgreSQL)
```bash
# Export SQLite data
python3 -c "
from enterprise_multi_client_manager import EnterpriseMultiClientManager
mgr = EnterpriseMultiClientManager()
mgr.export_to_postgresql('postgresql://user:pass@postgres:5432/openclaw')
"
```

---

## 🔍 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs
docker-compose logs openclaw-app

# Verify environment variables
docker-compose config

# Test individual components
docker run --rm -it openclaw-enterprise python3 health_check.py
```

#### API Connection Issues
```bash
# Check network connectivity
docker network ls
docker network inspect davinci-resolve-openclaw_openclaw_network

# Test API directly
curl -v http://localhost:8080/api/v1/health
```

#### Performance Issues
```bash
# Monitor resource usage
docker stats

# Check disk space
df -h
docker system df

# Clean up unused resources
docker system prune -a
```

---

## 📋 Maintenance

### Backup Strategy
```bash
# Backup data volumes
docker run --rm -v davinci-resolve-openclaw_openclaw_data:/data \
  -v $(pwd):/backup ubuntu tar czf /backup/openclaw-data-$(date +%Y%m%d).tar.gz /data

# Backup database
docker-compose exec postgres pg_dump -U openclaw openclaw > backup-$(date +%Y%m%d).sql
```

### Updates & Upgrades
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Verify deployment
curl http://localhost:8080/api/v1/health
```

### Log Rotation
```bash
# Configure logrotate for container logs
echo '/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    size=10M
    missingok
    delaycompress
    copytruncate
}' > /etc/logrotate.d/docker-containers
```

---

## 💼 Production Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Domain name pointed to server
- [ ] Firewall configured (ports 80, 443, 8080)
- [ ] Backup strategy implemented

### Security
- [ ] API keys rotated and secured
- [ ] Database passwords changed from defaults
- [ ] CORS policies configured
- [ ] Rate limiting enabled
- [ ] Log rotation configured

### Monitoring
- [ ] Health checks enabled
- [ ] Prometheus metrics configured
- [ ] Grafana dashboards imported
- [ ] Alert rules configured
- [ ] Log aggregation setup

### Performance
- [ ] Resource limits configured
- [ ] Auto-scaling rules defined
- [ ] Load balancer configured
- [ ] CDN setup for static assets
- [ ] Database optimization complete

---

## 🎯 Success Metrics

### System Health
- **Uptime**: >99.9% availability
- **API Response**: <200ms average
- **Error Rate**: <0.1% of requests
- **Resource Usage**: <80% utilization

### Business Metrics
- **Client Onboarding**: <15 minutes
- **Processing Time**: <5 minutes per video
- **Quality Score**: >0.95 average
- **Client Satisfaction**: >4.8/5 rating

---

## 🔗 Additional Resources

- **API Documentation**: `/api/v1/docs`
- **System Status**: `/health`
- **Performance Dashboard**: `:3000` (Grafana)
- **Metrics Endpoint**: `:9090` (Prometheus)

---

**🎬 DaVinci Resolve OpenClaw - Production Ready!**  
*Enterprise SaaS Platform with Docker Deployment*