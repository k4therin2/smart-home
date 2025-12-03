# CI/CD Setup - Auto-Deploy to Windows Laptop

This guide sets up automatic deployment: **Push to GitHub → Build Docker image → Auto-deploy to Windows laptop**.

## Architecture

```
Your Mac/Dev Machine
    ↓ (git push)
GitHub (main branch)
    ↓ (GitHub Actions)
Docker Hub (published image)
    ↓ (Watchtower polling every 5 min)
Windows Laptop (auto-pulls & restarts)
```

## One-Time Setup

### 1. Create Docker Hub Account

1. Go to https://hub.docker.com/signup
2. Create free account (username: `k4therin2` or your choice)
3. Verify email

### 2. Create Docker Hub Access Token

1. Log in to Docker Hub
2. Click your username → **Account Settings**
3. Click **Security** → **New Access Token**
4. Name: `github-actions`
5. Permissions: **Read, Write, Delete**
6. Copy the token (you won't see it again!)

### 3. Add GitHub Secret

1. Go to your GitHub repo: https://github.com/k4therin2/smart-home
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `DOCKER_PASSWORD`
5. Value: Paste the Docker Hub token from step 2
6. Click **Add secret**

### 4. Update GitHub Action (if needed)

If you used a different Docker Hub username, edit `.github/workflows/docker-publish.yml`:

```yaml
env:
  DOCKER_USERNAME: your-dockerhub-username  # Change this
  IMAGE_NAME: home-automation-agent
```

And update `docker-compose.prod.yml`:

```yaml
agent:
  image: your-dockerhub-username/home-automation-agent:latest  # Change this
```

## Windows Laptop Deployment

### Initial Setup (One Time)

On your Windows laptop:

1. **Install Docker Desktop** (if not already installed)
   - Download from https://www.docker.com/products/docker-desktop/
   - Start Docker Desktop

2. **Clone the repo** (PowerShell):
   ```powershell
   git clone https://github.com/k4therin2/smart-home.git
   cd smart-home
   ```

3. **Configure environment**:
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Add your:
   - `ANTHROPIC_API_KEY`
   - `HA_TOKEN` (generate after first HA setup)

4. **Start with production compose file**:
   ```powershell
   docker-compose -f docker-compose.prod.yml up -d
   ```

### What Happens

1. **First run**:
   - Downloads Home Assistant (~500MB)
   - Downloads Agent image from Docker Hub (~200MB)
   - Starts Watchtower (monitoring service)
   - Takes ~5-10 minutes

2. **Every 5 minutes**:
   - Watchtower checks Docker Hub for new image
   - If new version found → pulls → stops old container → starts new → cleans up

3. **When you push to GitHub**:
   - GitHub Actions builds new image (~2-3 minutes)
   - Pushes to Docker Hub
   - Within 5 minutes, Watchtower pulls to Windows laptop
   - **Total time: ~7-8 minutes from push to deployed**

## Daily Workflow

### On Your Mac (Development)

```bash
# Make changes to code
# ...

# Commit and push
git add .
git commit -m "Add new feature"
git push

# GitHub Actions automatically builds and publishes
# Check status: https://github.com/k4therin2/smart-home/actions
```

### Automatic Deployment

No manual steps needed! Just wait ~7-8 minutes:

1. ✅ GitHub Actions builds (2-3 min)
2. ✅ Pushes to Docker Hub (30 sec)
3. ✅ Watchtower detects new image (next 5-min check)
4. ✅ Pulls and restarts (1 min)

### Monitoring on Windows

```powershell
# Check status
docker-compose -f docker-compose.prod.yml ps

# View Watchtower logs (see when updates happen)
docker logs watchtower -f

# View agent logs
docker logs home-agent -f

# Manual update (if impatient)
docker-compose -f docker-compose.prod.yml pull agent
docker-compose -f docker-compose.prod.yml up -d agent
```

## GitHub Actions Status

### View Build Status

1. Go to https://github.com/k4therin2/smart-home/actions
2. See workflow runs
3. Click on a run to see details

### Manual Trigger

If you want to rebuild without pushing code:

1. Go to **Actions** tab
2. Click **Build and Publish Docker Image**
3. Click **Run workflow** → **Run workflow**

## File Structure

```
Your repo/
├── .github/workflows/
│   └── docker-publish.yml      # GitHub Actions workflow
├── docker-compose.yml          # Development (local build)
├── docker-compose.prod.yml     # Production (uses Docker Hub image)
└── Dockerfile                  # Image definition
```

## Development vs Production

### Development (Your Mac)
```bash
# Use docker-compose.yml (builds locally)
docker-compose up -d
```

### Production (Windows Laptop)
```powershell
# Use docker-compose.prod.yml (pulls from Docker Hub)
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### GitHub Actions fails with "unauthorized"
- Check GitHub secret `DOCKER_PASSWORD` is set correctly
- Verify Docker Hub access token is valid
- Check Docker Hub username in workflow matches your account

### Watchtower not updating
```powershell
# Check Watchtower is running
docker ps | findstr watchtower

# View Watchtower logs
docker logs watchtower

# Check if new image exists
docker pull k4therin2/home-automation-agent:latest

# Force update
docker-compose -f docker-compose.prod.yml pull agent
docker-compose -f docker-compose.prod.yml up -d agent
```

### Image pull fails on Windows
- Ensure Docker Desktop is running
- Check internet connection
- Verify image name matches Docker Hub: `k4therin2/home-automation-agent:latest`

### Want faster updates
Edit `docker-compose.prod.yml` and change:
```yaml
- WATCHTOWER_POLL_INTERVAL=60  # Check every 1 minute (faster but more requests)
```

## Cost

- **Docker Hub Free Tier**: Unlimited public images ✅
- **GitHub Actions**: 2,000 free minutes/month ✅
- **Your setup**: ~3 minutes per build = ~600 builds/month free

## Security Notes

- Docker Hub image is **public** (anyone can pull it)
- **Secrets are NOT in the image** (they're in `.env` file on Windows laptop)
- Never commit `.env` file to GitHub
- GitHub secrets are encrypted and only accessible to workflows

## Next Steps

Once set up:
1. ✅ Make a test change and push to verify workflow
2. ✅ Watch GitHub Actions build
3. ✅ Wait ~8 minutes and check Windows laptop
4. ✅ Verify new version is running: `docker logs home-agent`

## Rollback

If a bad deployment happens:

```powershell
# Stop watchtower temporarily
docker stop watchtower

# Pull specific version (use commit SHA)
docker pull k4therin2/home-automation-agent:main-abc1234

# Update docker-compose.prod.yml to use that tag
# Restart
docker-compose -f docker-compose.prod.yml up -d agent

# Restart watchtower when ready
docker start watchtower
```

## Alternative: Manual Deployment

If you don't want auto-deployment, just:

```powershell
# On Windows laptop, periodically run:
git pull
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```
