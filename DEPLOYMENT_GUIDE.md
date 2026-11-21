# JanSahayak Production Deployment, Operations & Rollback Guide

This document outlines the standard operating procedures for deploying, maintaining, backing up, and rolling back JanSahayak in a controlled pilot or production environment.

---

## 1. Environment Architecture

```
                       [ Reverse Proxy / Load Balancer (Nginx / Cloudflare) ]
                                      |                     |
                        Port 80/443   |                     | Port 80/443
                                      v                     v
                             [ Next.js Frontend ]   [ Django Backend API ]
                             (Node 20 / Port 3000)  (Gunicorn / Port 8000)
                                                            |
                                              +-------------+-------------+
                                              |                           |
                                      [ PostgreSQL 16 ]            [ Local/S3 Media ]
                                      (Port 5432)                  (/app/media)
```

---

## 2. Pre-Deployment Configuration Checklist

Before initiating deployment:
1. **Secret Generation**:
   Generate a strong random secret key:
   ```bash
   python -c 'import secrets; print(secrets.token_urlsafe(50))'
   ```
2. **Environment File**:
   Copy `.env.production.example` to `.env` on the host:
   ```bash
   cp .env.production.example .env
   chmod 600 .env
   ```
3. **Verify Critical Variables**:
   - `DJANGO_ENV=production`
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=<your-production-domains>`
   - `CORS_ALLOWED_ORIGINS=<your-frontend-domain>`
   - `CSRF_TRUSTED_ORIGINS=<your-frontend-domain>`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`

---

## 3. Deployment Procedures

### Option A: Standard Virtualenv + Systemd Deployment

1. **Backend Setup**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt gunicorn psycopg2-binary
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

2. **Systemd Service for Gunicorn** (`/etc/systemd/system/jansahayak-backend.service`):
   ```ini
   [Unit]
   Description=JanSahayak Django Gunicorn Daemon
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/jansahayak/backend
   EnvironmentFile=/var/www/jansahayak/.env
   ExecStart=/var/www/jansahayak/backend/venv/bin/gunicorn \
             --config gunicorn_conf.py \
             jansahayak_project.wsgi:application
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Frontend Setup**:
   ```bash
   cd ../frontend
   npm ci
   npm run build
   ```

4. **Systemd Service for Next.js** (`/etc/systemd/system/jansahayak-frontend.service`):
   ```ini
   [Unit]
   Description=JanSahayak Next.js Frontend
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/jansahayak/frontend
   Environment=NODE_ENV=production
   Environment=PORT=3000
   ExecStart=/usr/bin/npm run start
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

### Option B: Docker Compose Deployment

```bash
# 1. Start containers in detached mode
docker-compose up -d --build

# 2. Run database migrations inside container
docker-compose exec backend python manage.py migrate

# 3. Verify health
curl -s http://localhost:8000/api/health/
```

---

## 4. Health & Diagnostics Verification

JanSahayak exposes two health monitoring endpoints:

1. **Public Ping** (for Cloud Load Balancers, Route53, Kubernetes probes):
   ```bash
   curl -I https://api.jansahayak.gov.in/api/health/
   # Expected: HTTP/1.1 200 OK
   # Response: {"status":"healthy","service":"JanSahayak Civic Platform",...}
   ```

2. **Administrative Deep Diagnostics** (Admin/Staff Token Required):
   ```bash
   curl -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" https://api.jansahayak.gov.in/api/health/diagnostics/
   # Response:
   # {
   #   "status": "healthy",
   #   "checks": {
   #     "database": {"connected": true, "latency_ms": 1.45},
   #     "media_storage": {"writable": true},
   #     "ai_service": {"provider": "Google Gemini", "configured": true, "mode": "hybrid-fallback"}
   #   }
   # }
   ```

---

## 5. Database Backup and Restore Procedures

### Database Backup
Automate daily backups using cron:
```bash
# Daily PostgreSQL dump
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -Fc -f /backups/jansahayak_$(date +%Y%m%d_%H%M%S).dump

# Media files backup (rsync / tar)
tar -czf /backups/media_$(date +%Y%m%d).tar.gz /var/www/jansahayak/backend/media/
```

### Database Restore
To restore database state from a backup:
```bash
# 1. Stop backend service
sudo systemctl stop jansahayak-backend

# 2. Restore PostgreSQL dump
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME --clean --if-exists /backups/jansahayak_YYYYMMDD_HHMMSS.dump

# 3. Restart backend service
sudo systemctl start jansahayak-backend
```

---

## 6. Rollback Procedures

If a deployment introduces regressions or unexpected errors:

1. **Git Code Rollback**:
   ```bash
   # Revert to previous release tag or stable commit
   git checkout <PREVIOUS_STABLE_COMMIT_OR_TAG>
   ```

2. **Re-build & Restart Services**:
   ```bash
   # Backend
   cd backend && python manage.py migrate
   sudo systemctl restart jansahayak-backend

   # Frontend
   cd ../frontend && npm ci && npm run build
   sudo systemctl restart jansahayak-frontend
   ```

3. **Verify Recovery**:
   ```bash
   curl -f http://localhost:8000/api/health/ || echo "Backend Unhealthy"
   curl -f http://localhost:3000/ || echo "Frontend Unhealthy"
   ```

