# InstaSpark AI — Deployment Guide

## Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| Docker      | 24.0           |
| Docker Compose | v2.20       |
| RAM         | 512 MB         |
| Disk        | 200 MB         |

## Quick Start (Docker Compose)

```bash
# 1. Clone the repository
git clone <repo-url>
cd instaspark

# 2. Create .env from template
cp .env.example .env

# 3. (Optional) Add your LLM API key for AI-generated content
echo 'LLM_API_KEY=sk-your-deepseek-key' >> .env

# 4. Build and start
docker compose up --build -d

# 5. Open in browser
open http://localhost:8501
```

The application will be available at `http://localhost:8501`.

### Default Login

| Role     | Username | Password   |
|----------|----------|------------|
| Admin    | `admin`  | `admin123` |
| Viewer   | `demo`   | `demo123`  |

**Change default credentials in `.env` before production deployment.**

## Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env

# Run the application
streamlit run app.py

# Run tests
pytest -q
```

## Docker Only (without Compose)

```bash
# Build the image
docker build -t instaspark .

# Run the container
docker run -d \
  --name instaspark \
  -p 8501:8501 \
  -v instaspark_data:/app/data \
  --env-file .env \
  instaspark

# View logs
docker logs -f instaspark

# Stop
docker stop instaspark && docker rm instaspark
```

## Environment Variables

All configuration is managed via `.env`. See `.env.example` for the full reference.

### Critical Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | _(empty)_ | LLM API key. When empty, app runs in Demo Mode with mock content. |
| `LLM_BASE_URL` | `https://api.deepseek.com` | API endpoint. Supports any OpenAI-compatible provider. |
| `LLM_MODEL` | `deepseek-chat` | Model name for content generation. |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Admin password. **Change in production.** |
| `DEFAULT_DEMO_PASSWORD` | `demo123` | Demo user password. **Change in production.** |
| `DATABASE_PATH` | `data/instaspark.db` | SQLite database path (relative to project root). |
| `PBKDF2_ITERATIONS` | `260000` | Password hashing iterations. Minimum 100,000. |

### LLM Configuration

The app supports any OpenAI-compatible LLM provider. Configure in `.env`:

**DeepSeek (default, low cost):**
```env
LLM_API_KEY=sk-your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

**OpenAI:**
```env
LLM_API_KEY=sk-your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**Moonshot (Kimi):**
```env
LLM_API_KEY=sk-your-moonshot-key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | _(empty)_ | API key for the LLM provider. |
| `LLM_BASE_URL` | `https://api.deepseek.com` | Base URL for OpenAI-compatible API. |
| `LLM_MODEL` | `deepseek-chat` | Model name for content generation. |
| `LLM_MAX_TOKENS` | `2000` | Maximum tokens per API call. |
| `LLM_TEMPERATURE` | `0.7` | Creativity level (0.0–1.0). |

### Scoring & Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `SCORE_WEIGHT_MISSION_FIT` | `0.20` | Mission fit (market + language). Mix weights must sum to 1.0. |
| `SCORE_WEIGHT_TOPIC_OVERLAP` | `0.30` | Jaccard of mission topics vs creator topics/styles. |
| `SCORE_WEIGHT_MOMENTUM` | `0.15` | Momentum weight. |
| `SCORE_WEIGHT_COMMERCIAL_FIT` | `0.15` | Commercial fit weight. |
| `SCORE_WEIGHT_BRAND_SAFETY` | `0.20` | Brand safety weight. |
| `SCORE_WEIGHT_CONTENT_FIT` | `0.30` | Legacy alias for topic overlap. |
| `SCORE_WEIGHT_AUDIENCE_FIT` | `0.20` | Legacy alias for mission fit. |
| `OPPORTUNITY_HUMAN_REVIEW_THRESHOLD` | `70` | Score below this triggers human review. |
| `OPPORTUNITY_QUALIFIED_THRESHOLD` | `75` | Score at or above qualifies for missions. |
| `OPPORTUNITY_LOW_CONFIDENCE_THRESHOLD` | `60` | Score below this is low confidence. |

## Production Deployment

### Security Checklist

1. **Change default credentials** — Set `DEFAULT_ADMIN_PASSWORD` and `DEFAULT_DEMO_PASSWORD` in `.env`
2. **Set LLM_API_KEY** — Required for AI-generated content (Brief, hooks, scripts, localization)
3. **Increase PBKDF2_ITERATIONS** — Consider 310,000+ for production (OWASP 2023 recommendation)
4. **Restrict network access** — Use a reverse proxy (nginx, Caddy) with TLS
5. **Backup SQLite database** — The `data/instaspark.db` file is the persistence layer
6. **Set up log rotation** — Docker logs can grow; configure `max-size` and `max-file`

### Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name instaspark.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

### Docker Compose with TLS

```yaml
services:
  instaspark:
    build: .
    ports:
      - "127.0.0.1:8501:8501"  # Only listen on localhost
    volumes:
      - db_data:/app/data
      - ./.env:/app/.env:ro
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - instaspark
    restart: unless-stopped

volumes:
  db_data:
```

### Cloud Deployment

#### Streamlit Community Cloud

1. Push the repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect the repository
4. Set `app.py` as the entry point
5. Add secrets in the Streamlit dashboard (equivalent to `.env`)

#### AWS / GCP / Azure

1. Build the Docker image: `docker build -t instaspark .`
2. Push to container registry (ECR / GCR / ACR)
3. Deploy on ECS / Cloud Run / Container Apps
4. Configure environment variables in the cloud console
5. Mount a persistent volume for `data/` directory

## Health Monitoring

### Health Check Endpoint

The Docker container includes a health check that hits:
```
GET http://localhost:8501/_stcore/health
```

Expected response: `200 OK` with body `{"status": "ok"}`

### View Health Status

```bash
# Docker
docker inspect --format='{{.State.Health.Status}}' instaspark

# Docker Compose
docker compose ps
```

### Database Backup

```bash
# Backup
docker exec instaspark cp /app/data/instaspark.db /app/data/backup-$(date +%Y%m%d).db

# Or copy to host
docker cp instaspark:/app/data/instaspark.db ./backup-$(date +%Y%m%d).db
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs instaspark

# Common issues:
# 1. Port 8501 already in use → change port mapping
# 2. .env file missing → cp .env.example .env
# 3. Permission denied → ensure data/ directory is writable
```

### Database locked

```bash
# If SQLite database is locked, restart the container
docker restart instaspark
```

### LLM content not generating

1. Verify `LLM_API_KEY` is set in `.env`
2. Check container environment: `docker exec instaspark env | grep LLM`
3. View application logs: `docker logs instaspark 2>&1 | grep -i llm`
4. The app shows a "Demo Mode" badge when no API key is configured

### Reset demo data

```bash
# Enter the container and reset
docker exec -it instaspark python -c "
from infra.database import init_db, reset_db
from infra.auth import seed_default_users
init_db()
reset_db()
seed_default_users()
print('Demo data reset successfully')
"
```

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Browser (UI)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Streamlit     │
                    │   (app.py)      │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │  Components  │  │  Services   │  │    Infra    │
    │  (UI layer)  │  │ (Business)  │  │ (Database)  │
    └─────────────┘  └──────┬──────┘  └──────┬──────┘
                            │                 │
                    ┌───────▼───────┐ ┌──────▼──────┐
                    │  LLM Service  │ │   SQLite    │
                    │  (OpenAI API) │ │  (.db file) │
                    └───────────────┘ └─────────────┘
```

## License

MIT — See [LICENSE](LICENSE)
