# Docker Deployment Guide

This guide covers deploying SmartHome Assistant using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- A configured `.env` file (see [Configuration](#configuration))

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/k4therin2/smarthome.git
cd smarthome

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys and Home Assistant URL

# 3. Start the container
docker-compose up -d

# 4. Check the logs
docker-compose logs -f smarthome

# 5. Access the application
# HTTPS: https://localhost:5050
# HTTP (redirects to HTTPS): http://localhost:5049
```

## Configuration

### Required Environment Variables

The following must be set in your `.env` file:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (or configure alternative LLM provider) |
| `HA_URL` | Home Assistant URL (e.g., `http://homeassistant.local:8123`) |
| `HA_TOKEN` | Home Assistant long-lived access token |
| `FLASK_SECRET_KEY` | Session encryption key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Set to `development` for debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HTTP_PORT` | `5049` | HTTP port (redirects to HTTPS) |
| `HTTPS_PORT` | `5050` | HTTPS port |
| `LLM_PROVIDER` | `openai` | LLM provider (openai, anthropic, local) |

See `.env.example` for all available options.

## Persistent Data

The Docker setup uses named volumes for persistence:

| Volume | Container Path | Description |
|--------|----------------|-------------|
| `smarthome_data` | `/app/data` | SQLite database, caches |
| `smarthome_certs` | `/app/certs` | SSL certificates |
| `smarthome_logs` | `/app/logs` | Application logs |

### Backup Volumes

```bash
# Backup data volume
docker run --rm -v smarthome_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/smarthome_data_backup.tar.gz -C /data .

# Restore data volume
docker run --rm -v smarthome_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/smarthome_data_backup.tar.gz -C /data
```

## Health Checks

The container includes Kubernetes-style health probes:

- **Liveness probe** (`/healthz`): Checks if the process is alive
- **Readiness probe** (`/readyz`): Checks if all dependencies are healthy

The Docker health check uses the liveness probe:
- Runs every 30 seconds
- Checks the `/healthz` endpoint
- Marks the container unhealthy after 3 failures
- Has a 60-second startup period

Check container health:
```bash
docker inspect --format='{{.State.Health.Status}}' smarthome-assistant
```

## Development Mode

For development with hot-reloading:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This enables:
- Source code hot-reloading (bind mounts)
- Debug logging
- Flask debug mode
- Increased resource limits

## Commands

### Start/Stop

```bash
# Start in background
docker-compose up -d

# Stop
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Logs

```bash
# Follow logs
docker-compose logs -f smarthome

# Last 100 lines
docker-compose logs --tail=100 smarthome
```

### Rebuild

```bash
# Rebuild after code changes
docker-compose build

# Rebuild and restart
docker-compose up -d --build
```

### Shell Access

```bash
# Access container shell
docker-compose exec smarthome bash

# Run a command
docker-compose exec smarthome python -c "print('Hello')"
```

## Security Considerations

The Docker setup includes several security measures:

1. **Non-root user**: Container runs as `smarthome` user, not root
2. **No new privileges**: Containers cannot gain new privileges
3. **Resource limits**: CPU and memory limits prevent resource exhaustion
4. **Health checks**: Automatic container restart on failure
5. **Read-only tmpfs**: Temporary files in memory-only filesystem

### SSL Certificates

By default, the application generates self-signed certificates. For production:

1. Mount your certificates to `/app/certs`:
   ```yaml
   volumes:
     - /path/to/your/cert.pem:/app/certs/server.crt:ro
     - /path/to/your/key.pem:/app/certs/server.key:ro
   ```

2. Or use a reverse proxy (nginx, Traefik) for SSL termination

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs smarthome

# Check environment
docker-compose config

# Verify .env file
cat .env | grep -v '^#' | grep -v '^$'
```

### Can't connect to Home Assistant

- Ensure `HA_URL` is accessible from the container
- If using `localhost`, change to actual IP or use `host.docker.internal` (Docker Desktop)
- Check Home Assistant allows the Docker network

### Database errors

```bash
# Reset database (WARNING: deletes data)
docker-compose down
docker volume rm smarthome_data
docker-compose up -d
```

### Port conflicts

Change ports in `.env`:
```bash
HTTP_PORT=8049
HTTPS_PORT=8050
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```
