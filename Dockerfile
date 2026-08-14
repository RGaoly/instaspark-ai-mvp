# ─── Dockerfile for InstaSparkAI ───────────────────────────────
# Multi-stage build: install deps → copy app → run as non-root user
# ───────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies to a target directory
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime

LABEL maintainer="InstaSparkAI Team"
LABEL description="Creator marketing collaboration workspace powered by AI"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create data directory with correct permissions
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Expose Streamlit port
EXPOSE 8501

# Health check — verify Streamlit is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
# --server.address=0.0.0.0  : bind to all interfaces
# --server.port=8501         : default Streamlit port
# --server.headless=true     : no browser auto-open
ENTRYPOINT ["streamlit", "run", "app.py"]
CMD ["--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
