FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    redis-server \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator.py .
COPY api/ ./api/
COPY core/ ./core/
COPY templates/ ./templates/

RUN mkdir -p outputs

RUN cat > /app/redis.conf << 'REDIS_CONF'
bind 0.0.0.0
port 6379
protected-mode no
daemonize yes
replica-read-only no
REDIS_CONF

RUN cat > /app/start.sh << 'SCRIPT_EOF'
#!/bin/bash
set -e

redis-server /app/redis.conf

for i in {1..30}; do
    if redis-cli -h localhost ping 2>/dev/null | grep -q PONG; then
        echo "Redis ready!"
        break
    fi
    sleep 1
done

exec python orchestrator.py --host 0.0.0.0 --redis-host 127.0.0.1 --redis-port 6379 --reset-state
SCRIPT_EOF
RUN chmod +x /app/start.sh

EXPOSE 5000 6379

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["/app/start.sh"]
