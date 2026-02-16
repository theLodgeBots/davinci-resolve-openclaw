# 🐳 DaVinci Resolve OpenClaw - Production Docker Container
# Enterprise SaaS Platform Ready
# Built for multi-client deployment with full API stack

FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV OPENCLAW_ENV=production
ENV API_PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    curl \
    wget \
    git \
    sqlite3 \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd -m -u 1000 openclaw && \
    mkdir -p /app /var/openclaw/clients /var/log/openclaw && \
    chown -R openclaw:openclaw /app /var/openclaw /var/log/openclaw

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=openclaw:openclaw . .

# Create necessary directories
RUN mkdir -p /var/openclaw/clients/{configs,workspaces,logs} && \
    chown -R openclaw:openclaw /var/openclaw

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/sites-available/default
COPY docker/supervisor.conf /etc/supervisor/conf.d/openclaw.conf

# Create startup script
COPY docker/startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

# Expose ports
EXPOSE 8080 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

# Switch to application user
USER openclaw

# Default command
CMD ["/app/startup.sh"]