# CycleOPS Orchestrator Server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    redis-server \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY orchestrator.py .
COPY api/ ./api/
COPY core/ ./core/
COPY templates/ ./templates/

# Create outputs directory
RUN mkdir -p outputs

# Expose ports
EXPOSE 5000 6379

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run orchestrator
CMD ["python", "orchestrator.py"]
